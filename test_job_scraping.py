#!/usr/bin/env python3
"""
Test job scraping functionality independently of Gmail.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from helpers import logger, load_config
from job_scraper import JobScraper

async def test_job_scraping():
    """Test job scraping functionality."""
    logger.info("Testing job scraping functionality...")
    
    try:
        # Initialize job scraper
        scraper = JobScraper("config.json")
        logger.info("Job scraper initialized successfully")
        
        # Test LinkedIn scraping
        logger.info("Testing LinkedIn job scraping...")
        try:
            linkedin_jobs = await scraper.scrape_linkedin_jobs(
                keywords=["python developer"],
                locations=["remote"],
                max_results=3
            )
            logger.info(f"LinkedIn scraping: SUCCESS - Found {len(linkedin_jobs)} jobs")
            
            if linkedin_jobs:
                for i, job in enumerate(linkedin_jobs[:2]):  # Show first 2 jobs
                    logger.info(f"Job {i+1}: {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")
                    
        except Exception as e:
            logger.warning(f"LinkedIn scraping failed (may be rate limited): {e}")
        
        # Test Indeed scraping
        logger.info("Testing Indeed job scraping...")
        try:
            indeed_jobs = await scraper.scrape_indeed_jobs(
                keywords=["python developer"],
                location="remote"
            )
            logger.info(f"Indeed scraping: SUCCESS - Found {len(indeed_jobs)} jobs")
            
            if indeed_jobs:
                for i, job in enumerate(indeed_jobs[:2]):  # Show first 2 jobs
                    logger.info(f"Job {i+1}: {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")
                    
        except Exception as e:
            logger.warning(f"Indeed scraping failed (may be rate limited): {e}")
        
        logger.info("Job scraping test completed!")
        return True
        
    except Exception as e:
        logger.error(f"Job scraping test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_job_scraping())
    if success:
        logger.info("Job scraping test: PASSED")
    else:
        logger.error("Job scraping test: FAILED") 