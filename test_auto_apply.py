#!/usr/bin/env python3
"""
Test script for auto-apply functionality using a sample job.
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

from job_application import JobApplication
from helpers import load_config, logger

async def test_auto_apply():
    """
    Test the auto-apply functionality with a sample job.
    """
    try:
        logger.info("Starting auto-apply test...")
        
        # Load configuration
        config = load_config("config.json")
        
        # Get user profile
        user_profile = config.get('user_profile', {})
        if not user_profile:
            logger.error("User profile not found in config")
            return
        
        # Create a sample job for testing
        sample_job = {
            'title': 'Software Developer',
            'company': 'Test Company',
            'location': 'Dubai, UAE',
            'apply_url': 'https://www.linkedin.com/jobs/view/test-job',
            'source': 'Test'
        }
        
        logger.info(f"Testing with sample job: {sample_job.get('title')} at {sample_job.get('company')}")
        logger.info(f"Apply URL: {sample_job.get('apply_url')}")
        
        # Test the job application module
        try:
            async with JobApplication(config_path="config.json") as app:
                logger.info("JobApplication initialized successfully")
                
                # Test the apply_to_job method
                result = await app.apply_to_job(sample_job, user_profile)
                
                if result:
                    logger.info("[SUCCESS] Job application test completed successfully")
                else:
                    logger.warning("[FAILED] Job application test failed")
                    
        except Exception as e:
            logger.error(f"[ERROR] Job application test error: {e}")
        
        logger.info("Auto-apply test completed.")
        
    except Exception as e:
        logger.error(f"Auto-apply test failed: {e}")
        raise

def main():
    """Main entry point."""
    # Run the test
    asyncio.run(test_auto_apply())

if __name__ == "__main__":
    main() 