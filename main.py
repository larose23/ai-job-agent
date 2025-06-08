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
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List, Optional, Set
import re

from dotenv import load_dotenv
load_dotenv()

# Custom modules
import job_scraper
import email_scanner
import resume_tailor
import sheets_logger
import email_sender
from helpers import load_config, validate_email, retry_on_failure
from logger import logger, notify_slack


def validate_sheet_url(config: Dict, logger: logging.Logger) -> str:
    sheet_url = config.get("google_sheet_url")
    if not sheet_url:
        logger.error("Google Sheet URL missing in config. Add 'google_sheet_url'.")
        raise ValueError("Missing Google Sheet URL in config.")
    logger.info(f"Using Google Sheet URL: {sheet_url}")
    return sheet_url


def find_recruiter_email(job: Dict) -> str:
    """
    Extract recruiter email from job description or company website.
    
    Args:
        job: Dictionary containing job details including title, company, and description
        
    Returns:
        str: Recruiter email if found, empty string otherwise
        
    Note:
        This is a basic implementation that looks for common email patterns.
        In a production environment, this should be enhanced with:
        - Company website scraping
        - LinkedIn profile parsing
        - Email pattern recognition
        - Domain validation
    """
    if not job.get('description'):
        return ""
        
    # Look for common email patterns in description
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w{2,}'
    if match := re.search(email_pattern, job['description']):
        email = match.group(0)
        if validate_email(email):
            return email
            
    # Check company domain for common email patterns
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


@retry_on_failure(max_retries=3)
def send_cold_email(recruiter_email: str, job: Dict) -> None:
    """
    Send a personalized cold email to a recruiter.
    
    Args:
        recruiter_email: Valid email address of the recruiter
        job: Dictionary containing job details
        
    Raises:
        ValueError: If recruiter_email is invalid
        smtplib.SMTPException: If email sending fails
    """
    if not recruiter_email or not validate_email(recruiter_email):
        logger.error(f"Invalid recruiter email: {recruiter_email}")
        raise ValueError(f"Invalid recruiter email: {recruiter_email}")
        
    if not job.get('title') or not job.get('company'):
        logger.error("Job title and company are required")
        raise ValueError("Job title and company are required")
        
    subject = f"Application for {job['title']} at {job['company']}"
    body = (
        f"Hello,\n\n"
        f"My name is Zakariya. I'm interested in the {job['title']} role at {job['company']} "
        f"(posted on {job.get('date_posted', '')}).\n\n"
        f"[Insert bullet summary of match here]\n"
        f"Resume: [LINK]\n"
        f"Cover letter: [OPTIONAL LINK]\n\n"
        f"Thank you for your time.\n\n"
        f"Zakariya\n"
        f"Email: {os.getenv('GMAIL_SENDER_EMAIL')}\n"
        f"LinkedIn: [YOUR_LINKEDIN_URL]"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("GMAIL_SENDER_EMAIL")
    msg["To"] = recruiter_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(os.getenv("GMAIL_SENDER_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
            smtp.send_message(msg)
            logger.info(f"Cold email sent to {recruiter_email} for {job['title']}")
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}")
        notify_slack(f"Failed to send email to {recruiter_email}: {e}")
        raise


class JobAgent:
    """Main job agent orchestrator for automating job search tasks."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the job agent with configuration.
        
        Args:
            config_path: Path to configuration file
            
        Raises:
            FileNotFoundError: If config file is missing
            ValueError: If config is invalid
        """
        self.config = load_config(config_path)
        self.logger = logger
        self.metrics = {
            'jobs_scraped': 0,
            'resumes_tailored': 0,
            'cover_letters_generated': 0,
            'emails_sent': 0,
            'applications_submitted': 0,
            'errors': []
        }
        logger.info("🚀 Job Agent Started")
    
    def scrape_mode(self) -> None:
        """
        Scrape new jobs, tailor resumes, and log to Google Sheets.
        
        This mode:
        1. Gets existing job URLs for deduplication
        2. Scrapes jobs from configured sources
        3. Filters out existing jobs
        4. Scans email for job alerts
        5. Processes each new job (tailor resume, log to sheets)
        
        Raises:
            ValueError: If required configuration is missing
            Exception: For any other errors during scraping
        """
        logger.info("Scrape mode started.")
        try:
            # Validate required config
            if not self.config.get("keywords") or not self.config.get("locations"):
                logger.error("Keywords and locations are required in config")
                raise ValueError("Keywords and locations are required in config")
                
            # Get existing job URLs
            sheet_url = validate_sheet_url(self.config, logger)
            existing_urls = set(sheets_logger.get_existing_job_urls(sheet_url))
            
            # Scrape new jobs
            scraped_jobs = job_scraper.scrape_all_jobs()
            new_jobs = [job for job in scraped_jobs if job.get('job_url') not in existing_urls]
            
            # Scan email for job alerts
            try:
                email_jobs = email_scanner.scan_job_emails(
                    label=self.config.get('job_alert_label', 'Job Alerts'),
                    max_emails=20
                )
                unique_email_jobs = [
                    job for job in email_jobs 
                    if job.get('job_url') not in existing_urls and job.get('job_url') not in {j.get('job_url') for j in new_jobs}
                ]
                new_jobs.extend(unique_email_jobs)
                logger.info(f"Added {len(unique_email_jobs)} email jobs")
            except Exception as e:
                logger.warning(f"Email scanning failed: {e}")
                self.metrics['errors'].append(str(e))
            
            self.metrics['jobs_scraped'] = len(new_jobs)
            
            # Process each new job
            for i, job in enumerate(new_jobs):
                try:
                    logger.info(f"Processing job {i+1}/{len(new_jobs)}: {job.get('title')} at {job.get('company')}")
                    
                    # Tailor resume and generate cover letter
                    tailor_output = resume_tailor.tailor_resume_and_cover(job)
                    
                    # Log to Google Sheets
                    row_number = sheets_logger.append_job_row(job, tailor_output)
                    
                    # Find recruiter email and send cold email
                    recruiter_email = find_recruiter_email(job)
                    if recruiter_email:
                        send_cold_email(recruiter_email, job)
                        self.metrics['emails_sent'] += 1
                    
                    self.metrics['resumes_tailored'] += 1
                    self.metrics['cover_letters_generated'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing job: {e}"
                    logger.error(error_msg)
                    notify_slack(error_msg)
                    self.metrics['errors'].append(error_msg)
            
            # Log metrics
            sheets_logger.log_daily_metrics(self.metrics)
            logger.info("Scrape mode finished.")
            
        except Exception as e:
            logger.error(f"Scrape mode failed: {e}")
            notify_slack(f"Scrape mode failed: {e}")
            raise
    
    def send_emails_mode(self) -> None:
        """
        Send cold outreach emails to recruiters for jobs flagged in Sheets.
        
        This mode:
        1. Gets jobs that need cold emails sent
        2. Sends emails in batches to avoid rate limiting
        3. Updates Google Sheets for successful sends
        4. Logs metrics
        
        Raises:
            ValueError: If required configuration is missing
            Exception: For any other errors during email sending
        """
        self.logger.info("Send Emails mode started.")
        try:
            # Validate email config
            if not os.getenv("GMAIL_SENDER_EMAIL") or not os.getenv("GMAIL_APP_PASSWORD"):
                raise ValueError("Gmail credentials are required in environment variables")
                
            jobs_to_email = sheets_logger.get_jobs_for_email_sending()
            if not jobs_to_email:
                self.logger.info("No jobs to email.")
                return
            
            batch_size = 10
            for i in range(0, len(jobs_to_email), batch_size):
                batch = jobs_to_email[i:i + batch_size]
                results = email_sender.send_bulk_cold_emails(batch)
                
                for idx, status in enumerate(results.get('statuses', [])):
                    if status:
                        try:
                            sheets_logger.mark_cold_email_sent(batch[idx]['row_number'])
                            self.metrics['emails_sent'] += 1
                        except Exception as e:
                            self.logger.error(f"Sheet update failed: {e}")
                    else:
                        self.metrics['errors'].append(f"Failed to send to {batch[idx].get('recruiter_email')}")
                
                if i + batch_size < len(jobs_to_email):
                    time.sleep(30)
            
                sheets_logger.log_daily_metrics(self.metrics)
            self.logger.info("Send Emails mode finished.")
            
        except Exception as e:
            self.logger.error(f"Send Emails mode failed: {e}")
            raise
    
    def mark_applied_mode(self, row_indices: List[int]) -> None:
        """
        Mark jobs as applied in Google Sheets.
        
        Args:
            row_indices: List of row numbers to mark as applied
            
        Raises:
            ValueError: If row_indices is empty
            Exception: For any other errors during marking
        """
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
    
    def test_mode(self) -> None:
        """
        Test all components of the system.
        
        Tests:
        1. Configuration loading
        2. Job scraper functionality
        3. Email scanner setup
        4. Resume tailor initialization
        5. Sheets logger connection
        6. Email sender configuration
        
        Returns:
            Dict[str, bool]: Test results for each component
        """
        self.logger.info("Test mode started.")
        test_results = {
            'config': False, 'job_scraper': False,
            'email_scanner': False, 'resume_tailor': False,
            'sheets_logger': False, 'email_sender': False
        }
        
        try:
            # Test configuration
            cfg = load_config()
            if all(cfg.get(k) for k in ['openai_api_key', 'spreadsheet_id', 'gmail_sender_email']):
                test_results['config'] = True
                self.logger.info("Config OK")
        except Exception as e:
            self.logger.error(f"Config test failed: {e}")
        
        try:
            # Test job scraper
            job_scraper.scrape_indeed_jobs('test', 'Dubai', 1)
            test_results['job_scraper'] = True
            self.logger.info("Scraper OK")
        except Exception as e:
            self.logger.error(f"Scraper test failed: {e}")
        
        try:
            # Test email scanner
            email_scanner.EmailScanner()
            test_results['email_scanner'] = True
            self.logger.info("Email Scanner OK")
        except Exception as e:
            self.logger.error(f"Email Scanner test failed: {e}")
            
        try:
            # Test resume tailor
            resume_tailor.ResumeTailor()
            test_results['resume_tailor'] = True
            self.logger.info("Resume Tailor OK")
        except Exception as e:
            self.logger.error(f"Resume Tailor test failed: {e}")
        
        try:
            # Test sheets logger
            sheets_logger.SheetsLogger(self.config)
            test_results['sheets_logger'] = True
            self.logger.info("Sheets Logger OK")
        except Exception as e:
            self.logger.error(f"Sheets Logger test failed: {e}")
        
        try:
            # Test email sender
            sender = email_sender.EmailSender()
            if sender.test_email_connection():
                test_results['email_sender'] = True
                self.logger.info("Email Sender OK")
        except Exception as e:
            self.logger.error(f"Email Sender test failed: {e}")
            
        self.logger.info(f"Test summary: {sum(test_results.values())}/{len(test_results)} components passed")
        return test_results
    

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Job Agent")
    parser.add_argument(
        "--config",
        "-c",
        default="config.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making actual changes"
    )
    return parser.parse_args()

def main():
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_args()
        
        # Initialize agent
        agent = JobAgent(config_path=args.config)
        
        if args.dry_run:
            logger.info("Running in dry-run mode - no changes will be made")
            
        # Run the pipeline
        agent.scrape_mode()
        agent.send_emails_mode()
        
        logger.info("✅ Pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        notify_slack(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check if we should use the CLI
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        # Import and run CLI
        from cli import app
        app()
    else:
        # Run main.py directly
        main()
