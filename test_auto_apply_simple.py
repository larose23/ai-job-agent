#!/usr/bin/env python3
"""
Simplified test script for auto-apply functionality without Google Sheets dependency.
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

from helpers import load_config, logger

async def test_browser_automation():
    """
    Test the browser automation functionality without Google Sheets.
    """
    try:
        logger.info("Starting browser automation test...")
        
        # Load configuration
        config = load_config("config.json")
        
        # Get user profile
        user_profile = config.get('user_profile', {})
        if not user_profile:
            logger.error("User profile not found in config")
            return
        
        # Test browser initialization
        try:
            from playwright.async_api import async_playwright
            
            logger.info("Testing browser initialization...")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Test navigation to a simple page
            logger.info("Testing page navigation...")
            await page.goto('https://www.google.com')
            title = await page.title()
            logger.info(f"[SUCCESS] Browser automation test passed. Page title: {title}")
            
            await browser.close()
            await playwright.stop()
            
        except Exception as e:
            logger.error(f"[ERROR] Browser automation test failed: {e}")
            return
        
        logger.info("Browser automation test completed successfully.")
        
    except Exception as e:
        logger.error(f"Browser automation test failed: {e}")
        raise

def main():
    """Main entry point."""
    # Run the test
    asyncio.run(test_browser_automation())

if __name__ == "__main__":
    main() 