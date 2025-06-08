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
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus, urljoin
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from helpers import (
    load_config,
    retry_on_failure,
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
        """Log in to LinkedIn using credentials from environment variables."""
        try:
            await self.page.goto('https://www.linkedin.com/login')
            await self.page.fill('#username', os.getenv('LINKEDIN_EMAIL'))
            await self.page.fill('#password', os.getenv('LINKEDIN_PASSWORD'))
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_selector('.feed-identity-module')
            logger.info("Successfully logged in to LinkedIn")
        except Exception as e:
            logger.error(f"LinkedIn login failed: {e}")
            notify_slack(f"LinkedIn login failed: {e}")
            raise
    
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
        seen_hashes = set()
        
        for job in jobs:
            job_url = job.get('job_url', '')
            job_hash = hash_job(
                job.get('title', ''),
                job.get('company', ''),
                job.get('location', '')
            )
            
            if job_url not in seen_urls and job_hash not in seen_hashes:
                unique_jobs.append(job)
                seen_urls.add(job_url)
                seen_hashes.add(job_hash)
                
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
        min_salary_aed: int, 
        max_results: int
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
            # Extract basic info
            title_elem = await card.query_selector('.job-search-card__title a')
            title = await title_elem.inner_text() if title_elem else ""
            
            company_elem = await card.query_selector('.job-search-card__subtitle a')
            company = await company_elem.inner_text() if company_elem else ""
            
            location_elem = await card.query_selector('.job-search-card__location')
            location = await location_elem.inner_text() if location_elem else ""
            
            # Get job URL
            job_url = await title_elem.get_attribute('href') if title_elem else ""
            if job_url and not job_url.startswith('http'):
                job_url = urljoin('https://www.linkedin.com', job_url)
            
            # Click to get full description and salary info
            await card.click()
            await page.wait_for_load_state('networkidle')
            
            # Extract salary info
            salary_elem = await page.query_selector('.job-details-jobs-unified-top-card__salary-info')
            salary_text = await salary_elem.inner_text() if salary_elem else ""
            
            # Extract job description
            desc_elem = await page.query_selector('.job-description')
            description = await desc_elem.inner_text() if desc_elem else ""
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'job_url': job_url,
                'salary_text': salary_text,
                'description': description,
                'source': 'linkedin'
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting job data: {e}")
            return None
    
    @retry_on_failure(max_retries=3)
    def scrape_indeed_jobs(self, keywords: str, location: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Scrape job postings from Indeed.
        
        Args:
            keywords: Job keywords to search
            location: Job location
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of job dictionaries
        """
        self.logger.info(f"Starting Indeed job scraping for '{keywords}' in '{location}'")
        all_jobs = []
        
        try:
            for page in range(max_pages):
                jobs = self._search_indeed_jobs(keywords, location, page)
                all_jobs.extend(jobs)
                
                if len(jobs) < 10:  # Less than 10 jobs means we're on the last page
                    break
                    
                # Random delay between pages
                time.sleep(random.uniform(2, 5))
                
        except Exception as e:
            self.logger.error(f"Error during Indeed scraping: {e}")
            
        # Filter and deduplicate
        filtered_jobs = self.filter_by_salary(all_jobs, self.config.get('min_salary_aed', 0))
        unique_jobs = self.deduplicate_jobs(filtered_jobs)
        
        self.logger.info(f"Indeed scraping completed: {len(unique_jobs)} jobs found")
        return unique_jobs
    
    def _search_indeed_jobs(self, keywords: str, location: str, page: int) -> List[Dict[str, Any]]:
        """
        Search for jobs on Indeed with specific keyword and location.
        
        Args:
            keywords: Job keywords
            location: Job location
            page: Page number to scrape
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        try:
            # Construct search URL
            search_url = f"https://www.indeed.com/jobs?q={quote_plus(keywords)}&l={quote_plus(location)}&start={page * 10}"
            
            # Make request
            response = requests.get(
                search_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            
            for card in job_cards:
                try:
                    job_data = self._extract_indeed_job_data(card)
                    if job_data:
                        jobs.append(job_data)
                        
                except Exception as e:
                    self.logger.warning(f"Error extracting job data: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error searching Indeed jobs: {e}")
            
        return jobs
    
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
                keywords=config.get('job_keywords', []),
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

