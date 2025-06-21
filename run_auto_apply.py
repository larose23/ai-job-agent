#!/usr/bin/env python3
"""
Auto-apply script for the AI Job Agent.
Scans job alert emails and automatically applies to jobs using the application dispatcher.
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
from application_dispatcher import ApplicationDispatcher
from sheets_logger import SheetsLogger
from helpers import load_config, logger

async def run_auto_apply(config_path: str = "config.json"):
    """
    Run the auto-apply process:
    1. Scan job alert emails
    2. Process jobs through application dispatcher
    3. Log results to Google Sheets
    """
    try:
        logger.info("Starting auto-apply process...")
        
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
        
        # Initialize sheets logger
        sheets_logger = SheetsLogger(config_path)
        
        # Scan job alert emails
        logger.info("Scanning job alert emails...")
        jobs = scan_job_emails(max_emails=50)
        
        if not jobs:
            logger.info("No jobs found in email alerts")
            return
        
        logger.info(f"Found {len(jobs)} jobs in email alerts")
        
        # Initialize application dispatcher
        dispatcher_config = {
            'auto_apply_enabled': auto_apply_enabled,
            'review_before_apply': review_before_apply,
            'gmail': config.get('credentials', {}).get('google', {}).get('gmail', {}),
            'config_path': config_path
        }
        
        dispatcher = ApplicationDispatcher(dispatcher_config, user_profile)
        
        # Process each job
        processed_count = 0
        for job in jobs:
            try:
                logger.info(f"Processing job: {job.get('title')} at {job.get('company')}")
                
                # Log job to sheets first
                sheets_logger.append_job_row(job)
                
                # Dispatch job for application
                result = await dispatcher.dispatch(job)
                
                logger.info(f"Job {job.get('title')} dispatched with result: {result}")
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing job {job.get('title')}: {e}")
                # Log error to sheets
                try:
                    sheets_logger.update_notes(
                        job.get('job_url', job.get('apply_url', '')),
                        f"Processing error: {e}"
                    )
                except:
                    pass
                continue
        
        logger.info(f"Auto-apply process completed. Processed {processed_count} jobs.")
        
    except Exception as e:
        logger.error(f"Auto-apply process failed: {e}")
        raise

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run AI Job Agent Auto-Apply')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("Running in test mode...")
        # You can add test-specific logic here
    
    # Run the auto-apply process
    asyncio.run(run_auto_apply(args.config))

if __name__ == "__main__":
    main() 