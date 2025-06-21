"""
Job source implementations for various job boards.
Each source implements its own scraping logic while following a common interface.
"""

import os
import asyncio
import random
import time
import logging
import json
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus, urljoin
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent
from datetime import datetime

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

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
]

class BaseJobSource:
    """Base class for all job sources."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        self.min_salary = config.get('salary', {}).get('min_salary', {}).get('amount', 0)
        self.salary_currency = config.get('salary', {}).get('min_salary', {}).get('currency', 'AED')
        self.proxies = config.get('proxies', [])
        self.current_proxy_index = 0
        
    async def init_browser(self) -> None:
        """Initialize browser for scraping."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
    async def rotate_proxy(self) -> None:
        """Rotate to the next proxy in the list."""
        if not self.proxies:
            return
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_index]
        self.logger.info(f"Rotating to proxy: {proxy}")
        await self.context.route("**/*", lambda route: route.continue_(proxy=proxy))
            
    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def scrape_jobs(
        self,
        keywords: List[str],
        locations: List[str],
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from this source."""
        raise NotImplementedError("Subclasses must implement scrape_jobs")
        
    def deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on URL."""
        unique_jobs = []
        seen_urls = set()
        
        for job in jobs:
            job_url = job.get('job_url', '')
            if job_url and job_url not in seen_urls:
                unique_jobs.append(job)
                seen_urls.add(job_url)
                
        return unique_jobs
        
    def meets_salary_requirement(self, salary_text: str) -> bool:
        """Check if job meets minimum salary requirement."""
        if not salary_text or not self.min_salary:
            return True  # If no salary info, include the job
            
        try:
            # Extract numeric value from salary text
            import re
            numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', salary_text)
            if not numbers:
                return True
                
            # Convert to float, handling different formats
            salary = float(numbers[0].replace(',', ''))
            
            # Handle different currencies and units (per year, per month, etc.)
            if 'k' in salary_text.lower() or 'thousand' in salary_text.lower():
                salary *= 1000
            if 'm' in salary_text.lower() or 'million' in salary_text.lower():
                salary *= 1000000
                
            # Convert to monthly if annual
            if 'year' in salary_text.lower() or 'annual' in salary_text.lower():
                salary /= 12
                
            # Convert to AED if needed
            if self.salary_currency != 'AED':
                # TODO: Implement currency conversion using fixer.io
                pass
                
            return salary >= self.min_salary
            
        except Exception as e:
            self.logger.warning(f"Error parsing salary {salary_text}: {e}")
            return True  # Include job if salary parsing fails

class LinkedInSource(BaseJobSource):
    """LinkedIn job source implementation."""
    
    async def login(self) -> bool:
        """Handle LinkedIn login with retries and better error handling."""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"LinkedIn login attempt {attempt + 1}/{max_retries}")
                
                # Navigate to login page with increased timeout
                await self.page.goto('https://www.linkedin.com/login', timeout=60000)
                
                # Wait for the login form with increased timeout
                await self.page.wait_for_selector('#username', timeout=60000)
                await self.page.wait_for_selector('#password', timeout=60000)
                
                # Clear fields and type credentials
                await self.page.fill('#username', '')
                await self.page.fill('#password', '')
                
                # Type credentials with human-like delays
                await self.page.type('#username', self.config['credentials']['linkedin']['email'], delay=100)
                await self.page.type('#password', self.config['credentials']['linkedin']['password'], delay=100)
                
                # Click sign in and wait for navigation
                await self.page.click('button[type="submit"]')
                
                # Wait for navigation with increased timeout
                await self.page.wait_for_load_state('networkidle', timeout=60000)
                
                # Check for success indicators
                success_indicators = [
                    'feed-identity-module',
                    'global-nav',
                    'search-global-typeahead',
                    'messaging-nav-item',
                    'notifications-nav-item'
                ]
                
                for indicator in success_indicators:
                    try:
                        await self.page.wait_for_selector(f'[data-test-id="{indicator}"]', timeout=10000)
                        self.logger.info(f"LinkedIn login successful - found indicator: {indicator}")
                        return True
                    except Exception as e:
                        self.logger.debug(f"Indicator {indicator} not found: {e}")
                        continue
                
                # If we get here, no success indicators were found
                self.logger.warning(f"Login attempt {attempt + 1} failed - no success indicators found")
                
                # Check for error messages
                error_selectors = [
                    '#error-for-username',
                    '#error-for-password',
                    '.alert-error',
                    '.form__error--text'
                ]
                
                for selector in error_selectors:
                    try:
                        error_element = await self.page.query_selector(selector)
                        if error_element:
                            error_text = await error_element.inner_text()
                            self.logger.error(f"Login error: {error_text}")
                    except Exception as e:
                        if "not found" not in str(e):
                            self.logger.error(f"Error checking for error message: {e}")
                
                # Take screenshot for debugging
                await self.page.screenshot(path=f'linkedin_login_error_attempt_{attempt + 1}.png')
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    self.logger.info(f"Waiting {retry_delay} seconds before retrying...")
                    await asyncio.sleep(retry_delay)
                
            except Exception as e:
                self.logger.error(f"Login attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Waiting {retry_delay} seconds before retrying...")
                    await asyncio.sleep(retry_delay)
        
        return False
    
    async def scrape_jobs(
        self,
        keywords: List[str],
        locations: List[str],
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from LinkedIn."""
        await self.init_browser()
        all_jobs = []
        
        # Set a more realistic user agent and headers
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Pragma": "no-cache"
        })

        # Enable stealth mode
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Attempt login
        if not await self.login():
            raise Exception("LinkedIn login failed after all retries")

        # Add a delay after successful login
        await asyncio.sleep(5)

        # Rest of the scraping logic remains the same
        for keyword in keywords:
            for location in locations:
                for page_num in range(max_pages):
                    start = page_num * 25
                    url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keyword)}&location={quote_plus(location)}&start={start}"
                    self.logger.info(f"Scraping LinkedIn page {page_num+1}: {url}")
                    
                    try:
                        # Rotate proxy before each request
                        await self.rotate_proxy()
                        
                        # Add random delay between requests
                        await asyncio.sleep(random.uniform(3, 7))
                        
                        # Navigate with increased timeout and wait for network idle
                        await self.page.goto(url, timeout=90000, wait_until='networkidle')
                        
                        # Check for anti-bot protection
                        content = await self.page.content()
                        if any(text in content.lower() for text in ["captcha", "security check", "unusual traffic", "verify you're a human"]):
                            self.logger.warning("Detected anti-bot protection on LinkedIn. Skipping this page.")
                            continue
                            
                        # Try multiple selectors with retries
                        selectors = [
                            '.jobs-search-results__list-item',  # Primary selector
                            '.job-card-container',  # Alternative selector
                            '[data-job-id]',  # Generic job card selector
                            '.job-card',  # Another possible selector
                            '.job-listing'  # Yet another possible selector
                        ]
                        
                        found_cards = False
                        for selector in selectors:
                            try:
                                # Wait for selector with increased timeout
                                await self.page.wait_for_selector(selector, timeout=30000)
                                
                                # Add a small delay after finding the selector
                                await asyncio.sleep(1)
                                
                                job_cards = await self.page.query_selector_all(selector)
                                if job_cards:
                                    found_cards = True
                                    self.logger.info(f"Found {len(job_cards)} job cards using selector: {selector}")
                                    break
                            except Exception as e:
                                self.logger.debug(f"Selector {selector} not found: {e}")
                                continue
                        
                        if not found_cards:
                            self.logger.error("No job cards found with any selector. Page might be blocked.")
                            continue
                            
                        # Extract job details with multiple selector attempts
                        for i, card in enumerate(job_cards):
                            try:
                                # Try multiple selectors for each field
                                title = ''
                                for title_selector in ['h3', '.job-card-list__title', '[data-job-title]', '.job-title']:
                                    title_el = await card.query_selector(title_selector)
                                    if title_el:
                                        title = await title_el.inner_text()
                                        break
                                        
                                company = ''
                                for company_selector in ['.job-card-container__company-name', '.company-name', '[data-company]', '.company']:
                                    company_el = await card.query_selector(company_selector)
                                    if company_el:
                                        company = await company_el.inner_text()
                                        break
                                        
                                location = ''
                                for location_selector in ['.job-card-container__metadata-item', '.location', '[data-location]', '.job-location']:
                                    location_el = await card.query_selector(location_selector)
                                    if location_el:
                                        location = await location_el.inner_text()
                                        break
                                        
                                # Try multiple ways to get the job URL
                                job_url = ''
                                for link_selector in ['a', '[href*="/jobs/view/"]', '.job-card-list__title']:
                                    link_el = await card.query_selector(link_selector)
                                    if link_el:
                                        job_url = await link_el.get_attribute('href')
                                        if job_url:
                                            break
                                
                                if title and company:  # Only add if we have at least title and company
                                    job = {
                                        'title': title.strip(),
                                        'company': company.strip(),
                                        'location': location.strip(),
                                        'url': job_url.strip() if job_url else '',
                                        'source': 'linkedin',
                                        'keyword': keyword,
                                        'scraped_at': datetime.now().isoformat()
                                    }
                                    all_jobs.append(job)
                            except Exception as e:
                                self.logger.error(f"Error extracting LinkedIn job card {i+1}: {e}")
                                continue
                                
                    except Exception as e:
                        self.logger.error(f"Error processing LinkedIn page {page_num+1}: {e}")
                        continue
                        
        self.logger.info(f"Extracted {len(all_jobs)} jobs from LinkedIn.")
        return all_jobs

class IndeedSource(BaseJobSource):
    """Indeed.com job source implementation."""
    
    async def scrape_jobs(
        self,
        keywords: List[str],
        locations: List[str],
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from Indeed.com."""
        await self.init_browser()
        all_jobs = []
        
        # Set a more realistic user agent and headers
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Pragma": "no-cache"
        })

        # Enable stealth mode
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        for keyword in keywords:
            for location in locations:
                for page_num in range(max_pages):
                    start = page_num * 10
                    url = f"https://ae.indeed.com/jobs?q={quote_plus(keyword)}&l={quote_plus(location)}&start={start}"
                    self.logger.info(f"Scraping Indeed page {page_num+1}: {url}")
                    
                    try:
                        # Rotate proxy before each request
                        await self.rotate_proxy()
                        
                        # Add random delay between requests
                        await asyncio.sleep(random.uniform(3, 7))
                        
                        # Navigate with increased timeout and wait for network idle
                        await self.page.goto(url, timeout=90000, wait_until='networkidle')
                        
                        # Check for anti-bot protection
                        content = await self.page.content()
                        if any(text in content.lower() for text in ["captcha", "security check", "unusual traffic", "verify you're a human"]):
                            self.logger.warning("Detected anti-bot protection on Indeed. Skipping this page.")
                            continue
                            
                        # Try multiple selectors with retries
                        selectors = [
                            '.job_seen_beacon',  # Primary selector
                            '.jobsearch-ResultsList',  # Alternative selector
                            '[data-tn-component="organicJob"]',  # Another possible selector
                            '.job_seen_beacon',  # Yet another possible selector
                            '.job_seen_beacon'  # And another
                        ]
                        
                        found_cards = False
                        for selector in selectors:
                            try:
                                # Wait for selector with increased timeout
                                await self.page.wait_for_selector(selector, timeout=30000)
                                
                                # Add a small delay after finding the selector
                                await asyncio.sleep(1)
                                
                                job_cards = await self.page.query_selector_all(selector)
                                if job_cards:
                                    found_cards = True
                                    self.logger.info(f"Found {len(job_cards)} job cards using selector: {selector}")
                                    break
                            except Exception as e:
                                self.logger.debug(f"Selector {selector} not found: {e}")
                                continue
                        
                        if not found_cards:
                            self.logger.error("No job cards found with any selector. Page might be blocked.")
                            continue
                            
                        # Extract job details with multiple selector attempts
                        for i, card in enumerate(job_cards):
                            try:
                                # Try multiple selectors for each field
                                title = ''
                                for title_selector in ['h2', '.jobTitle', '[data-tn-component="organicJob"] h2']:
                                    title_el = await card.query_selector(title_selector)
                                    if title_el:
                                        title = await title_el.inner_text()
                                        break
                                        
                                company = ''
                                for company_selector in ['.companyName', '.company', '[data-tn-component="organicJob"] .company']:
                                    company_el = await card.query_selector(company_selector)
                                    if company_el:
                                        company = await company_el.inner_text()
                                        break
                                        
                                location = ''
                                for location_selector in ['.companyLocation', '.location', '[data-tn-component="organicJob"] .location']:
                                    location_el = await card.query_selector(location_selector)
                                    if location_el:
                                        location = await location_el.inner_text()
                                        break
                                        
                                # Try multiple ways to get the job URL
                                job_url = ''
                                for link_selector in ['a', '[href*="/viewjob"]', '.job_link']:
                                    link_el = await card.query_selector(link_selector)
                                    if link_el:
                                        job_url = await link_el.get_attribute('href')
                                        if job_url:
                                            break
                                
                                if title and company:  # Only add if we have at least title and company
                                    job = {
                                        'title': title.strip(),
                                        'company': company.strip(),
                                        'location': location.strip(),
                                        'url': f'https://ae.indeed.com{job_url.strip()}' if job_url else '',
                                        'source': 'indeed',
                                        'keyword': keyword,
                                        'scraped_at': datetime.now().isoformat()
                                    }
                                    all_jobs.append(job)
                            except Exception as e:
                                self.logger.error(f"Error extracting Indeed job card {i+1}: {e}")
                                continue
                                
                    except Exception as e:
                        self.logger.error(f"Error processing Indeed page {page_num+1}: {e}")
                        continue
                        
        self.logger.info(f"Extracted {len(all_jobs)} jobs from Indeed.")
        return all_jobs

class BaytSource(BaseJobSource):
    """Bayt.com job source implementation."""
    
    async def scrape_jobs(
        self,
        keywords: List[str],
        locations: List[str],
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from Bayt.com."""
        await self.init_browser()
        all_jobs = []
        
        # Set a more realistic user agent and headers
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Pragma": "no-cache"
        })

        # Enable stealth mode
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        for keyword in keywords:
            for location in locations:
                for page_num in range(max_pages):
                    url = f"https://www.bayt.com/en/uae/jobs/{quote_plus(keyword)}-jobs-in-{quote_plus(location)}/?page={page_num+1}"
                    self.logger.info(f"Scraping Bayt page {page_num+1}: {url}")
                    
                    try:
                        # Rotate proxy before each request
                        await self.rotate_proxy()
                        
                        # Add random delay between requests
                        await asyncio.sleep(random.uniform(3, 7))
                        
                        # Navigate with increased timeout and wait for network idle
                        await self.page.goto(url, timeout=90000, wait_until='networkidle')
                        
                        # Check for anti-bot protection
                        content = await self.page.content()
                        if any(text in content.lower() for text in ["just a moment", "checking your browser", "cloudflare", "security check"]):
                            self.logger.warning("Detected anti-bot protection on Bayt. Skipping this page.")
                            continue
                            
                        # Try multiple selectors with retries
                        selectors = [
                            '.has-pointer-d',  # Primary selector
                            '.job-card',       # Alternative selector
                            '[data-job-id]',   # Generic job card selector
                            '.job-listing',    # Another possible selector
                            '.job-box'         # Yet another possible selector
                        ]
                        
                        found_cards = False
                        for selector in selectors:
                            try:
                                # Wait for selector with increased timeout
                                await self.page.wait_for_selector(selector, timeout=30000)
                                
                                # Add a small delay after finding the selector
                                await asyncio.sleep(1)
                                
                                job_cards = await self.page.query_selector_all(selector)
                                if job_cards:
                                    found_cards = True
                                    self.logger.info(f"Found {len(job_cards)} job cards using selector: {selector}")
                                    break
                            except Exception as e:
                                self.logger.debug(f"Selector {selector} not found: {e}")
                                continue
                        
                        if not found_cards:
                            self.logger.error("No job cards found with any selector. Page might be blocked.")
                            continue
                            
                        # Extract job details with multiple selector attempts
                        for i, card in enumerate(job_cards):
                            try:
                                # Try multiple selectors for each field
                                title = ''
                                for title_selector in ['h2', '.job-title', '[data-job-title]', '.job-title-text']:
                                    title_el = await card.query_selector(title_selector)
                                    if title_el:
                                        title = await title_el.inner_text()
                                        break
                                        
                                company = ''
                                for company_selector in ['.jb-company', '.company-name', '[data-company]', '.company-text']:
                                    company_el = await card.query_selector(company_selector)
                                    if company_el:
                                        company = await company_el.inner_text()
                                        break
                                        
                                location = ''
                                for location_selector in ['.jb-loc', '.location', '[data-location]', '.location-text']:
                                    location_el = await card.query_selector(location_selector)
                                    if location_el:
                                        location = await location_el.inner_text()
                                        break
                                        
                                # Try multiple ways to get the job URL
                                job_url = ''
                                for link_selector in ['a', '[href*="/job/"]', '.job-link']:
                                    link_el = await card.query_selector(link_selector)
                                    if link_el:
                                        job_url = await link_el.get_attribute('href')
                                        if job_url:
                                            break
                                
                                if title and company:  # Only add if we have at least title and company
                                    job = {
                                        'title': title.strip(),
                                        'company': company.strip(),
                                        'location': location.strip(),
                                        'url': job_url.strip() if job_url else '',
                                        'source': 'bayt',
                                        'keyword': keyword,
                                        'scraped_at': datetime.now().isoformat()
                                    }
                                    all_jobs.append(job)
                            except Exception as e:
                                self.logger.error(f"Error extracting Bayt job card {i+1}: {e}")
                                continue
                                
                    except Exception as e:
                        self.logger.error(f"Error processing Bayt page {page_num+1}: {e}")
                        continue
                        
        self.logger.info(f"Extracted {len(all_jobs)} jobs from Bayt.")
        return all_jobs

# Factory function to get job source instance
def get_job_source(source_name: str, config: Dict[str, Any]) -> BaseJobSource:
    """Get job source instance by name."""
    sources = {
        'linkedin': LinkedInSource,
        'indeed': IndeedSource,
        'bayt': BaytSource
    }
    
    source_class = sources.get(source_name.lower())
    if not source_class:
        raise ValueError(f"Unsupported job source: {source_name}")
        
    return source_class(config) 