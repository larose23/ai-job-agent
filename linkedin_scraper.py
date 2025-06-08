"""
LinkedIn job scraping module for the AI Job Agent application.

This module provides the LinkedInScraper class that handles:
1. Job search on LinkedIn using Selenium
2. Data extraction from job listings
3. Authentication and session management
4. Error handling and retry logic

Example usage:
    with LinkedInScraper(email="user@example.com", password="password") as scraper:
        scraper.login()
        jobs = scraper.search_jobs("python developer", "dubai")
"""

import os
import time
import random
from typing import Dict, List, Optional, Any, Union, Type
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from helpers import (
    retry_network,
    retry_auth,
    safe_operation,
    random_delay,
    logger,
    notify_slack
)

class LinkedInScraper:
    """
    LinkedIn job scraper using Selenium and undetected-chromedriver.
    
    This class provides methods for:
    1. Setting up and managing a Chrome driver
    2. Authenticating with LinkedIn
    3. Searching for jobs
    4. Extracting job data
    5. Handling errors and retries
    
    Attributes:
        email (str): LinkedIn login email
        password (str): LinkedIn login password
        driver (Optional[webdriver.Chrome]): Chrome driver instance
        wait (Optional[WebDriverWait]): WebDriverWait instance for explicit waits
    """
    
    def __init__(self, email: str, password: str) -> None:
        """
        Initialize LinkedIn scraper with credentials.
        
        Args:
            email: LinkedIn login email
            password: LinkedIn login password
            
        Example:
            scraper = LinkedInScraper("user@example.com", "password")
        """
        self.email = email
        self.password = password
        self.driver = None
        self.wait = None
        
    def __enter__(self) -> 'LinkedInScraper':
        """
        Context manager entry.
        
        Returns:
            LinkedInScraper: Self instance with driver set up
            
        Example:
            with LinkedInScraper(email, password) as scraper:
                scraper.login()
        """
        self.setup_driver()
        return self
        
    def __exit__(self, exc_type: Optional[Type[Exception]], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        """
        Context manager exit.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
            
        Example:
            with LinkedInScraper(email, password) as scraper:
                scraper.login()
        """
        if self.driver:
            self.driver.quit()
            
    @safe_operation
    def setup_driver(self) -> None:
        """
        Set up the Chrome driver with undetected-chromedriver.
        
        This method:
        1. Configures Chrome options for headless operation
        2. Initializes the undetected-chromedriver
        3. Sets up WebDriverWait for explicit waits
        
        Raises:
            Exception: If driver setup fails
            
        Example:
            scraper.setup_driver()
        """
        try:
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            self.driver = uc.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 20)
            
        except Exception as e:
            error_msg = f"Failed to setup Chrome driver: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_auth
    def login(self) -> None:
        """
        Log in to LinkedIn with retry logic.
        
        This method:
        1. Navigates to the LinkedIn login page
        2. Enters credentials
        3. Submits the login form
        4. Waits for successful login
        
        Raises:
            Exception: If login fails after retries
            
        Example:
            scraper.login()
        """
        try:
            self.driver.get("https://www.linkedin.com/login")
            random_delay()
            
            # Enter email
            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.send_keys(self.email)
            random_delay()
            
            # Enter password
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            random_delay()
            
            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for login to complete
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav"))
            )
            
            logger.info("Successfully logged in to LinkedIn")
            
        except Exception as e:
            error_msg = f"LinkedIn login failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def search_jobs(
        self,
        keywords: str,
        location: str,
        max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs on LinkedIn with retry logic.
        
        This method:
        1. Constructs the search URL
        2. Navigates to the search results
        3. Extracts job data from each page
        4. Handles pagination
        
        Args:
            keywords: Job search keywords (e.g., "python developer")
            location: Location to search in (e.g., "dubai")
            max_pages: Maximum number of pages to scrape (default: 5)
            
        Returns:
            List[Dict[str, Any]]: List of job dictionaries containing:
                - title: Job title
                - company: Company name
                - location: Job location
                - description: Full job description
                - apply_link: Direct application link (if available)
                - source: Source platform (LinkedIn)
                - scraped_at: Timestamp of scraping
                
        Raises:
            Exception: If job search fails after retries
            
        Example:
            jobs = scraper.search_jobs("python developer", "dubai", max_pages=3)
        """
        jobs = []
        page = 1
        
        try:
            # Construct search URL
            search_url = (
                f"https://www.linkedin.com/jobs/search/?"
                f"keywords={keywords.replace(' ', '%20')}&"
                f"location={location.replace(' ', '%20')}"
            )
            
            self.driver.get(search_url)
            random_delay()
            
            while page <= max_pages:
                # Wait for job cards to load
                job_cards = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, ".job-card-container")
                    )
                )
                
                # Extract job data from each card
                for card in job_cards:
                    try:
                        job_data = self._extract_job_data(card)
                        if job_data:
                            jobs.append(job_data)
                    except StaleElementReferenceException:
                        logger.warning("Stale element encountered, skipping job card")
                        continue
                        
                # Try to click next page
                try:
                    next_button = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "button.artdeco-pagination__button--next"
                    )
                    if "artdeco-button--disabled" in next_button.get_attribute("class"):
                        break
                    next_button.click()
                    random_delay()
                    page += 1
                except NoSuchElementException:
                    break
                    
            logger.info(f"Successfully scraped {len(jobs)} jobs from LinkedIn")
            return jobs
            
        except Exception as e:
            error_msg = f"LinkedIn job search failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @safe_operation
    def _extract_job_data(self, card: Any) -> Optional[Dict[str, Any]]:
        """
        Extract job data from a job card with error handling.
        
        This method:
        1. Clicks on the job card to load details
        2. Waits for job details to load
        3. Extracts job information
        4. Handles missing or stale elements
        
        Args:
            card: Selenium WebElement representing a job card
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing job details:
                - title: Job title
                - company: Company name
                - location: Job location
                - description: Full job description
                - apply_link: Direct application link (if available)
                - source: Source platform (LinkedIn)
                - scraped_at: Timestamp of scraping
                None if extraction fails
                
        Example:
            job_data = scraper._extract_job_data(job_card)
        """
        try:
            # Click on job card to load details
            card.click()
            random_delay()
            
            # Wait for job details to load
            job_details = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-view-layout"))
            )
            
            # Extract job information
            title = job_details.find_element(
                By.CSS_SELECTOR,
                ".job-details-jobs-unified-top-card__job-title"
            ).text
            
            company = job_details.find_element(
                By.CSS_SELECTOR,
                ".job-details-jobs-unified-top-card__company-name"
            ).text
            
            location = job_details.find_element(
                By.CSS_SELECTOR,
                ".job-details-jobs-unified-top-card__bullet"
            ).text
            
            # Get job description
            description = job_details.find_element(
                By.CSS_SELECTOR,
                ".job-details-jobs-unified-top-card__job-description"
            ).text
            
            # Get application link
            try:
                apply_button = job_details.find_element(
                    By.CSS_SELECTOR,
                    ".jobs-apply-button"
                )
                apply_link = apply_button.get_attribute("href")
            except NoSuchElementException:
                apply_link = None
                
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'apply_link': apply_link,
                'source': 'LinkedIn',
                'scraped_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract job data: {str(e)}")
            return None

def create_linkedin_scraper() -> LinkedInScraper:
    """
    Create a LinkedIn scraper instance with credentials from environment variables.
    
    Returns:
        LinkedInScraper: Configured LinkedIn scraper instance
        
    Raises:
        ValueError: If required environment variables are missing
        
    Example:
        scraper = create_linkedin_scraper()
    """
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    
    if not email or not password:
        error_msg = "Missing LinkedIn credentials in environment variables"
        logger.error(error_msg)
        notify_slack(error_msg)
        raise ValueError(error_msg)
        
    return LinkedInScraper(email=email, password=password)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Test LinkedIn scraping
        with create_linkedin_scraper() as scraper:
            # Login
            scraper.login()
            
            # Search for jobs
            jobs = scraper.search_jobs(
                keywords="Python Developer",
                location="Remote",
                max_pages=2
            )
            
            logger.info(f"Found {len(jobs)} jobs")
            for job in jobs:
                logger.info(f"Job: {job['title']} at {job['company']}")
                
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1) 