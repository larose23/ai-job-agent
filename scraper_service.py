"""
Job scraping service module that provides a unified interface for scraping jobs from multiple sources.
Handles scraping from LinkedIn and Indeed, with proper error handling, logging, and retry logic.
"""

import os
import asyncio
import random
import time
import logging
import json
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus, urljoin
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent
from datetime import datetime, timedelta

from helpers import (
    load_config,
    retry_network,
    retry_auth,
    safe_operation,
    random_delay,
    logger,
    notify_slack
)

load_dotenv()

# Common desktop browser User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]

def is_cookie_file_stale(filepath: str, max_age_days: int = 7) -> bool:
    """
    Check if a cookie file is stale (doesn't exist or older than max_age_days).
    
    Args:
        filepath: Path to cookie file
        max_age_days: Maximum age in days before file is considered stale
        
    Returns:
        bool: True if file is stale or doesn't exist
    """
    if not os.path.exists(filepath):
        return True
    mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
    return datetime.now() - mod_time > timedelta(days=max_age_days)

class JobScraper:
    """Job scraping service for multiple platforms."""
    
    def __init__(self, headful: bool = False, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the job scraper.
        
        Args:
            headful (bool): Whether to run browser in headful mode
            config (Dict[str, Any]): Configuration dictionary containing search parameters
        """
        self.headful = headful
        self.config = config or {}
        self.browser = None
        self.page = None
        self.logger = logging.getLogger(__name__)
        self.playwright = None
        self.context = None
        self.seen_jobs = set()
        
    def is_remote_job(self, title: str, location: str, description: str = "") -> bool:
        """
        Check if a job is remote based on title, location, and description.
        
        Args:
            title (str): Job title
            location (str): Job location
            description (str): Job description
            
        Returns:
            bool: True if job is remote, False otherwise
        """
        remote_indicators = [
            "remote",
            "work from home",
            "wfh",
            "virtual",
            "telecommute",
            "anywhere",
            "distributed"
        ]
        
        text_to_check = f"{title} {location} {description}".lower()
        return any(indicator in text_to_check for indicator in remote_indicators)
        
    def should_include_job(self, job_location: str, is_remote: bool) -> bool:
        """
        Determine if a job should be included based on location and remote status.
        
        Args:
            job_location (str): Job location
            is_remote (bool): Whether the job is remote
            
        Returns:
            bool: True if job should be included, False otherwise
        """
        # If location is in remote_only list, only include remote jobs
        if job_location in self.config.get('remote_only', []):
            return is_remote
        # Otherwise include all jobs
        return True

    async def save_cookies(self, platform: str) -> None:
        """
        Save browser cookies to a file.
        
        Args:
            platform: Platform name (linkedin, indeed, or glassdoor)
        """
        try:
            cookie_file = f"{platform}_cookies.json"
            cookies = await self.context.cookies()
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
            self.logger.info(f"Saved {len(cookies)} cookies to {cookie_file}")
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {str(e)}")
            raise

    async def load_cookies(self, platform: str) -> bool:
        """
        Load cookies from file and add them to browser context.
        
        Args:
            platform: Platform name (linkedin, indeed, or glassdoor)
            
        Returns:
            bool: True if cookies were loaded successfully, False otherwise
        """
        try:
            cookie_file = f"{platform}_cookies.json"
            
            # Check if cookie file is stale
            if is_cookie_file_stale(cookie_file):
                self.logger.info(f"Cookie file {cookie_file} is stale or doesn't exist")
                return False
                
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
                
            if not cookies:
                self.logger.info(f"Cookie file {cookie_file} is empty")
                return False
                
            await self.context.add_cookies(cookies)
            self.logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {str(e)}")
            return False

    async def verify_login(self, platform: str) -> bool:
        """
        Verify login status for a platform.
        
        Args:
            platform: Platform name (linkedin, indeed, or glassdoor)
            
        Returns:
            bool: True if login is verified, False otherwise
        """
        try:
            if platform == 'linkedin':
                await self.page.goto('https://www.linkedin.com/feed/', wait_until='networkidle')
                return bool(await self.page.query_selector('.feed-identity-module'))
            elif platform == 'indeed':
                await self.page.goto('https://www.indeed.com/myjobs', wait_until='networkidle')
                return bool(await self.page.query_selector('.jobsearch-Header'))
            elif platform == 'glassdoor':
                await self.page.goto('https://www.glassdoor.com/profile/my_profile.htm', wait_until='networkidle')
                return bool(await self.page.query_selector('.profile-header'))
            return False
        except Exception as e:
            self.logger.error(f"Failed to verify login for {platform}: {str(e)}")
            return False

    async def init_browser(self) -> None:
        """
        Initialize the browser with appropriate settings and load cookies if available.
        """
        try:
            self.logger.info("Initializing browser...")
            self.playwright = await async_playwright().start()
            
            # Launch browser with headful mode if specified
            self.browser = await self.playwright.chromium.launch(
                headless=not self.headful,
                args=['--no-sandbox']
            )
            
            # Create context with viewport and user agent
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(USER_AGENTS)
            )
            
            # Set timeouts for page operations
            self.page = await self.context.new_page()
            await self.page.set_default_timeout(90000)  # 90 seconds
            await self.page.set_default_navigation_timeout(90000)  # 90 seconds
            
            self.logger.info("Browser initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize browser: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception)),
        reraise=True
    )
    async def login_to_linkedin(self) -> None:
        """
        Log in to LinkedIn using credentials from environment variables.
        Implements retry logic with exponential backoff and CAPTCHA detection.
        """
        try:
            # Initialize browser if not already initialized
            if self.browser is None:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=not self.headful,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )

            # Initialize page if not already initialized
            if self.page is None:
                self.page = await self.browser.new_page()
                await self.page.set_viewport_size({"width": 1920, "height": 1080})

            # Try to load cookies first
            if await self.load_cookies('linkedin'):
                if await self.verify_login('linkedin'):
                    self.logger.info("Successfully logged in to LinkedIn using cookies")
                    return
                else:
                    self.logger.warning("LinkedIn cookies loaded but login verification failed")
            
            # If cookies failed or don't exist, perform normal login
            self.logger.info("Performing fresh LinkedIn login...")
            
            # Navigate to login page with random delay
            self.logger.info("Opening LinkedIn login page...")
            await self.page.goto('https://www.linkedin.com/login', wait_until='networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Check for CAPTCHA before attempting login
            captcha_present = await self.page.query_selector('iframe[title*="captcha"]')
            if captcha_present:
                self.logger.error("CAPTCHA detected! Consider using headful mode or pre-auth cookies")
                await self.page.screenshot(path='linkedin_captcha.png')
                raise Exception("CAPTCHA detected during login")
            
            # Fill in credentials with human-like delays
            self.logger.info("LinkedIn page loaded. Filling in credentials...")
            
            # Type email with random delays between characters
            email = os.getenv('LINKEDIN_EMAIL')
            await self.page.fill('#username', '')  # Clear first
            for char in email:
                await self.page.type('#username', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Type password with random delays between characters
            password = os.getenv('LINKEDIN_PASSWORD')
            await self.page.fill('#password', '')  # Clear first
            for char in password:
                await self.page.type('#password', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Random delay before clicking
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Click login button
            self.logger.info("Credentials filled. Submitting login form...")
            await self.page.click('button[type="submit"]')
            
            # Wait for either success, failure, or CAPTCHA
            try:
                # First check for error messages
                error_selectors = [
                    '#error-for-username',
                    '#error-for-password',
                    '.alert-error',
                    '.form__error'
                ]
                
                for selector in error_selectors:
                    error_element = await self.page.query_selector(selector)
                    if error_element:
                        error_text = await error_element.text_content()
                        self.logger.error(f"Login failed: {error_text}")
                        await self.page.screenshot(path='linkedin_login_error.png')
                        raise Exception(f"Login failed: {error_text}")
                
                # Check for CAPTCHA after login attempt
                captcha_present = await self.page.query_selector('iframe[title*="captcha"]')
                if captcha_present:
                    self.logger.error("CAPTCHA detected after login attempt!")
                    await self.page.screenshot(path='linkedin_captcha_after_login.png')
                    raise Exception("CAPTCHA detected after login attempt")
                
                # Wait for successful login using multiple possible selectors
                self.logger.info("Login submitted. Waiting for dashboard selector...")
                selectors = [
                    '.feed-identity-module',  # Main feed
                    '.global-nav__me-photo',  # Profile photo
                    '.global-nav__me-menu',   # Profile menu
                    '.search-global-typeahead',  # Search bar
                    '.global-nav__primary-items'  # Main navigation
                ]
                
                for selector in selectors:
                    try:
                        await self.page.wait_for_selector(selector, timeout=60000)
                        self.logger.info(f"Login confirmed by selector: {selector}")
                        break
                    except PlaywrightTimeoutError as e:
                        self.logger.error(f"LinkedIn login failed at selector {selector}: {str(e)}")
                        continue
                else:
                    # If we get here, no selectors were found
                    # Log the page content for debugging
                    page_content = await self.page.content()
                    self.logger.error(f"Login page content: {page_content}")
                    await self.page.screenshot(path='linkedin_login_failed.png')
                    raise PlaywrightTimeoutError("No login confirmation selectors found")
                
                # Additional verification - check if we're on the feed page
                current_url = self.page.url
                if 'feed' not in current_url and 'checkpoint' not in current_url:
                    self.logger.warning(f"Unexpected URL after login: {current_url}")
                    await self.page.screenshot(path='linkedin_unexpected_url.png')
                
                self.logger.info("Successfully logged in to LinkedIn")
                
                # Save cookies after successful login
                await self.save_cookies('linkedin')
                
            except PlaywrightTimeoutError as e:
                error_msg = f"Login verification failed: {str(e)}"
                self.logger.error(error_msg)
                # Take screenshot and log page content for debugging
                await self.page.screenshot(path='linkedin_login_error.png')
                page_content = await self.page.content()
                self.logger.error(f"Login page content: {page_content}")
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"LinkedIn login failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    async def login_to_indeed(self) -> None:
        """
        Log in to Indeed using credentials from environment variables.
        """
        try:
            # Try to load cookies first
            if await self.load_cookies('indeed'):
                if await self.verify_login('indeed'):
                    self.logger.info("Successfully logged in to Indeed using cookies")
                    return
                else:
                    self.logger.warning("Indeed cookies loaded but login verification failed")
            
            # If cookies failed or don't exist, perform normal login
            self.logger.info("Performing fresh Indeed login...")
            
            # Navigate to login page
            await self.page.goto('https://www.indeed.com/account/login', wait_until='networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Fill in credentials with human-like delays
            email = os.getenv('INDEED_EMAIL')
            password = os.getenv('INDEED_PASSWORD')
            
            # Type email
            await self.page.fill('#ifl-InputFormField-3', '')
            for char in email:
                await self.page.type('#ifl-InputFormField-3', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Type password
            await self.page.fill('#ifl-InputFormField-4', '')
            for char in password:
                await self.page.type('#ifl-InputFormField-4', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Click login button
            await self.page.click('button[type="submit"]')
            
            # Wait for successful login
            await self.page.wait_for_selector('.jobsearch-Header', timeout=60000)
            
            # Save cookies after successful login
            await self.save_cookies('indeed')
            
        except Exception as e:
            error_msg = f"Indeed login failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    async def login_to_glassdoor(self) -> None:
        """
        Log in to Glassdoor using credentials from environment variables.
        """
        try:
            # Try to load cookies first
            if await self.load_cookies('glassdoor'):
                if await self.verify_login('glassdoor'):
                    self.logger.info("Successfully logged in to Glassdoor using cookies")
                    return
                else:
                    self.logger.warning("Glassdoor cookies loaded but login verification failed")
            
            # If cookies failed or don't exist, perform normal login
            self.logger.info("Performing fresh Glassdoor login...")
            
            # Navigate to login page
            await self.page.goto('https://www.glassdoor.com/profile/login_input.htm', wait_until='networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Fill in credentials with human-like delays
            email = os.getenv('GLASSDOOR_EMAIL')
            password = os.getenv('GLASSDOOR_PASSWORD')
            
            # Type email
            await self.page.fill('#userEmail', '')
            for char in email:
                await self.page.type('#userEmail', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Type password
            await self.page.fill('#userPassword', '')
            for char in password:
                await self.page.type('#userPassword', char, delay=random.uniform(50, 150))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Click login button
            await self.page.click('button[type="submit"]')
            
            # Wait for successful login
            await self.page.wait_for_selector('.profile-header', timeout=60000)
            
            # Save cookies after successful login
            await self.save_cookies('glassdoor')
            
        except Exception as e:
            error_msg = f"Glassdoor login failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.logger.error(f"Error closing browser: {str(e)}")

    async def get_jobs(self, keywords: List[str], locations: List[Dict[str, Any]], max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Get jobs from multiple platforms.
        
        Args:
            keywords: List of job keywords to search for
            locations: List of location dictionaries
            max_pages: Maximum number of pages to scrape per search
            
        Returns:
            List of job dictionaries
        """
        try:
            await self.init_browser()
            
            all_jobs = []
            
            # Scrape from each platform
            for platform in ['linkedin', 'indeed', 'glassdoor']:
                try:
                    if platform == 'linkedin':
                        await self.login_to_linkedin()
                        jobs = await self.scrape_linkedin_jobs(keywords, locations, max_pages)
                    elif platform == 'indeed':
                        await self.login_to_indeed()
                        jobs = await self.scrape_indeed_jobs(keywords, locations, max_pages)
                    elif platform == 'glassdoor':
                        await self.login_to_glassdoor()
                        jobs = await self.scrape_glassdoor_jobs(keywords, locations, max_pages)
                    
                    all_jobs.extend(jobs)
                    
                except Exception as e:
                    self.logger.error(f"Error scraping {platform}: {str(e)}")
                    continue
            
            return all_jobs
            
        finally:
            await self.close()

    def deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate jobs based on URL or job hash.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Deduplicated list of jobs
        """
        unique_jobs = []
        seen_urls = set()
        
        for job in jobs:
            job_url = job.get('job_url', '')
            if job_url not in seen_urls:
                unique_jobs.append(job)
                seen_urls.add(job_url)
                
        self.logger.info(f"Deduplicated {len(jobs)} jobs to {len(unique_jobs)} unique jobs")
        return unique_jobs

    async def scrape_linkedin_jobs(self, keywords: List[str], locations: List[str], max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape jobs from LinkedIn.
        
        Args:
            keywords (List[str]): List of job keywords to search for
            locations (List[str]): List of locations to search in
            max_pages (int): Maximum number of pages to scrape per search
            
        Returns:
            List[Dict[str, Any]]: List of job listings
        """
        try:
            # Login to LinkedIn
            await self.login_to_linkedin()
            
            all_jobs = []
            for keyword in keywords:
                for location in locations:
                    # Construct search URL with remote filter if needed
                    search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}"
                    if location in self.config.get('remote_only', []):
                        search_url += "&f_WT=2"  # Add remote filter for LinkedIn
                    
                    self.logger.info(f"Searching LinkedIn for: {keyword} in {location}")
                    await self.page.goto(search_url)
                    
                    # Scrape jobs from each page
                    for page in range(max_pages):
                        # Wait for job cards to load
                        await self.page.wait_for_selector('.job-card-container')
                        
                        # Get all job cards on the page
                        job_cards = await self.page.query_selector_all('.job-card-container')
                        
                        for card in job_cards:
                            try:
                                # Extract job details
                                title = await card.query_selector('.job-card-list__title')
                                company = await card.query_selector('.job-card-container__company-name')
                                location_elem = await card.query_selector('.job-card-container__metadata-item')
                                description = await card.query_selector('.job-card-container__description')
                                
                                title_text = await title.text_content() if title else "N/A"
                                company_text = await company.text_content() if company else "N/A"
                                location_text = await location_elem.text_content() if location_elem else "N/A"
                                description_text = await description.text_content() if description else ""
                                
                                # Check if job is remote
                                is_remote = self.is_remote_job(title_text, location_text, description_text)
                                
                                # Skip job if it doesn't meet remote requirements
                                if not self.should_include_job(location, is_remote):
                                    continue
                                
                                # Get job URL
                                job_link = await card.query_selector('a.job-card-list__title')
                                job_url = await job_link.get_attribute('href') if job_link else None
                                
                                if job_url:
                                    job = {
                                        'title': title_text.strip(),
                                        'company': company_text.strip(),
                                        'location': location_text.strip(),
                                        'url': job_url,
                                        'source': 'LinkedIn',
                                        'is_remote': is_remote
                                    }
                                    all_jobs.append(job)
                                    
                            except Exception as e:
                                self.logger.error(f"Error scraping job card: {str(e)}")
                                continue
                        
                        # Click next page if available
                        next_button = await self.page.query_selector('button[aria-label="Next"]')
                        if not next_button or page == max_pages - 1:
                            break
                        await next_button.click()
                        await self.page.wait_for_load_state('networkidle')
            
            return all_jobs
            
        except Exception as e:
            error_msg = f"LinkedIn scraping failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    async def scrape_indeed_jobs(self, keywords: List[str], locations: List[str], max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape jobs from Indeed.
        
        Args:
            keywords (List[str]): List of job keywords to search for
            locations (List[str]): List of locations to search in
            max_pages (int): Maximum number of pages to scrape per search
            
        Returns:
            List[Dict[str, Any]]: List of job listings
        """
        try:
            # Login to Indeed
            await self.login_to_indeed()
            
            all_jobs = []
            for keyword in keywords:
                for location in locations:
                    # Construct search URL with remote filter if needed
                    search_url = f"https://www.indeed.com/jobs?q={keyword}&l={location}"
                    if location in self.config.get('remote_only', []):
                        search_url += "&sc=0kf%3Aattr(FSFW)%3B"  # Add remote filter for Indeed
                    
                    self.logger.info(f"Searching Indeed for: {keyword} in {location}")
                    await self.page.goto(search_url)
                    
                    # Scrape jobs from each page
                    for page in range(max_pages):
                        # Wait for job cards to load
                        await self.page.wait_for_selector('.job_seen_beacon')
                        
                        # Get all job cards on the page
                        job_cards = await self.page.query_selector_all('.job_seen_beacon')
                        
                        for card in job_cards:
                            try:
                                # Extract job details
                                title = await card.query_selector('.jobTitle')
                                company = await card.query_selector('.companyName')
                                location_elem = await card.query_selector('.companyLocation')
                                description = await card.query_selector('.job-snippet')
                                
                                title_text = await title.text_content() if title else "N/A"
                                company_text = await company.text_content() if company else "N/A"
                                location_text = await location_elem.text_content() if location_elem else "N/A"
                                description_text = await description.text_content() if description else ""
                                
                                # Check if job is remote
                                is_remote = self.is_remote_job(title_text, location_text, description_text)
                                
                                # Skip job if it doesn't meet remote requirements
                                if not self.should_include_job(location, is_remote):
                                    continue
                                
                                # Get job URL
                                job_link = await card.query_selector('a.jcs-JobTitle')
                                job_url = await job_link.get_attribute('href') if job_link else None
                                if job_url and not job_url.startswith('http'):
                                    job_url = f"https://www.indeed.com{job_url}"
                                
                                if job_url:
                                    job = {
                                        'title': title_text.strip(),
                                        'company': company_text.strip(),
                                        'location': location_text.strip(),
                                        'url': job_url,
                                        'source': 'Indeed',
                                        'is_remote': is_remote
                                    }
                                    all_jobs.append(job)
                                    
                            except Exception as e:
                                self.logger.error(f"Error scraping job card: {str(e)}")
                                continue
                        
                        # Click next page if available
                        next_button = await self.page.query_selector('a[data-testid="pagination-page-next"]')
                        if not next_button or page == max_pages - 1:
                            break
                        await next_button.click()
                        await self.page.wait_for_load_state('networkidle')
            
            return all_jobs
            
        except Exception as e:
            error_msg = f"Indeed scraping failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

    async def scrape_glassdoor_jobs(self, keywords: List[str], locations: List[str], max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape jobs from Glassdoor.
        
        Args:
            keywords (List[str]): List of job keywords to search for
            locations (List[str]): List of locations to search in
            max_pages (int): Maximum number of pages to scrape per search
            
        Returns:
            List[Dict[str, Any]]: List of job listings
        """
        try:
            # Login to Glassdoor
            await self.login_to_glassdoor()
            
            all_jobs = []
            for keyword in keywords:
                for location in locations:
                    # Construct search URL with remote filter if needed
                    search_url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keyword}&loc={location}"
                    if location in self.config.get('remote_only', []):
                        search_url += "&remoteWorkType=1"  # Add remote filter for Glassdoor
                    
                    self.logger.info(f"Searching Glassdoor for: {keyword} in {location}")
                    await self.page.goto(search_url)
                    
                    # Scrape jobs from each page
                    for page in range(max_pages):
                        # Wait for job cards to load
                        await self.page.wait_for_selector('.react-job-listing')
                        
                        # Get all job cards on the page
                        job_cards = await self.page.query_selector_all('.react-job-listing')
                        
                        for card in job_cards:
                            try:
                                # Extract job details
                                title = await card.query_selector('.job-title')
                                company = await card.query_selector('.employer-name')
                                location_elem = await card.query_selector('.location')
                                description = await card.query_selector('.job-description')
                                
                                title_text = await title.text_content() if title else "N/A"
                                company_text = await company.text_content() if company else "N/A"
                                location_text = await location_elem.text_content() if location_elem else "N/A"
                                description_text = await description.text_content() if description else ""
                                
                                # Check if job is remote
                                is_remote = self.is_remote_job(title_text, location_text, description_text)
                                
                                # Skip job if it doesn't meet remote requirements
                                if not self.should_include_job(location, is_remote):
                                    continue
                                
                                # Get job URL
                                job_link = await card.query_selector('a.jobLink')
                                job_url = await job_link.get_attribute('href') if job_link else None
                                if job_url and not job_url.startswith('http'):
                                    job_url = f"https://www.glassdoor.com{job_url}"
                                
                                if job_url:
                                    job = {
                                        'title': title_text.strip(),
                                        'company': company_text.strip(),
                                        'location': location_text.strip(),
                                        'url': job_url,
                                        'source': 'Glassdoor',
                                        'is_remote': is_remote
                                    }
                                    all_jobs.append(job)
                                    
                            except Exception as e:
                                self.logger.error(f"Error scraping job card: {str(e)}")
                                continue
                        
                        # Click next page if available
                        next_button = await self.page.query_selector('button[data-test="pagination-next"]')
                        if not next_button or page == max_pages - 1:
                            break
                        await next_button.click()
                        await self.page.wait_for_load_state('networkidle')
            
            return all_jobs
            
        except Exception as e:
            error_msg = f"Glassdoor scraping failed: {str(e)}"
            self.logger.error(error_msg)
            notify_slack(error_msg)
            raise

async def get_jobs(
    keywords: List[str],
    locations: List[str],
    max_pages: int = 3
) -> List[Dict[str, Any]]:
    """
    Scrape jobs from both LinkedIn and Indeed, combine results, and return a unified list.
    
    Args:
        keywords: List of job keywords to search
        locations: List of locations to search
        max_pages: Maximum number of pages to scrape per search (default: 3)
        
    Returns:
        List of job dictionaries containing:
            - title: Job title
            - company: Company name
            - location: Job location
            - job_url: URL to the job posting
            - salary_text: Salary information text
            - description: Job description
            - source: Source platform ("linkedin" or "indeed")
    """
    print("[DEBUG] get_jobs received keywords:", keywords)
    scraper = JobScraper()
    
    # Scrape from both sources concurrently
    jobs = await scraper.get_jobs(keywords, locations, max_pages)
    
    # Deduplicate jobs
    unique_jobs = scraper.deduplicate_jobs(jobs)
    
    logger.info(f"Total jobs found: {len(unique_jobs)}")
    return unique_jobs
