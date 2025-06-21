"""
Job application automation module for the AI Job Agent application.
Handles web form automation for job applications on various platforms.

This module provides the JobApplication class that handles:
1. Web form automation for job applications
2. Integration with existing job tracking
3. Error handling and retry logic
4. Application status updates

Example usage:
    with JobApplication(config_path="config.json") as app:
        success = await app.apply_to_job(job_data, user_profile)
"""

import os
import asyncio
import random
import logging
from typing import Dict, List, Optional, Any, Union
from playwright.async_api import async_playwright, Browser, Page
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
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
from sheets_logger import SheetsLogger

class JobApplication:
    """Handles automated job applications through web forms."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the job application handler.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logger
        self.browser = None
        self.page = None
        self.sheets_logger = SheetsLogger(config_path)
        
    async def __aenter__(self):
        """Context manager entry."""
        await self.init_browser()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.browser:
            await self.browser.close()
            
    async def init_browser(self) -> None:
        """Initialize the browser for web automation."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            
            # Set a more realistic user agent
            await self.page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            })
            
            # Enable stealth mode
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            notify_slack(f"Browser initialization failed: {e}")
            raise
            
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def apply_to_job(self, job: Dict[str, Any], user_profile: Dict[str, Any]) -> bool:
        """
        Apply to a job using web form automation.
        
        Args:
            job: Job data dictionary
            user_profile: User profile data dictionary
            
        Returns:
            bool: True if application was successful, False otherwise
        """
        try:
            # Determine the application method based on the job source
            source = job.get('source', '').lower()
            apply_url = job.get('apply_url') or job.get('url')
            
            if not apply_url:
                logger.error("No application URL found for job")
                return False
                
            # Navigate to the application page
            await self.page.goto(apply_url, wait_until='networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Handle application based on source
            if 'linkedin' in source:
                success = await self._handle_linkedin_application(job, user_profile)
            elif 'indeed' in source:
                success = await self._handle_indeed_application(job, user_profile)
            else:
                logger.warning(f"Unsupported job source for automation: {source}")
                return False
                
            if success:
                # Update application status in Google Sheets
                self.sheets_logger.mark_applied(job['url'])
                logger.info(f"Successfully applied to {job['title']} at {job['company']}")
                return True
            else:
                logger.error(f"Failed to apply to {job['title']} at {job['company']}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying to job: {e}")
            notify_slack(f"Job application failed: {e}")
            return False
            
    async def _handle_linkedin_application(self, job: Dict[str, Any], user_profile: Dict[str, Any]) -> bool:
        """Handle LinkedIn Easy Apply application with robust error handling and logging."""
        try:
            # CAPTCHA/anti-bot detection
            page_content = await self.page.content()
            if any(text in page_content.lower() for text in ["captcha", "security check", "unusual traffic", "verify you're a human"]):
                logger.warning("CAPTCHA or anti-bot detected on LinkedIn. Logging for manual review.")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required: CAPTCHA/anti-bot detected")
                return False

            # Check for Easy Apply button
            easy_apply_button = await self.page.query_selector('button[data-control-name="jobdetails_topcard_inapply"]')
            if not easy_apply_button:
                logger.warning("Easy Apply button not found. Logging for manual review.")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required: Easy Apply button not found")
                return False

            # Click Easy Apply button
            await easy_apply_button.click()
            await asyncio.sleep(random.uniform(1, 2))

            # Fill out the application form
            form_selectors = {
                'name': 'input[name="name"]',
                'email': 'input[name="email"]',
                'phone': 'input[name="phone"]',
                'resume': 'input[type="file"]'
            }
            try:
                for field, selector in form_selectors.items():
                    if field == 'resume':
                        if user_profile.get('resume_path'):
                            await self.page.set_input_files(selector, user_profile['resume_path'])
                    else:
                        value = user_profile.get(field, '')
                        if value:
                            await self.page.fill(selector, value)
                            await asyncio.sleep(random.uniform(0.1, 0.3))
            except Exception as e:
                logger.warning(f"Form structure unsupported or error filling form: {e}. Logging for manual review.")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), f"Manual review required: Form structure unsupported or error: {e}")
                return False

            # Handle additional questions if present
            try:
                await self._handle_linkedin_questions()
            except Exception as e:
                logger.warning(f"Error handling additional questions: {e}. Logging for manual review.")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), f"Manual review required: Error handling questions: {e}")
                return False

            # Submit application
            submit_button = await self.page.query_selector('button[aria-label="Submit application"]')
            if submit_button:
                await submit_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                # Check for success message
                success_message = await self.page.query_selector('.jobs-easy-apply-success-message')
                if success_message:
                    return True
                else:
                    logger.warning("No success message after submit. Logging for manual review.")
                    self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required: No success message after submit")
                    return False
            else:
                logger.warning("Submit button not found. Logging for manual review.")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required: Submit button not found")
                return False
        except Exception as e:
            logger.error(f"Error in LinkedIn application: {e}")
            self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), f"Manual review required: Exception: {e}")
            return False
            
    async def _handle_linkedin_questions(self) -> None:
        """Handle additional questions in LinkedIn application form."""
        try:
            # Look for question containers
            question_containers = await self.page.query_selector_all('.jobs-easy-apply-form-element')
            
            for container in question_containers:
                # Get question text
                question_text = await container.query_selector('.jobs-easy-apply-form-element__label')
                if not question_text:
                    continue
                    
                question = await question_text.inner_text()
                
                # Handle different question types
                # Radio buttons
                radio_buttons = await container.query_selector_all('input[type="radio"]')
                if radio_buttons:
                    # Select first option by default
                    await radio_buttons[0].click()
                    continue
                    
                # Checkboxes
                checkboxes = await container.query_selector_all('input[type="checkbox"]')
                if checkboxes:
                    # Check first option by default
                    await checkboxes[0].click()
                    continue
                    
                # Text input
                text_input = await container.query_selector('input[type="text"]')
                if text_input:
                    # Enter a default response
                    await text_input.fill("Yes")
                    continue
                    
                # Text area
                text_area = await container.query_selector('textarea')
                if text_area:
                    # Enter a default response
                    await text_area.fill("I am interested in this position and meet the requirements.")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling LinkedIn questions: {e}")
            
    async def _handle_indeed_application(self, job: Dict[str, Any], user_profile: Dict[str, Any]) -> bool:
        """Handle Indeed application."""
        try:
            # Check for apply button
            apply_button = await self.page.query_selector('button[data-tn-element="apply-button"]')
            if not apply_button:
                logger.warning("Indeed apply button not found")
                return False
                
            # Click apply button
            await apply_button.click()
            await asyncio.sleep(random.uniform(1, 2))
            
            # Handle Indeed's application form
            # Note: Indeed's form structure may vary, so we need to handle different cases
            form_selectors = {
                'name': 'input[name="name"]',
                'email': 'input[name="email"]',
                'phone': 'input[name="phone"]',
                'resume': 'input[type="file"]'
            }
            
            # Fill basic information
            for field, selector in form_selectors.items():
                if field == 'resume':
                    # Handle resume upload
                    if user_profile.get('resume_path'):
                        await self.page.set_input_files(selector, user_profile['resume_path'])
                else:
                    # Fill text fields
                    value = user_profile.get(field, '')
                    if value:
                        await self.page.fill(selector, value)
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                        
            # Handle additional questions if present
            await self._handle_indeed_questions()
            
            # Submit application
            submit_button = await self.page.query_selector('button[type="submit"]')
            if submit_button:
                await submit_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                
                # Check for success message or redirect
                success_indicators = [
                    '.jobsearch-IndeedApplyButton-successMessage',
                    '.jobsearch-IndeedApplyButton-successIcon',
                    '.jobsearch-IndeedApplyButton-successText'
                ]
                
                for indicator in success_indicators:
                    success_element = await self.page.query_selector(indicator)
                    if success_element:
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Error in Indeed application: {e}")
            return False
            
    async def _handle_indeed_questions(self) -> None:
        """Handle additional questions in Indeed application form."""
        try:
            # Look for question containers
            question_containers = await self.page.query_selector_all('.jobsearch-IndeedApplyButton-formElement')
            
            for container in question_containers:
                # Get question text
                question_text = await container.query_selector('.jobsearch-IndeedApplyButton-formElement-label')
                if not question_text:
                    continue
                    
                question = await question_text.inner_text()
                
                # Handle different question types
                # Radio buttons
                radio_buttons = await container.query_selector_all('input[type="radio"]')
                if radio_buttons:
                    # Select first option by default
                    await radio_buttons[0].click()
                    continue
                    
                # Checkboxes
                checkboxes = await container.query_selector_all('input[type="checkbox"]')
                if checkboxes:
                    # Check first option by default
                    await checkboxes[0].click()
                    continue
                    
                # Text input
                text_input = await container.query_selector('input[type="text"]')
                if text_input:
                    # Enter a default response
                    await text_input.fill("Yes")
                    continue
                    
                # Text area
                text_area = await container.query_selector('textarea')
                if text_area:
                    # Enter a default response
                    await text_area.fill("I am interested in this position and meet the requirements.")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Indeed questions: {e}")
