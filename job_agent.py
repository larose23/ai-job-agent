"""
Job Agent module for automated job search and analysis.

This module provides the main JobAgent class that orchestrates:
1. Job searching on LinkedIn
2. Job analysis using OpenAI
3. Spreadsheet logging
4. Email notifications

Example usage:
    agent = JobAgent("config.json")
    agent.setup()
    results = agent.run(
        keywords="python developer",
        location="dubai",
        recipient_email="user@example.com"
    )
"""

import os
import time
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI
from linkedin_scraper import LinkedInScraper
from gmail_sender import GmailSender
from spreadsheet_manager import SpreadsheetManager
from helpers import (
    retry_network,
    retry_auth,
    safe_operation,
    random_delay,
    logger,
    notify_slack,
    load_config
)

class JobAgent:
    """
    Main class for job search automation.
    
    This class coordinates the entire job search process:
    1. Initializes and manages all components
    2. Handles job searching and analysis
    3. Manages data storage and notifications
    4. Provides error handling and retry logic
    
    Attributes:
        config (Dict[str, Any]): Configuration dictionary
        openai_client (OpenAI): OpenAI API client
        linkedin_scraper (Optional[LinkedInScraper]): LinkedIn scraper instance
        gmail_sender (Optional[GmailSender]): Gmail sender instance
        spreadsheet_manager (Optional[SpreadsheetManager]): Spreadsheet manager instance
    """
    
    def __init__(self, config_path: str = "config.json") -> None:
        """
        Initialize the JobAgent.
        
        Args:
            config_path: Path to the configuration file
            
        Example:
            agent = JobAgent("config.json")
        """
        self.config = load_config(config_path)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.linkedin_scraper = None
        self.gmail_sender = None
        self.spreadsheet_manager = None
        
    @safe_operation
    def setup(self) -> None:
        """
        Set up all components with error handling.
        
        This method:
        1. Initializes the LinkedIn scraper
        2. Sets up the Gmail sender
        3. Configures the spreadsheet manager
        4. Verifies all components are working
        
        Raises:
            Exception: If any component fails to initialize
            
        Example:
            agent.setup()
        """
        try:
            # Initialize LinkedIn scraper
            self.linkedin_scraper = LinkedInScraper(
                email=os.getenv("LINKEDIN_EMAIL"),
                password=os.getenv("LINKEDIN_PASSWORD")
            )
            
            # Initialize Gmail sender
            self.gmail_sender = GmailSender(
                email=os.getenv("GMAIL_SENDER_EMAIL"),
                app_password=os.getenv("GMAIL_APP_PASSWORD")
            )
            
            # Initialize spreadsheet manager
            self.spreadsheet_manager = SpreadsheetManager(
                spreadsheet_id=os.getenv("SPREADSHEET_ID")
            )
            self.spreadsheet_manager.authenticate()
            
            logger.info("Successfully set up all components")
            
        except Exception as e:
            error_msg = f"Failed to set up components: {str(e)}"
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
        Search for jobs with retry logic.
        
        Args:
            keywords: Job search keywords (e.g., "python developer")
            location: Location to search in (e.g., "dubai")
            max_pages: Maximum number of pages to scrape (default: 5)
            
        Returns:
            List[Dict[str, Any]]: List of job listings with details
            
        Raises:
            Exception: If job search fails
            
        Example:
            jobs = agent.search_jobs("python developer", "dubai", max_pages=3)
        """
        try:
            with self.linkedin_scraper as scraper:
                scraper.login()
                jobs = scraper.search_jobs(keywords, location, max_pages)
                
            logger.info(f"Successfully found {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            error_msg = f"Job search failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def analyze_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a job listing with retry logic.
        
        Args:
            job: Job listing to analyze with required fields:
                - title: Job title
                - company: Company name
                - location: Job location
                - description: Job description
                
        Returns:
            Dict[str, Any]: Job listing with added analysis
            
        Raises:
            Exception: If job analysis fails
            
        Example:
            analyzed_job = agent.analyze_job(job_listing)
        """
        try:
            # Prepare prompt
            prompt = f"""
            Analyze this job listing and provide:
            1. Key requirements
            2. Required skills
            3. Experience level
            4. Salary range (if mentioned)
            5. Company culture indicators
            6. Match score (0-100)
            
            Job Title: {job['title']}
            Company: {job['company']}
            Location: {job['location']}
            Description: {job['description']}
            """
            
            # Get analysis from OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a job analysis expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Parse response
            analysis = response.choices[0].message.content
            
            # Add analysis to job data
            job['analysis'] = analysis
            
            logger.info(f"Successfully analyzed job: {job['title']}")
            return job
            
        except Exception as e:
            error_msg = f"Job analysis failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def save_to_spreadsheet(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Save jobs to spreadsheet with retry logic.
        
        Args:
            jobs: List of job listings to save with required fields:
                - title: Job title
                - company: Company name
                - location: Job location
                - analysis: Job analysis
                - apply_link: Application link
                - scraped_at: Timestamp
                
        Raises:
            Exception: If saving to spreadsheet fails
            
        Example:
            agent.save_to_spreadsheet(job_listings)
        """
        try:
            # Prepare data
            values = []
            for job in jobs:
                row = [
                    job['title'],
                    job['company'],
                    job['location'],
                    job.get('analysis', ''),
                    job.get('apply_link', ''),
                    job.get('scraped_at', '')
                ]
                values.append(row)
                
            # Append to spreadsheet
            self.spreadsheet_manager.append_rows(
                range_name="Jobs!A:F",
                values=values
            )
            
            logger.info(f"Successfully saved {len(jobs)} jobs to spreadsheet")
            
        except Exception as e:
            error_msg = f"Failed to save jobs to spreadsheet: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def send_job_alerts(
        self,
        jobs: List[Dict[str, Any]],
        recipient_email: str,
        subject: str = "New Job Opportunities"
    ) -> Dict[str, str]:
        """
        Send job alerts via email with retry logic.
        
        Args:
            jobs: List of job listings to send
            recipient_email: Email address to send to
            subject: Email subject (default: "New Job Opportunities")
            
        Returns:
            Dict[str, str]: Results summary with keys:
                - status: "success" or "error"
                - message: Success or error message
                
        Raises:
            Exception: If sending email fails
            
        Example:
            result = agent.send_job_alerts(jobs, "user@example.com")
        """
        try:
            # Prepare email body
            body = "<h2>New Job Opportunities</h2>"
            for job in jobs:
                body += f"""
                <h3>{job['title']} at {job['company']}</h3>
                <p><strong>Location:</strong> {job['location']}</p>
                <p><strong>Analysis:</strong></p>
                <pre>{job.get('analysis', 'No analysis available')}</pre>
                <p><a href="{job.get('apply_link', '#')}">Apply Here</a></p>
                <hr>
                """
                
            # Send email
            success = self.gmail_sender.send_email(
                to_email=recipient_email,
                subject=subject,
                body=body
            )
            
            if success:
                logger.info(f"Successfully sent job alerts to {recipient_email}")
                return {'status': 'success', 'message': 'Email sent successfully'}
            else:
                error_msg = f"Failed to send job alerts to {recipient_email}"
                logger.error(error_msg)
                notify_slack(error_msg)
                return {'status': 'error', 'message': error_msg}
                
        except Exception as e:
            error_msg = f"Failed to send job alerts: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @safe_operation
    def run(
        self,
        keywords: str,
        location: str,
        recipient_email: str,
        max_pages: int = 5
    ) -> Dict[str, Any]:
        """
        Run the complete job search and notification process.
        
        This method:
        1. Searches for jobs using the provided keywords and location
        2. Analyzes each job listing
        3. Saves the results to the spreadsheet
        4. Sends email notifications
        
        Args:
            keywords: Job search keywords (e.g., "python developer")
            location: Location to search in (e.g., "dubai")
            recipient_email: Email address to send alerts to
            max_pages: Maximum number of pages to scrape (default: 5)
            
        Returns:
            Dict[str, Any]: Results summary with keys:
                - status: "success" or "error"
                - jobs_found: Number of jobs found
                - jobs_analyzed: Number of jobs analyzed
                - alert_status: Status of email alerts
                - message: Success or error message
                
        Raises:
            Exception: If any step of the process fails
            
        Example:
            results = agent.run(
                keywords="python developer",
                location="dubai",
                recipient_email="user@example.com"
            )
        """
        try:
            # Search for jobs
            jobs = self.search_jobs(keywords, location, max_pages)
            
            # Analyze jobs
            analyzed_jobs = []
            for job in jobs:
                analyzed_job = self.analyze_job(job)
                analyzed_jobs.append(analyzed_job)
                random_delay()  # Avoid rate limiting
                
            # Save to spreadsheet
            self.save_to_spreadsheet(analyzed_jobs)
            
            # Send alerts
            alert_result = self.send_job_alerts(analyzed_jobs, recipient_email)
            
            return {
                'status': 'success',
                'jobs_found': len(jobs),
                'jobs_analyzed': len(analyzed_jobs),
                'alert_status': alert_result['status'],
                'message': alert_result['message']
            }
            
        except Exception as e:
            error_msg = f"Job search process failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            return {
                'status': 'error',
                'jobs_found': 0,
                'jobs_analyzed': 0,
                'alert_status': 'error',
                'message': error_msg
            } 