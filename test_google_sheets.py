#!/usr/bin/env python3
"""
Simple Google Sheets API connectivity test to diagnose issues.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from helpers import logger, load_config

def test_google_sheets():
    """Test Google Sheets API connection."""
    logger.info("Testing Google Sheets API connection...")
    
    try:
        # Check if service account file exists
        if not os.path.exists('google_service_account.json'):
            logger.error("google_service_account.json not found")
            return False
        
        # Check config
        config = load_config("config.json")
        spreadsheet_id = config.get('google_sheets', {}).get('spreadsheet_id')
        
        if not spreadsheet_id:
            logger.error("Google Sheets spreadsheet_id not found in config")
            return False
        
        logger.info(f"Spreadsheet ID: {spreadsheet_id}")
        logger.info("Service account file: OK")
        
        # Test Google Sheets API
        try:
            import gspread
            from google.oauth2 import service_account
            
            logger.info("Initializing Google Sheets API...")
            
            # Try to authenticate with service account
            gc = gspread.service_account(filename='google_service_account.json')
            logger.info("Google Sheets authentication: OK")
            
            # Try to open spreadsheet
            spreadsheet = gc.open_by_key(spreadsheet_id)
            logger.info(f"Spreadsheet access: OK - {spreadsheet.title}")
            
            # Try to access a worksheet
            worksheet = spreadsheet.worksheet('Jobs')
            logger.info("Worksheet access: OK")
            
            # Try to read some data
            data = worksheet.get_all_values()
            logger.info(f"Data reading: OK - {len(data)} rows found")
            
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets API test failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Google Sheets connection test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_google_sheets()
    if success:
        logger.info("Google Sheets connection test: PASSED")
    else:
        logger.error("Google Sheets connection test: FAILED") 