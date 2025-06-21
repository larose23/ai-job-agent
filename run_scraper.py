#!/usr/bin/env python3
"""
Simple runner script for the job scraper service.
Loads configuration and runs the scraper with specified parameters.

Usage:
    python run_scraper.py                    # Run with default config
    python run_scraper.py --config custom.json  # Run with custom config
    python run_scraper.py --help             # Show help
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any
from datetime import datetime, timedelta

from dotenv import load_dotenv
from scraper_service import JobScraper
from helpers import load_config, notify_slack
from slack_notifications import notify_slack as slack_notify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(dotenv_path=".env")

# Verify environment variables are loaded
print("Loaded email:", os.getenv("LINKEDIN_EMAIL"))

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description='Job scraper for LinkedIn, Indeed, and Glassdoor')
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=1,
        help='Maximum number of pages to scrape per platform (default: 1)'
    )
    
    parser.add_argument(
        '--headful',
        action='store_true',
        help='Run browser in headful mode (default: False)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    
    return parser.parse_args()

def is_cookie_file_stale(filepath: str, max_age_days: int = 7) -> bool:
    """
    Check if a cookie file is stale (doesn't exist or older than max_age_days).
    
    Args:
        filepath: Path to cookie file
        max_age_days: Maximum age in days before file is considered stale
        
    Returns:
        bool: True if file is stale or doesn't exist
    """
    if not os.path.exists(filepath):
        return True
    mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
    return datetime.now() - mod_time > timedelta(days=max_age_days)

def load_config(config_path: str) -> dict:
    """
    Load configuration from JSON file.
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Validate required fields
        required_fields = ['keywords', 'locations']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field '{field}' in config file")
                
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise

async def run_scraper(config_path: str, max_pages: int, headful: bool) -> List[Dict[str, Any]]:
    """
    Run the job scraper with the given configuration.
    
    Args:
        config_path: Path to configuration file
        max_pages: Maximum number of pages to scrape per search
        headful: Whether to run browser in non-headless mode
        
    Returns:
        List of job dictionaries
    """
    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)
        
        # Debug prints
        print("[DEBUG] run_scraper.py - Raw config keywords:", config.get("keywords"))
        print("[DEBUG] run_scraper.py - Config file path:", config_path)
        
        # Validate required config fields
        if not config.get("keywords") or not config.get("locations"):
            raise ValueError("Keywords and locations are required in config")
        
        logger.info(f"Configuration loaded successfully. Keywords: {config['keywords']}, Locations: {config['locations']}")
        
        # Initialize scraper with headful mode
        scraper = JobScraper(headful=headful)
        
        # Run scraper
        logger.info(f"Starting job scraping with max_pages={max_pages} and headful={headful}...")
        jobs = await scraper.get_jobs(
            keywords=config["keywords"],
            locations=config["locations"],
            max_pages=max_pages
        )
        
        logger.info(f"Scraping completed. Found {len(jobs)} jobs.")
        return jobs
        
    except Exception as e:
        error_msg = f"Scraper failed: {str(e)}"
        logger.error(error_msg)
        slack_notify(error_msg)
        raise

def save_results(jobs: List[Dict[str, Any]], output_path: str) -> None:
    """
    Save scraped jobs to a JSON file.
    
    Args:
        jobs: List of job dictionaries
        output_path: Path to save the results
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {output_path}")
    except Exception as e:
        error_msg = f"Failed to save results: {str(e)}"
        logger.error(error_msg)
        slack_notify(error_msg)
        raise

async def main():
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Load configuration
        config = load_config(args.config)
        
        # Initialize scraper
        scraper = JobScraper(headful=args.headful)
        
        # Start scraping
        logger.info(f"Starting job scraping with configuration:")
        logger.info(f"  - Max pages: {args.max_pages}")
        logger.info(f"  - Headful mode: {args.headful}")
        logger.info(f"  - Config file: {args.config}")
        logger.info(f"  - Keywords: {config['keywords']}")
        logger.info(f"  - Locations: {config['locations']}")
        
        # Scrape LinkedIn
        logger.info("Scraping LinkedIn...")
        linkedin_jobs = await scraper.scrape_linkedin_jobs(
            keywords=config['keywords'],
            locations=config['locations'],
            max_pages=args.max_pages
        )
        logger.info(f"Found {len(linkedin_jobs)} jobs on LinkedIn")
        
        # Scrape Indeed
        logger.info("Scraping Indeed...")
        indeed_jobs = await scraper.scrape_indeed_jobs(
            keywords=config['keywords'],
            locations=config['locations'],
            max_pages=args.max_pages
        )
        logger.info(f"Found {len(indeed_jobs)} jobs on Indeed")
        
        # Scrape Glassdoor
        logger.info("Scraping Glassdoor...")
        glassdoor_jobs = await scraper.scrape_glassdoor_jobs(
            keywords=config['keywords'],
            locations=config['locations'],
            max_pages=args.max_pages
        )
        logger.info(f"Found {len(glassdoor_jobs)} jobs on Glassdoor")
        
        # Combine all jobs
        all_jobs = linkedin_jobs + indeed_jobs + glassdoor_jobs
        logger.info(f"Total jobs found: {len(all_jobs)}")
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'job_results_{timestamp}.json'
        
        # Save to JSON
        scraper.save_to_json(all_jobs, filename)
        logger.info(f"Results saved to {filename}")
        
        # Save to CSV
        csv_filename = f'job_results_{timestamp}.csv'
        scraper.save_to_csv(all_jobs, csv_filename)
        logger.info(f"Results saved to {csv_filename}")
        
        # Send Slack notification
        message = f"Job scraping completed successfully!\nFound {len(all_jobs)} jobs across all platforms.\nResults saved to {filename} and {csv_filename}"
        slack_notify(message)
        logger.info("Slack notification sent")
        
    except Exception as e:
        error_message = f"Error during job scraping: {str(e)}"
        logger.error(error_message)
        slack_notify(error_message)
        raise
    finally:
        # Close browser
        if 'scraper' in locals():
            await scraper.close()
            logger.info("Browser closed")

if __name__ == "__main__":
    asyncio.run(main()) 