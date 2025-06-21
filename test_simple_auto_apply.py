#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script for auto-apply functionality.
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

async def test_auto_apply_config():
    """
    Test the auto-apply configuration and basic functionality.
    """
    try:
        logger.info("Starting auto-apply configuration test...")
        
        # Load configuration
        config = load_config("config.json")
        
        # Check auto-apply settings
        auto_apply_config = config.get('auto_apply', {})
        auto_apply_enabled = auto_apply_config.get('enabled', True)
        review_before_apply = auto_apply_config.get('review_before_apply', False)
        
        logger.info(f"Auto-apply enabled: {auto_apply_enabled}")
        logger.info(f"Review before apply: {review_before_apply}")
        
        # Check user profile
        user_profile = config.get('user_profile', {})
        if user_profile:
            logger.info(f"User profile found: {user_profile.get('full_name', 'Unknown')}")
        else:
            logger.warning("User profile not found in config")
        
        # Check LinkedIn credentials
        linkedin_creds = config.get('credentials', {}).get('linkedin', {})
        if linkedin_creds:
            logger.info("LinkedIn credentials found in config")
        else:
            logger.warning("LinkedIn credentials not found in config")
        
        # Test browser automation capability
        try:
            from playwright.async_api import async_playwright
            
            logger.info("Testing browser automation capability...")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Test navigation
            await page.goto('https://www.google.com')
            title = await page.title()
            logger.info(f"[SUCCESS] Browser automation test passed. Page title: {title}")
            
            await browser.close()
            await playwright.stop()
            
        except Exception as e:
            logger.error(f"[ERROR] Browser automation test failed: {e}")
        
        logger.info("Auto-apply configuration test completed.")
        
    except Exception as e:
        logger.error(f"Auto-apply configuration test failed: {e}")
        raise

def main():
    """Main entry point."""
    # Run the test
    asyncio.run(test_auto_apply_config())

if __name__ == "__main__":
    main() 