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
from datetime import datetime

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
        print(f"[DEBUG][LinkedInScraper.__init__] email: {email}, password: {password}")
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
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            random_user_agent = random.choice(user_agents)
            self.driver = uc.Chrome(options=options)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": random_user_agent
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            self.wait = WebDriverWait(self.driver, 30)
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
        5. Verifies login success with multiple checks
        
        Raises:
            Exception: If login fails after retries
            
        Example:
            scraper.login()
        """
        try:
            logger.info("Attempting to log in to LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            random_delay(3, 5)

            # Get credentials from environment variables
            email = os.getenv("LINKEDIN_EMAIL")
            password = os.getenv("LINKEDIN_PASSWORD")
            print(f"[DEBUG] Using LinkedIn email: {email}")

            # Enter email
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.clear()
            random_delay(1, 2)
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            logger.debug("Email entered successfully")
            random_delay(1, 2)
            
            # Enter password
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
            password_field.clear()
            random_delay(1, 2)
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            logger.debug("Password entered successfully")
            random_delay(1, 2)
            
            # Click login button
            login_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            random_delay(1, 2)
            login_button.click()
            logger.debug("Login button clicked")
            
            # Wait for login success
            success_selectors = [
                '.global-nav__me-photo',
                '.global-nav__me-menu',
                '.feed-identity-module',
                '.search-global-typeahead',
                '.global-nav__primary-items',
                '.global-nav__secondary-items'
            ]
            
            login_success = False
            for selector in success_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    login_success = True
                    logger.info(f"Login successful! Detected by selector: {selector}")
                    break
                except TimeoutException:
                    logger.debug(f"Selector {selector} not found, trying next...")
                    continue
            
            if not login_success:
                # Check for 2FA or CAPTCHA
                current_url = self.driver.current_url
                if "checkpoint" in current_url or "captcha" in current_url.lower():
                    logger.warning("⚠️ 2FA or CAPTCHA detected. Please complete manually in the browser.")
                    input("Press Enter after completing 2FA/CAPTCHA in the browser...")
                    logger.info("Manual intervention complete. Re-checking login status...")
                    
                    # Try all selectors again after manual intervention
                    for selector in success_selectors:
                        try:
                            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            login_success = True
                            logger.info(f"Login successful after manual intervention! Detected by selector: {selector}")
                            break
                        except TimeoutException:
                            logger.debug(f"Selector {selector} not found after manual intervention, trying next...")
                            continue
                
                if not login_success:
                    raise Exception("Login failed - no success indicators found")
            
            # Additional verification
            self.driver.get("https://www.linkedin.com/feed/")
            random_delay(2, 4)
            if "feed" not in self.driver.current_url:
                raise Exception("Failed to access feed after login")
            logger.info("Successfully accessed feed after login")
            
        except Exception as e:
            error_msg = f"Login failed: {str(e)}"
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
        """
        try:
            # Click on job card to load details
            card.click()
            random_delay()

            # Wait for job details to load
            job_details = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-view-layout"))
            )

            # Robust selectors for job info
            def try_select(selectors):
                for sel in selectors:
                    try:
                        el = job_details.find_element(By.CSS_SELECTOR, sel)
                        if el and el.text.strip():
                            return el.text.strip()
                    except Exception:
                        continue
                return "N/A"

            title = try_select([
                ".job-details-jobs-unified-top-card__job-title",
                ".top-card-layout__title",
                "h2.top-card-layout__title",
                "h1"
            ])
            company = try_select([
                ".job-details-jobs-unified-top-card__company-name",
                ".topcard__org-name-link",
                ".topcard__flavor",
                ".topcard__org-name"
            ])
            location = try_select([
                ".job-details-jobs-unified-top-card__bullet",
                ".topcard__flavor--bullet",
                ".topcard__flavor",
                ".topcard__location"
            ])
            description = try_select([
                ".job-description",
                "#job-details",
                ".description__text",
                ".jobs-description__container"
            ])

            # Get apply link if available
            try:
                apply_link = job_details.find_element(
                    By.CSS_SELECTOR,
                    ".jobs-apply-button, a[data-control-name='jobdetails_topcard_inapply']"
                ).get_attribute("href")
            except NoSuchElementException:
                apply_link = None

            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'apply_link': apply_link
            }
        except Exception as e:
            logger.warning(f"Error extracting job data: {e}")
            return None 