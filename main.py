#!/usr/bin/env python3
"""
Main orchestration module for the AI Job Agent.
Provides CLI interface to automate scraping, resume tailoring, email sending, and logging.

Usage:
    python main.py                    # Run with default config
    python main.py --config custom.json  # Run with custom config
    python main.py --help             # Show help
"""

import argparse
import os
import smtplib
import sys
import time
import logging
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List
import re
import asyncio
import traceback
import json

from dotenv import load_dotenv
load_dotenv()

# Environment variables validation
required_env_vars = [
    "OPENAI_API_KEY",
    "GMAIL_SENDER_EMAIL",
    "GMAIL_APP_PASSWORD",
    "SPREADSHEET_ID",
    "GOOGLE_CREDENTIALS_JSON_PATH"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Environment variables
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
openai_api_key = os.getenv("OPENAI_API_KEY")
gmail_sender_email = os.getenv("GMAIL_SENDER_EMAIL")
gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
spreadsheet_id = os.getenv("SPREADSHEET_ID")
google_sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

# Custom modules
import job_scraper
import email_scanner
import resume_tailor
import sheets_logger
import email_sender
from helpers import load_config, validate_email
from logger import logger, notify_slack
from job_sources import get_job_source
from linkedin_scraper import LinkedInScraper


def validate_sheet_url(config: Dict, logger: logging.Logger) -> str:
    sheet_url = os.getenv("GOOGLE_SHEET_URL") or f"https://docs.google.com/spreadsheets/d/{os.getenv('SPREADSHEET_ID')}/edit"
    if not sheet_url:
        logger.error("Google Sheet URL missing in environment. Add 'GOOGLE_SHEET_URL' or 'SPREADSHEET_ID'.")
        raise ValueError("Missing Google Sheet URL in environment.")
    logger.info(f"Using Google Sheet URL: {sheet_url}")
    return sheet_url


def find_recruiter_email(job: Dict) -> str:
    if not job.get('description'):
        return ""
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w{2,}'
    if match := re.search(email_pattern, job['description']):
        email = match.group(0)
        if validate_email(email):
            return email
    company = job.get('company', '').lower().replace(' ', '')
    if company:
        common_domains = [f"{company}.com", f"{company}.co", f"{company}.org"]
        common_prefixes = ['careers', 'jobs', 'recruiting', 'hr', 'talent']
        for domain in common_domains:
            for prefix in common_prefixes:
                email = f"{prefix}@{domain}"
                if validate_email(email):
                    return email
    return ""


def send_cold_email(recruiter_email: str, job: Dict, user_profile: Dict, gmail_config: Dict) -> None:
    if not recruiter_email or not validate_email(recruiter_email):
        logger.error(f"Invalid recruiter email: {recruiter_email}")
        raise ValueError(f"Invalid recruiter email: {recruiter_email}")
        
    if not job.get('title') or not job.get('company'):
        logger.error("Job title and company are required")
        raise ValueError("Job title and company are required")
        
    if not user_profile.get('full_name') or not user_profile.get('email'):
        logger.error("User full name and email are required")
        raise ValueError("User full name and email are required")
        
    if not gmail_config.get('sender_email') or not gmail_config.get('app_password'):
        logger.error("Gmail sender email and app password are required")
        raise ValueError("Gmail sender email and app password are required")
        
    subject = f"Application for {job['title']} at {job['company']}"
    body = (
        f"Hello,\n\n"
        f"My name is {user_profile['full_name']}. I'm interested in the {job['title']} role at {job['company']} "
        f"(posted on {job.get('date_posted', '')}).\n\n"
        f"[Insert bullet summary of match here]\n"
        f"Resume: [LINK]\n"
        f"Cover letter: [OPTIONAL LINK]\n\n"
        f"Thank you for your time.\n\n"
        f"{user_profile['full_name']}\n"
        f"Email: {user_profile['email']}\n"
        f"LinkedIn: {user_profile.get('linkedin_profile_url', '[YOUR_LINKEDIN_URL]')}"
    )
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = gmail_config['sender_email']
    msg["To"] = recruiter_email
    msg.set_content(body)
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_config['sender_email'], gmail_config['app_password'])
            smtp.send_message(msg)
            logger.info(f"Cold email sent to {recruiter_email} for {job['title']}")
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}")
        if job.get('notifications', {}).get('slack', {}).get('enabled'):
            notify_slack(f"Failed to send email to {recruiter_email}: {e}")
        raise


def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)


class JobAgent:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.logger = setup_logging()
        self.logger.info("Job Agent Started")
        self.browser = None
        self.page = None
        self.metrics = {
            'total_jobs': 0,
            'new_jobs': 0,
            'applications': 0,
            'success_rate': 0,
            'errors': []
        }
        
        # Validate required config sections
        if not self.config.get('credentials'):
            raise ValueError("Credentials section missing in config")
        if not self.config.get('search'):
            raise ValueError("Search section missing in config")
        if not self.config['search'].get('job_titles') or not self.config['search'].get('locations'):
            raise ValueError("Job titles and locations are required in search config")
            
        # Set up credentials
        self.linkedin_credentials = self.config['credentials'].get('linkedin', {})
        self.google_credentials = self.config['credentials'].get('google', {})
        self.openai_credentials = self.config['credentials'].get('openai', {})
        
        # Set up search parameters
        self.search_config = self.config['search']
        self.job_titles = self.search_config['job_titles']
        self.locations = self.search_config['locations']
        self.keywords = self.search_config.get('keywords', [])
        self.max_results = self.search_config.get('max_results_per_source', 20)
        
        # Set up job sources
        self.job_sources = self.config.get('job_sources', ['linkedin', 'indeed'])
        
        # Set up Google Sheets config
        self.sheets_config = self.config.get('google_sheets', {})
        if not self.sheets_config.get('spreadsheet_id'):
            raise ValueError("Google Sheets spreadsheet_id is required in config")
            
        # Set up notifications
        self.notifications = self.config.get('notifications', {})
        
        # Set up user profile
        self.user_profile = self.config.get('user_profile', {})
        if not self.user_profile.get('email'):
            raise ValueError("User email is required in user_profile config")

    async def scrape_mode(self):
        """Run in scrape mode to find and save new jobs."""
        try:
            self.logger.info("Scrape mode started.")
            
            # Get existing job URLs from Google Sheets
            existing_urls = sheets_logger.get_existing_job_urls(
                self.sheets_config['spreadsheet_id'],
                self.sheets_config['sheet_name']
            )
            
            # Initialize metrics
            metrics = {
                'total_jobs': 0,
                'new_jobs': 0,
                'applications': 0,
                'success_rate': 0,
                'errors': []
            }
            
            # Get keywords and locations from config
            keywords = self.config.get('search', {}).get('keywords', [])
            locations = self.config.get('search', {}).get('locations', [])
            max_results = self.config.get('search', {}).get('max_results_per_source', 20)
            
            if not keywords or not locations:
                raise ValueError("No keywords or locations found in config")
                
            # Scrape jobs from each source
            all_jobs = []
            for source_name in self.config.get('job_sources', []):
                try:
                    self.logger.info(f"Scraping jobs from {source_name}")
                    source = get_job_source(source_name, self.config)
                    jobs = await source.scrape_jobs(keywords, locations, max_pages=3)
                    
                    # Filter out existing jobs
                    new_jobs = [job for job in jobs if job['job_url'] not in existing_urls]
                    
                    # Update metrics
                    metrics['total_jobs'] += len(jobs)
                    metrics['new_jobs'] += len(new_jobs)
                    
                    # Add new jobs to list
                    all_jobs.extend(new_jobs)
                    
                except Exception as e:
                    error_msg = f"Error scraping {source_name}: {str(e)}"
                    self.logger.error(error_msg)
                    metrics['errors'].append(error_msg)
                    
            # Save new jobs to Google Sheets
            if all_jobs:
                try:
                    sheets_logger.save_jobs_to_sheets(all_jobs, self.sheets_config)
                    self.logger.info(f"Saved {len(all_jobs)} new jobs to Google Sheets")
                except Exception as e:
                    error_msg = f"Error saving jobs to sheets: {str(e)}"
                    self.logger.error(error_msg)
                    metrics['errors'].append(error_msg)
                    
            # Log daily metrics
            try:
                sheets_logger.log_daily_metrics(metrics, self.sheets_config['spreadsheet_id'], self.sheets_config['metrics_sheet_name'])
                self.logger.info("Daily metrics logged successfully")
            except Exception as e:
                error_msg = f"Error logging metrics: {str(e)}"
                self.logger.error(error_msg)
                metrics['errors'].append(error_msg)
                
            self.logger.info("Scrape mode finished.")
            
        except Exception as e:
            self.logger.error(f"Error in scrape mode: {str(e)}")
            raise

    def send_emails_mode(self) -> None:
        self.logger.info("Send Emails mode started.")
        try:
            if not self.notifications.get('email', {}).get('enabled'):
                self.logger.info("Email notifications are disabled in config.")
                return
                
            if not self.google_credentials.get('gmail'):
                raise ValueError("Gmail credentials are required in config")
                
            jobs_to_email = sheets_logger.get_jobs_for_email_sending(
                self.sheets_config['spreadsheet_id'],
                self.sheets_config['sheet_name']
            )
            
            if not jobs_to_email:
                self.logger.info("No jobs to email.")
                return
                
            batch_size = 10
            for i in range(0, len(jobs_to_email), batch_size):
                batch = jobs_to_email[i:i + batch_size]
                results = email_sender.send_bulk_cold_emails(
                    batch,
                    self.user_profile,
                    self.google_credentials['gmail']
                )
                
                for idx, status in enumerate(results.get('statuses', [])):
                    if status:
                        try:
                            sheets_logger.mark_cold_email_sent(
                                batch[idx]['row_number'],
                                self.sheets_config['spreadsheet_id'],
                                self.sheets_config['sheet_name']
                            )
                            self.metrics['emails_sent'] += 1
                        except Exception as e:
                            self.logger.error(f"Sheet update failed: {e}")
                            self.metrics['errors'].append(f"Sheet update failed: {e}")
                    else:
                        error_msg = f"Failed to send to {batch[idx].get('recruiter_email')}"
                        self.logger.error(error_msg)
                        self.metrics['errors'].append(error_msg)
                        
                if i + batch_size < len(jobs_to_email):
                    time.sleep(30)
                    
                sheets_logger.log_daily_metrics(
                    self.metrics,
                    self.sheets_config['spreadsheet_id'],
                    self.sheets_config['metrics_sheet_name']
                )
                
            self.logger.info("Send Emails mode finished.")
            
        except Exception as e:
            error_msg = f"Send Emails mode failed: {e}"
            self.logger.error(error_msg)
            if self.notifications.get('slack', {}).get('enabled'):
                notify_slack(error_msg)
            raise

    def mark_applied_mode(self, row_indices: List[int]) -> None:
        if not row_indices:
            raise ValueError("No row indices provided")
        self.logger.info("Mark Applied mode started.")
        try:
            for row_index in row_indices:
                try:
                    sheets_logger.mark_applied(row_index)
                    self.metrics['applications_submitted'] += 1
                except Exception as e:
                    self.metrics['errors'].append(f"Row {row_index} error: {e}")
            sheets_logger.log_daily_metrics(self.metrics)
            self.logger.info("Mark Applied mode finished.")
        except Exception as e:
            self.logger.error(f"Mark Applied mode failed: {e}")
            raise

    def test_mode(self) -> Dict[str, bool]:
        """Run system tests and return results."""
        self.logger.info("Starting system test...")
        
        results = {}
        
        # Test config validation
        try:
            self.logger.info("[PASS] Config validation passed")
            results['config_validation'] = True
        except Exception as e:
            self.logger.error(f"[FAIL] Config validation failed: {e}")
            results['config_validation'] = False
        
        # Test LinkedIn credentials and login
        try:
            # Force use of environment variables
            linkedin_email = os.getenv("LINKEDIN_EMAIL")
            linkedin_password = os.getenv("LINKEDIN_PASSWORD")
            print("[DEBUG] LINKEDIN_EMAIL (forced):", linkedin_email)
            print("[DEBUG] LINKEDIN_PASSWORD (forced):", linkedin_password)
            if not linkedin_email or not linkedin_password:
                raise ValueError("LinkedIn credentials missing")
            print("[FATAL DEBUG] About to instantiate LinkedInScraper with:", linkedin_email, linkedin_password)
            with LinkedInScraper(
                email=linkedin_email,
                password=linkedin_password
            ) as scraper:
                scraper.login()
                jobs = scraper.search_jobs(
                    keywords="python developer",
                    location="remote",
                    max_pages=1
                )
                if not jobs:
                    raise ValueError("No jobs found in test search")
                self.logger.info(f"[PASS] LinkedIn login and job search successful - found {len(jobs)} jobs")
                results['linkedin_functionality'] = True
        except Exception as e:
            self.logger.error(f"[FAIL] LinkedIn functionality test failed: {e}")
            results['linkedin_functionality'] = False
        
        # Test Google credentials and Sheets access
        try:
            if not self.google_credentials.get('credentials_json_path'):
                raise ValueError("Google credentials missing")
            
            # Test actual Sheets access
            sheet_url = validate_sheet_url(self.config, self.logger)
            existing_urls = sheets_logger.get_existing_job_urls(
                self.sheets_config['spreadsheet_id'],
                self.sheets_config['sheet_name']
            )
            self.logger.info(f"[PASS] Google Sheets access verified - found {len(existing_urls)} existing job URLs")
            results['sheets_functionality'] = True
        except Exception as e:
            self.logger.error(f"[FAIL] Google Sheets functionality test failed: {e}")
            results['sheets_functionality'] = False
        
        # Test OpenAI credentials and API
        try:
            if not openai_api_key:
                raise ValueError("OpenAI API key missing")
            # Test actual API call
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test message"}],
                max_tokens=5
            )
            self.logger.info("[PASS] OpenAI API test successful")
            results['openai_functionality'] = True
        except Exception as e:
            self.logger.error(f"[FAIL] OpenAI functionality test failed: {e}")
            results['openai_functionality'] = False
        
        # Test email configuration and sending
        try:
            gmail_config = self.google_credentials.get('gmail', {})
            if not gmail_config.get('sender_email') or not gmail_config.get('app_password'):
                raise ValueError("Gmail configuration missing")
            
            # Test actual email sending
            test_email = "test@example.com"  # Replace with a real test email
            test_job = {
                'title': 'Test Job',
                'company': 'Test Company',
                'date_posted': '2024-01-01'
            }
            test_profile = {
                'full_name': 'Test User',
                'email': gmail_config['sender_email']
            }
            
            send_cold_email(
                recruiter_email=test_email,
                job=test_job,
                user_profile=test_profile,
                gmail_config=gmail_config
            )
            self.logger.info("[PASS] Email sending test successful")
            results['email_functionality'] = True
        except Exception as e:
            self.logger.error(f"[FAIL] Email functionality test failed: {e}")
            results['email_functionality'] = False
        
        # Print summary
        self.logger.info("\nTest Results Summary:")
        for test, status in results.items():
            self.logger.info(f"[{'PASS' if status else 'FAIL'}] {test}")
        
        # Calculate overall success rate
        total_tests = len(results)
        passed_tests = sum(1 for status in results.values() if status)
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        self.logger.info(f"\nOverall Test Results: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        return results

    async def login_to_linkedin(self) -> bool:
        """Login to LinkedIn with retries and comprehensive error handling"""
        selectors = [
            '.global-nav__me-photo',  # Profile photo
            '.global-nav__me-menu',   # Profile menu
            '.feed-identity-module',  # Feed module
            '.search-global-typeahead'  # Search bar
        ]
        max_retries = 3
        base_timeout = 30000  # 30 seconds
        backoff_waits = [5, 10, 20]  # seconds

        try:
            self.logger.info("Navigating to LinkedIn login page...")
            await self.page.goto('https://www.linkedin.com/login')
            self.logger.info("✅ Successfully navigated to LinkedIn login page.")

            await self.page.fill('#username', self.config['linkedin_email'])
            await self.page.fill('#password', self.config['linkedin_password'])
            await self.page.click('button[type="submit"]')
            self.logger.info("Submitted login credentials.")

            for attempt in range(max_retries):
                self.logger.info(f"Login attempt {attempt + 1} of {max_retries}...")
                try:
                    for selector in selectors:
                        self.logger.debug(f"Checking for selector: {selector} (attempt {attempt + 1})")
                        try:
                            await self.page.wait_for_selector(selector, timeout=base_timeout + attempt * 10000)
                            self.logger.info(f"✅ Login successful! Detected by selector: {selector}")
                            return True
                        except Exception:
                            self.logger.debug(f"Selector {selector} not found on attempt {attempt + 1}")
                    # If none of the selectors matched, raise to trigger retry/backoff
                    raise Exception("No login success selectors found.")
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_waits[attempt]
                        self.logger.warning(f"Login attempt {attempt + 1} failed: {e}. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        # Final failure: log details, screenshot, and HTML snapshot
                        current_url = self.page.url
                        self.logger.error(f"Login failed after {max_retries} attempts.")
                        self.logger.error(f"Current URL: {current_url}")
                        self.logger.error(f"Traceback: {traceback.format_exc()}")
                        screenshot_path = f'logs/login_failure_{int(time.time())}.png'
                        await self.page.screenshot(path=screenshot_path)
                        self.logger.error(f"Screenshot saved to: {screenshot_path}")
                        html_path = f'logs/login_failure_{int(time.time())}.html'
                        html_content = await self.page.content()
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        self.logger.error(f"HTML snapshot saved to: {html_path}")

                        if "checkpoint" in current_url or "captcha" in current_url.lower():
                            self.logger.warning("⚠️ 2FA or CAPTCHA detected. Please complete manually in the browser.")
                            input("Press Enter after completing 2FA/CAPTCHA in the browser...")
                            self.logger.info("Manual intervention complete. Re-checking login status...")
                            # Try all selectors again after manual intervention
                            for selector in selectors:
                                self.logger.debug(f"Checking for selector after manual intervention: {selector}")
                                try:
                                    await self.page.wait_for_selector(selector, timeout=30000)
                                    self.logger.info(f"✅ Login successful after manual intervention! Detected by selector: {selector}")
                                    return True
                                except Exception:
                                    self.logger.debug(f"Selector {selector} not found after manual intervention.")
                            self.logger.error("Login still failed after manual intervention.")
                            return False
                        else:
                            self.logger.error("Login failed and no 2FA/CAPTCHA detected.")
                            return False
            return False
        except Exception as e:
            self.logger.error(f"Login failed with error: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def scrape_indeed_jobs(self, keywords: List[str], location: str) -> List[Dict]:
        """Scrape jobs from Indeed"""
        try:
            if not keywords:
                self.logger.warning("No keywords provided for Indeed search")
                return []
                
            self.logger.info(f"Starting Indeed job scraping for '{keywords}' in '{location}'")
            
            # Format keywords for URL
            keyword_str = '+'.join(kw.strip() for kw in keywords if kw.strip())
            location_str = location.strip().replace(' ', '+')
            
            # Construct search URL
            search_url = f"https://www.indeed.com/jobs?q={keyword_str}&l={location_str}"
            self.logger.debug(f"Indeed search URL: {search_url}")
            
            # Navigate to search page
            await self.page.goto(search_url)
            await self.page.wait_for_selector('.job_seen_beacon', timeout=30000)
            
            # Extract job listings
            jobs = await self.page.evaluate('''() => {
                const jobs = [];
                document.querySelectorAll('.job_seen_beacon').forEach(job => {
                    jobs.push({
                        title: job.querySelector('.jobTitle')?.textContent?.trim() || '',
                        company: job.querySelector('.companyName')?.textContent?.trim() || '',
                        location: job.querySelector('.companyLocation')?.textContent?.trim() || '',
                        url: job.querySelector('a.jcs-JobTitle')?.href || '',
                        date_posted: job.querySelector('.date')?.textContent?.trim() || '',
                        description: job.querySelector('.job-snippet')?.textContent?.trim() || ''
                    });
                });
                return jobs;
            }''')
            
            self.logger.info(f"Indeed scraping completed: {len(jobs)} jobs found")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error searching Indeed jobs: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def scan_gmail(self) -> None:
        """Scan Gmail for job-related emails"""
        try:
            if not os.path.exists('credentials.json'):
                self.logger.warning("Gmail credentials not found. Skipping email scanning.")
                return

            self.logger.info("Starting Gmail scan...")
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', ['https://www.googleapis.com/auth/gmail.readonly'])
                    creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

            service = build('gmail', 'v1', credentials=creds)
            results = service.users().messages().list(userId='me', q='is:unread').execute()
            messages = results.get('messages', [])

            if not messages:
                self.logger.info("No new emails found")
                return

            self.logger.info(f"Found {len(messages)} unread messages")
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id']).execute()
                subject = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), '')
                self.logger.info(f"Processing email: {subject}")

        except Exception as e:
            self.logger.error(f"Error scanning Gmail: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")


def parse_args():
    parser = argparse.ArgumentParser(description='AI Job Agent')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--test', action='store_true', help='Run system tests')
    parser.add_argument('--scrape', action='store_true', help='Run in scrape mode')
    parser.add_argument('--send-emails', action='store_true', help='Run in send emails mode')
    return parser.parse_args()


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('job_agent.log', encoding='utf-8')
        ]
    )
    return logging.getLogger('job_agent')


def main():
    args = parse_args()
    agent = JobAgent(args.config)
    
    if args.test:
        agent.test_mode()
    elif args.scrape:
        asyncio.run(agent.scrape_mode())
    elif args.send_emails:
        agent.send_emails_mode()
    else:
        print("Please specify a mode: --test, --scrape, or --send-emails")

if __name__ == "__main__":
    main()
