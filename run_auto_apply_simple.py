#!/usr/bin/env python3
"""
Simplified Auto-apply script for the AI Job Agent.
Scans job alert emails and automatically applies to jobs without Google Sheets logging.
"""

import asyncio
import logging
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from email_scanner import scan_job_emails
from helpers import load_config, logger

# Mock SheetsLogger to avoid Google Sheets dependency
class MockSheetsLogger:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.logger = logger
        
    def mark_applied(self, job_url: str) -> None:
        self.logger.info(f"[SHEETS] Would mark job as applied: {job_url}")
        
    def update_notes(self, job_url: str, notes: str) -> None:
        self.logger.info(f"[SHEETS] Would update notes for {job_url}: {notes}")

# Patch the sheets_logger module to use our mock
import sheets_logger
sheets_logger.SheetsLogger = MockSheetsLogger

from job_application import JobApplication

async def run_auto_apply_simple(config_path: str = "config.json"):
    """
    Run the auto-apply process without Google Sheets logging:
    1. Scan job alert emails
    2. Process jobs through job application module
    3. Log results to console
    """
    try:
        logger.info("Starting simplified auto-apply process...")
        
        # Load configuration
        config = load_config(config_path)
        
        # Set auto-apply settings
        auto_apply_config = config.get('auto_apply', {})
        auto_apply_enabled = auto_apply_config.get('enabled', True)
        review_before_apply = auto_apply_config.get('review_before_apply', False)
        
        if not auto_apply_enabled:
            logger.info("Auto-apply is disabled in config. Exiting.")
            return
        
        logger.info(f"Auto-apply enabled: {auto_apply_enabled}")
        logger.info(f"Review before apply: {review_before_apply}")
        
        # Get user profile
        user_profile = config.get('user_profile', {})
        if not user_profile:
            logger.error("User profile not found in config")
            return
        
        # Scan job alert emails
        logger.info("Scanning job alert emails...")
        jobs = scan_job_emails(max_emails=50)
        
        if not jobs:
            logger.info("No jobs found in email alerts")
            return
        
        logger.info(f"Found {len(jobs)} jobs in email alerts")
        
        # Process each job
        processed_count = 0
        successful_applications = 0
        
        for job in jobs:
            try:
                logger.info(f"Processing job: {job.get('title')} at {job.get('company')}")
                logger.info(f"Apply URL: {job.get('apply_url', 'No apply URL')}")
                
                # Check if job has apply URL for web automation
                if job.get('apply_url') and auto_apply_enabled:
                    logger.info(f"Attempting web form automation for: {job.get('title')}")
                    
                    try:
                        async with JobApplication(config_path=config_path) as app:
                            result = await app.apply_to_job(job, user_profile)
                        
                        if result:
                            logger.info(f"[SUCCESS] Successfully applied to: {job.get('title')} at {job.get('company')}")
                            successful_applications += 1
                        else:
                            logger.warning(f"[FAILED] Failed to apply to: {job.get('title')} at {job.get('company')}")
                    
                    except Exception as e:
                        logger.error(f"[ERROR] Error applying to {job.get('title')}: {e}")
                
                else:
                    logger.info(f"[SKIP] Skipping {job.get('title')} - no apply URL or auto-apply disabled")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing job {job.get('title')}: {e}")
                continue
        
        logger.info(f"Auto-apply process completed.")
        logger.info(f"Processed: {processed_count} jobs")
        logger.info(f"Successful applications: {successful_applications}")
        logger.info(f"Success rate: {(successful_applications/processed_count*100):.1f}%" if processed_count > 0 else "N/A")
        
    except Exception as e:
        logger.error(f"Auto-apply process failed: {e}")
        raise

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run AI Job Agent Auto-Apply (Simplified)')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("Running in test mode...")
        # You can add test-specific logic here
    
    # Run the auto-apply process
    asyncio.run(run_auto_apply_simple(args.config))

if __name__ == "__main__":
    main() 