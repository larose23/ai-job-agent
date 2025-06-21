"""
Job scraping module for the AI Job Agent application.
Handles scraping from LinkedIn (using Playwright) and Indeed (using requests/BeautifulSoup).
"""

import os
import asyncio
import random
import time
import logging
import sys
import requests
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus, urljoin
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from helpers import (
    load_config,
    validate_email,
    sanitize_filename,
    create_directory_if_not_exists
)
from logger import logger, notify_slack

load_dotenv()

class JobScraper:
    """Main job scraper class that handles both LinkedIn and Indeed scraping."""
    
    def __init__(self, config_path: str = "config.json") -> None:
        """
        Initialize the job scraper with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logger
        self.browser = None
        self.page = None
        self.seen_jobs = set()
        
    async def init_browser(self) -> None:
        """Initialize the browser for web scraping."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            notify_slack(f"Browser initialization failed: {e}")
            raise
            
    async def login_to_linkedin(self) -> None:
        """Log in to LinkedIn using credentials from environment variables with robust selector and retry logic."""
        selectors = [
            '.global-nav__me-photo',  # Profile photo
            '.global-nav__me-menu',   # Profile menu
            '.feed-identity-module',  # Feed module
            '.search-global-typeahead',  # Search bar
            '.global-nav__primary-items'  # Main navigation
        ]
        max_retries = 3
        base_timeout = 30000  # 30 seconds
        for attempt in range(max_retries):
            try:
                await self.page.goto('https://www.linkedin.com/login')
                await self.page.fill('#username', os.getenv('LINKEDIN_EMAIL'))
                await self.page.fill('#password', os.getenv('LINKEDIN_PASSWORD'))
                await self.page.click('button[type="submit"]')
                for selector in selectors:
                    try:
                        await self.page.wait_for_selector(selector, timeout=base_timeout + attempt * 10000)
                        logger.info(f"Login successful! Detected by selector: {selector}")
                        return
                    except Exception:
                        continue
                raise Exception("No login success selectors found.")
            except Exception as e:
                logger.error(f"LinkedIn login attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    # Log page content and screenshot for debugging
                    try:
                        content = await self.page.content()
                        logger.error(f"LinkedIn login failed page content: {content[:1000]}")
                        await self.page.screenshot(path=f'linkedin_login_failed_attempt_{attempt+1}.png')
                    except Exception as ex:
                        logger.error(f"Failed to capture LinkedIn login debug info: {ex}")
                await asyncio.sleep(2 * (attempt + 1))
        raise Exception("LinkedIn login failed after retries.")
    
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
    
    def filter_by_salary(self, jobs: List[Dict[str, Any]], min_salary_aed: int) -> List[Dict[str, Any]]:
        """
        Filter jobs by minimum salary requirement.
        
        Args:
            jobs: List of job dictionaries
            min_salary_aed: Minimum salary in AED
            
        Returns:
            Filtered list of jobs
        """
        filtered_jobs = []
        
        for job in jobs:
            salary_text = job.get('salary_text', '')
            if not salary_text:
                # Include jobs without salary info for manual review
                filtered_jobs.append(job)
                continue
                
            salary_amount = parse_salary_text(salary_text)
            if salary_amount and salary_amount >= min_salary_aed:
                filtered_jobs.append(job)
            elif not salary_amount:
                # Include jobs where salary couldn't be parsed
                filtered_jobs.append(job)
                
        self.logger.info(f"Filtered {len(jobs)} jobs to {len(filtered_jobs)} jobs meeting salary criteria")
        return filtered_jobs

    async def scrape_linkedin_jobs(
        self, 
        keywords: List[str], 
        locations: List[str], 
        min_salary_aed: int = 0, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Scrape job postings from LinkedIn using Playwright.
        
        Args:
            keywords: List of job keywords to search
            locations: List of locations to search
            min_salary_aed: Minimum salary in AED
            max_results: Maximum results per query
            
        Returns:
            List of job dictionaries
        """
        self.logger.info("Starting LinkedIn job scraping")
        all_jobs = []
        
        try:
            await self.init_browser()
            await self.login_to_linkedin()
            
            # Search for each keyword-location combination
            for keyword in keywords:
                for location in locations:
                    self.logger.info(f"Searching LinkedIn for '{keyword}' in '{location}'")
                    jobs = await self._search_linkedin_jobs(self.page, keyword, location, max_results)
                    all_jobs.extend(jobs)
                    
                    # Random delay between searches
                    await asyncio.sleep(random.uniform(2, 5))
            
        except Exception as e:
            self.logger.error(f"Error during LinkedIn scraping: {e}")
        finally:
            if self.browser:
                await self.browser.close()
        
        # Filter and deduplicate
        filtered_jobs = self.filter_by_salary(all_jobs, min_salary_aed)
        unique_jobs = self.deduplicate_jobs(filtered_jobs)
        
        self.logger.info(f"LinkedIn scraping completed: {len(unique_jobs)} jobs found")
        return unique_jobs
    
    async def _search_linkedin_jobs(
        self, 
        page: Page, 
        keyword: str, 
        location: str, 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs on LinkedIn with specific keyword and location.
        
        Args:
            page: Playwright page object
            keyword: Job keyword
            location: Job location
            max_results: Maximum results to return
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        try:
            # Navigate to jobs page
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keyword)}&location={quote_plus(location)}"
            await page.goto(search_url)
            await page.wait_for_load_state('networkidle')
            
            # Scroll to load more jobs
            for _ in range(3):  # Scroll 3 times to load more content
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
            
            # Extract job listings
            job_cards = await page.query_selector_all('.job-search-card')
            
            for i, card in enumerate(job_cards[:max_results]):
                try:
                    job_data = await self._extract_linkedin_job_data(page, card)
                    if job_data:
                        jobs.append(job_data)
                        
                except Exception as e:
                    self.logger.warning(f"Error extracting job {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error searching LinkedIn jobs: {e}")
            
        return jobs
    
    async def _extract_linkedin_job_data(self, page: Page, card) -> Optional[Dict[str, Any]]:
        """
        Extract job data from a LinkedIn job card.
        
        Args:
            page: Playwright page object
            card: Job card element
            
        Returns:
            Job data dictionary or None if extraction fails
        """
        try:
            # Click on job card to load details
            await card.click()
            await asyncio.sleep(1)
            
            # Wait for job details to load
            await page.wait_for_selector('.job-details-jobs-unified-top-card')
            
            # Extract job information
            title = await page.query_selector('.job-details-jobs-unified-top-card__job-title')
            company = await page.query_selector('.job-details-jobs-unified-top-card__company-name')
            location = await page.query_selector('.job-details-jobs-unified-top-card__bullet')
            description = await page.query_selector('.job-details-jobs-unified-top-card__job-description')
            
            title_text = await title.text_content() if title else "N/A"
            company_text = await company.text_content() if company else "N/A"
            location_text = await location.text_content() if location else "N/A"
            description_text = await description.text_content() if description else ""
            
            # Get job URL
            job_url = await page.url()
            
            return {
                'title': title_text.strip(),
                'company': company_text.strip(),
                'location': location_text.strip(),
                'job_url': job_url,
                'description': description_text.strip(),
                'source': 'linkedin'
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting job data: {e}")
            return None
    
    def scrape_indeed_jobs(
        self, 
        keywords: str, 
        location: str, 
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Scrape job postings from Indeed with user-agent rotation and random delays.
        """
        self.logger.info(f"Starting Indeed job scraping for '{keywords}' in '{location}'")
        all_jobs = []
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        try:
            for page in range(max_pages):
                headers = {'User-Agent': random.choice(user_agents)}
                # Construct search URL
                search_url = f"https://www.indeed.com/jobs?q={quote_plus(keywords)}&l={quote_plus(location)}&start={page * 10}"
                # Make request
                response = requests.get(
                    search_url,
                    headers=headers
                )
                if response.status_code == 403:
                    self.logger.warning(f"Indeed returned 403 Forbidden for page {page+1}. Trying next user-agent.")
                    time.sleep(random.uniform(2, 5))
                    continue
                response.raise_for_status()
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = soup.find_all('div', class_='job_seen_beacon')
                for card in job_cards:
                    try:
                        job_data = self._extract_indeed_job_data(card)
                        if job_data:
                            all_jobs.append(job_data)
                    except Exception as e:
                        self.logger.warning(f"Error extracting job data: {e}")
                        continue
                if len(job_cards) < 10:
                    break
                time.sleep(random.uniform(2, 5))
        except Exception as e:
            self.logger.error(f"Error during Indeed scraping: {e}")
        unique_jobs = self.deduplicate_jobs(all_jobs)
        self.logger.info(f"Indeed scraping completed: {len(unique_jobs)} jobs found")
        return unique_jobs
    
    def _extract_indeed_job_data(self, card) -> Optional[Dict[str, Any]]:
        """
        Extract job data from an Indeed job card.
        
        Args:
            card: BeautifulSoup job card element
            
        Returns:
            Job data dictionary or None if extraction fails
        """
        try:
            # Extract basic info
            title_elem = card.find('h2', class_='jobTitle')
            title = title_elem.text.strip() if title_elem else ""
            
            company_elem = card.find('span', class_='companyName')
            company = company_elem.text.strip() if company_elem else ""
            
            location_elem = card.find('div', class_='companyLocation')
            location = location_elem.text.strip() if location_elem else ""
            
            # Get job URL
            job_url = ""
            link_elem = card.find('a', class_='jcs-JobTitle')
            if link_elem and 'href' in link_elem.attrs:
                job_url = urljoin('https://www.indeed.com', link_elem['href'])
            
            # Extract salary info
            salary_elem = card.find('div', class_='salary-snippet')
            salary_text = salary_elem.text.strip() if salary_elem else ""
            
            # Extract job description
            desc_elem = card.find('div', class_='job-snippet')
            description = desc_elem.text.strip() if desc_elem else ""
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'job_url': job_url,
                'salary_text': salary_text,
                'description': description,
                'source': 'indeed'
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting job data: {e}")
            return None


def scrape_all_jobs(config_path: str = "config.json") -> List[Dict[str, Any]]:
    """
    Scrape jobs from all configured sources.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        List of job dictionaries
    """
    config = load_config(config_path)
    scraper = JobScraper(config_path)
    
    all_jobs = []
    
    # Scrape LinkedIn jobs
    if config.get('enable_linkedin_scraping', True):
        try:
            linkedin_jobs = asyncio.run(scraper.scrape_linkedin_jobs(
                keywords=config.get('job_keywords', []),
                locations=config.get('job_locations', []),
                min_salary_aed=config.get('min_salary_aed', 0),
                max_results=config.get('max_results_per_query', 50)
            ))
            all_jobs.extend(linkedin_jobs)
        except Exception as e:
            logger.error(f"LinkedIn scraping failed: {e}")
    
    # Scrape Indeed jobs
    if config.get('enable_indeed_scraping', True):
        try:
            indeed_jobs = scraper.scrape_indeed_jobs(
                keywords=config.get('job_keywords', [])[0] if config.get('job_keywords') else "",
                location=config.get('job_locations', [])[0] if config.get('job_locations') else "",
                max_pages=config.get('max_pages', 3)
            )
            all_jobs.extend(indeed_jobs)
        except Exception as e:
            logger.error(f"Indeed scraping failed: {e}")
    
    # Final deduplication
    unique_jobs = scraper.deduplicate_jobs(all_jobs)
    logger.info(f"Total unique jobs found: {len(unique_jobs)}")
    
    return unique_jobs


def scrape_linkedin_jobs(
    keywords: List[str],
    locations: List[str],
    min_salary_aed: int = 0,
    max_results: int = 50
) -> List[Dict[str, Any]]:
    """
    Module-level function to scrape jobs from LinkedIn.
    
    Args:
        keywords: List of job keywords to search
        locations: List of locations to search
        min_salary_aed: Minimum salary in AED
        max_results: Maximum results per query
        
    Returns:
        List of job dictionaries
    """
    scraper = JobScraper()
    return asyncio.run(scraper.scrape_linkedin_jobs(
        keywords=keywords,
        locations=locations,
        min_salary_aed=min_salary_aed,
        max_results=max_results
    ))

def scrape_indeed_jobs(
    keywords: str,
    location: str,
    max_pages: int = 3
) -> List[Dict[str, Any]]:
    """
    Module-level function to scrape jobs from Indeed.
    
    Args:
        keywords: Job keywords to search
        location: Job location
        max_pages: Maximum number of pages to scrape
        
    Returns:
        List of job dictionaries
    """
    scraper = JobScraper()
    return scraper.scrape_indeed_jobs(
        keywords=keywords,
        location=location,
        max_pages=max_pages
    )

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        jobs = scrape_all_jobs()
        logger.info(f"Found {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"Error scraping jobs: {e}")
        sys.exit(1)

