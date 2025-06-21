#!/usr/bin/env python3
"""
Simple Gmail API connectivity test to diagnose issues.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from helpers import logger

def test_gmail_connection():
    """Test Gmail API connection."""
    logger.info("Testing Gmail API connection...")
    
    try:
        # Check if credentials file exists
        if not os.path.exists('google_credentials.json'):
            logger.error("google_credentials.json not found")
            return False
        
        # Check environment variables
        gmail_email = os.getenv('GMAIL_SENDER_EMAIL')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if not gmail_email:
            logger.error("GMAIL_SENDER_EMAIL not set")
            return False
        
        if not gmail_password:
            logger.error("GMAIL_APP_PASSWORD not set")
            return False
        
        logger.info(f"Gmail email: {gmail_email}")
        logger.info("Gmail app password: [SET]")
        logger.info("Credentials file: OK")
        
        # Test Gmail API authentication and email fetching
        try:
            from email_scanner import EmailScanner
            logger.info("Initializing EmailScanner...")
            scanner = EmailScanner()
            logger.info("Gmail API authentication: OK")
            
            # Test fetching emails
            logger.info("Testing email fetching...")
            
            # First try without a specific label
            try:
                emails = scanner.fetch_labeled_emails("INBOX", max_emails=1)
                logger.info(f"Email fetching from INBOX: OK (found {len(emails)} emails)")
            except Exception as e:
                logger.warning(f"INBOX fetch failed: {e}")
                # Try Job Alerts as fallback
                try:
                    emails = scanner.fetch_labeled_emails("Job Alerts", max_emails=1)
                    logger.info(f"Email fetching from Job Alerts: OK (found {len(emails)} emails)")
                except Exception as e2:
                    logger.error(f"Job Alerts fetch also failed: {e2}")
                    raise e2
            
            return True
            
        except Exception as e:
            logger.error(f"Gmail API test failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Gmail connection test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_gmail_connection()
    if success:
        logger.info("Gmail connection test: PASSED")
    else:
        logger.error("Gmail connection test: FAILED") 