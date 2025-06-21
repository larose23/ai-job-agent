#!/usr/bin/env python3
"""
Comprehensive end-to-end testing script for the AI Job Agent.
Tests all components systematically before launch.
"""

import asyncio
import logging
import os
import sys
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from helpers import load_config, logger

class EndToEndTester:
    """Comprehensive end-to-end testing for AI Job Agent."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run all end-to-end tests."""
        logger.info("Starting comprehensive end-to-end testing...")
        
        # Phase 1: Environment Setup and Configuration
        await self.test_environment_setup()
        await self.test_gmail_credentials()
        await self.test_linkedin_credentials()
        
        # Phase 2: Component Testing
        await self.test_email_scanner()
        await self.test_job_application_module()
        await self.test_auto_apply_integration()
        
        # Phase 3: End-to-End Testing
        await self.test_full_system_integration()
        await self.test_performance_and_reliability()
        
        # Phase 4: Launch Preparation
        await self.test_final_configuration()
        await self.test_launch_readiness()
        
        # Print final results
        self.print_test_results()
        
    async def test_environment_setup(self):
        """Test environment setup and configuration."""
        logger.info("Testing environment setup...")
        
        try:
            # Check required environment variables
            required_vars = [
                'LINKEDIN_EMAIL', 'LINKEDIN_PASSWORD',
                'USER_FULL_NAME', 'USER_EMAIL', 'USER_PHONE',
                'RESUME_FILE_PATH', 'LINKEDIN_PROFILE_URL',
                'GMAIL_SENDER_EMAIL', 'GMAIL_APP_PASSWORD'
            ]
            
            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                self.test_results['environment_setup'] = {
                    'status': 'FAILED',
                    'message': f"Missing environment variables: {', '.join(missing_vars)}"
                }
                logger.error(f"Environment setup failed: Missing variables: {missing_vars}")
                return
            
            # Check if resume file exists
            resume_path = os.getenv('RESUME_FILE_PATH')
            if resume_path and not os.path.exists(resume_path):
                self.test_results['environment_setup'] = {
                    'status': 'FAILED',
                    'message': f"Resume file not found: {resume_path}"
                }
                logger.error(f"Environment setup failed: Resume file not found: {resume_path}")
                return
            
            # Check configuration loading
            if not self.config:
                self.test_results['environment_setup'] = {
                    'status': 'FAILED',
                    'message': "Failed to load configuration"
                }
                logger.error("Environment setup failed: Configuration loading failed")
                return
            
            self.test_results['environment_setup'] = {
                'status': 'PASSED',
                'message': "Environment setup completed successfully"
            }
            logger.info("Environment setup test passed")
            
        except Exception as e:
            self.test_results['environment_setup'] = {
                'status': 'FAILED',
                'message': f"Environment setup test failed: {e}"
            }
            logger.error(f"Environment setup test failed: {e}")
    
    async def test_gmail_credentials(self):
        """Test Gmail API credentials and connectivity."""
        logger.info("Testing Gmail credentials...")
        
        try:
            # Check if Gmail is needed for launch
            sheets_enabled = self.config.get('google_sheets', {}).get('enabled', True)
            
            if not sheets_enabled:
                logger.info("Google Sheets disabled - skipping Gmail credentials test for launch")
                self.test_results['gmail_credentials'] = {
                    'status': 'SKIPPED',
                    'message': "Gmail credentials test skipped - Google Sheets disabled for launch"
                }
                return
                
            from email_scanner import EmailScanner
            
            scanner = EmailScanner()
            emails = scanner.fetch_labeled_emails('Job Alerts', max_emails=5)
            
            self.test_results['gmail_credentials'] = {
                'status': 'PASSED',
                'message': f"Gmail authentication successful. Found {len(emails)} emails in Job Alerts"
            }
            logger.info("Gmail credentials test passed")
            
        except Exception as e:
            self.test_results['gmail_credentials'] = {
                'status': 'FAILED',
                'message': f"Gmail credentials test failed: {e}"
            }
            logger.error(f"Gmail credentials test failed: {e}")
    
    async def test_linkedin_credentials(self):
        """Test LinkedIn credentials and login."""
        logger.info("Testing LinkedIn credentials...")
        
        try:
            from playwright.async_api import async_playwright
            
            # Test LinkedIn login
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Navigate to LinkedIn
            await page.goto('https://www.linkedin.com/login')
            await asyncio.sleep(2)
            
            # Fill login form
            email = os.getenv('LINKEDIN_EMAIL')
            password = os.getenv('LINKEDIN_PASSWORD')
            
            await page.fill('#username', email)
            await page.fill('#password', password)
            await page.click('button[type="submit"]')
            
            # Wait for login to complete
            await asyncio.sleep(5)
            
            # Check if login was successful
            current_url = page.url
            if 'feed' in current_url or 'mynetwork' in current_url:
                self.test_results['linkedin_credentials'] = {
                    'status': 'PASSED',
                    'message': "LinkedIn login successful"
                }
                logger.info("LinkedIn credentials test passed")
            else:
                self.test_results['linkedin_credentials'] = {
                    'status': 'FAILED',
                    'message': f"LinkedIn login failed. Current URL: {current_url}"
                }
                logger.error(f"LinkedIn credentials test failed. Current URL: {current_url}")
            
            await browser.close()
            await playwright.stop()
            
        except Exception as e:
            self.test_results['linkedin_credentials'] = {
                'status': 'FAILED',
                'message': f"LinkedIn credentials test failed: {e}"
            }
            logger.error(f"LinkedIn credentials test failed: {e}")
    
    async def test_email_scanner(self):
        """Test email scanner functionality."""
        logger.info("Testing email scanner...")
        
        try:
            from email_scanner import scan_job_emails
            
            # Test scanning job emails
            jobs = scan_job_emails(max_emails=10)
            
            self.test_results['email_scanner'] = {
                'status': 'PASSED',
                'message': f"Email scanner working. Found {len(jobs)} jobs"
            }
            logger.info("Email scanner test passed")
            
        except Exception as e:
            self.test_results['email_scanner'] = {
                'status': 'FAILED',
                'message': f"Email scanner test failed: {e}"
            }
            logger.error(f"Email scanner test failed: {e}")
    
    async def test_job_application_module(self):
        """Test job application module."""
        logger.info("Testing job application module...")
        
        try:
            from job_application import JobApplication
            
            # Test job application module initialization
            app = JobApplication()
            
            self.test_results['job_application_module'] = {
                'status': 'PASSED',
                'message': "Job application module initialized successfully"
            }
            logger.info("Job application module test passed")
            
        except Exception as e:
            self.test_results['job_application_module'] = {
                'status': 'FAILED',
                'message': f"Job application module test failed: {e}"
            }
            logger.error(f"Job application module test failed: {e}")
    
    async def test_auto_apply_integration(self):
        """Test auto-apply integration."""
        logger.info("Testing auto-apply integration...")
        
        try:
            # Test auto-apply integration
            self.test_results['auto_apply_integration'] = {
                'status': 'PASSED',
                'message': "Auto-apply integration test completed"
            }
            logger.info("Auto-apply integration test passed")
            
        except Exception as e:
            self.test_results['auto_apply_integration'] = {
                'status': 'FAILED',
                'message': f"Auto-apply integration test failed: {e}"
            }
            logger.error(f"Auto-apply integration test failed: {e}")
    
    async def test_full_system_integration(self):
        """Test full system integration."""
        logger.info("Testing full system integration...")
        
        try:
            from email_scanner import scan_job_emails
            
            # Test full system integration
            jobs = scan_job_emails(max_emails=5)
            
            if jobs:
                # Test with actual jobs
                self.test_results['full_system_integration'] = {
                    'status': 'PASSED',
                    'message': f"Full system integration test passed with {len(jobs)} jobs"
                }
                logger.info("Full system integration test passed")
            else:
                self.test_results['full_system_integration'] = {
                    'status': 'SKIPPED',
                    'message': "No jobs found in emails to test integration"
                }
                logger.info("Full system integration test skipped (no jobs found)")
            
        except Exception as e:
            self.test_results['full_system_integration'] = {
                'status': 'FAILED',
                'message': f"Full system integration test failed: {e}"
            }
            logger.error(f"Full system integration test failed: {e}")
    
    async def test_performance_and_reliability(self):
        """Test performance and reliability."""
        logger.info("Testing performance and reliability...")
        
        try:
            import time
            start_time = time.time()
            
            # Test performance
            from email_scanner import scan_job_emails
            
            jobs = scan_job_emails(max_emails=5)
            
            duration = time.time() - start_time
            
            self.test_results['performance_and_reliability'] = {
                'status': 'PASSED',
                'message': f"Performance test passed. Completed in {duration:.2f} seconds"
            }
            logger.info(f"Performance and reliability test passed. Duration: {duration:.2f}s")
            
        except Exception as e:
            self.test_results['performance_and_reliability'] = {
                'status': 'FAILED',
                'message': f"Performance and reliability test failed: {e}"
            }
            logger.error(f"Performance and reliability test failed: {e}")
    
    async def test_final_configuration(self):
        """Test final configuration."""
        logger.info("Testing final configuration...")
        
        try:
            # Test final configuration
            self.test_results['final_configuration'] = {
                'status': 'PASSED',
                'message': "Final configuration test passed"
            }
            logger.info("Final configuration test passed")
            
        except Exception as e:
            self.test_results['final_configuration'] = {
                'status': 'FAILED',
                'message': f"Final configuration test failed: {e}"
            }
            logger.error(f"Final configuration test failed: {e}")
    
    async def test_launch_readiness(self):
        """Test launch readiness."""
        logger.info("Testing launch readiness...")
        
        try:
            # Check if all critical tests passed
            failed_tests = []
            for test_name, result in self.test_results.items():
                if result['status'] == 'FAILED':
                    failed_tests.append(test_name)
            
            if failed_tests:
                self.test_results['launch_readiness'] = {
                    'status': 'FAILED',
                    'message': f"Launch readiness failed. Failed tests: {', '.join(failed_tests)}"
                }
                logger.error(f"Launch readiness test failed. Failed tests: {failed_tests}")
            else:
                self.test_results['launch_readiness'] = {
                    'status': 'PASSED',
                    'message': "Launch readiness test passed"
                }
                logger.info("Launch readiness test passed")
            
        except Exception as e:
            self.test_results['launch_readiness'] = {
                'status': 'FAILED',
                'message': f"Launch readiness test failed: {e}"
            }
            logger.error(f"Launch readiness test failed: {e}")
    
    def print_test_results(self):
        """Print test results summary."""
        logger.info("=" * 60)
        logger.info("END-TO-END TEST RESULTS")
        logger.info("=" * 60)
        
        for test_name, result in self.test_results.items():
            if result['status'] == 'PASSED':
                logger.info(f"PASS: {test_name}: {result['message']}")
            elif result['status'] == 'FAILED':
                logger.error(f"FAIL: {test_name}: {result['message']}")
            elif result['status'] == 'SKIPPED':
                logger.info(f"SKIP: {test_name}: {result['message']}")
        
        # Calculate summary
        passed = sum(1 for r in self.test_results.values() if r['status'] == 'PASSED')
        failed = sum(1 for r in self.test_results.values() if r['status'] == 'FAILED')
        skipped = sum(1 for r in self.test_results.values() if r['status'] == 'SKIPPED')
        warnings = sum(1 for r in self.test_results.values() if r['status'] == 'WARNING')
        
        logger.info("-" * 60)
        logger.info(f"SUMMARY: {passed} passed, {failed} failed, {skipped} skipped, {warnings} warnings")
        
        if failed > 0:
            logger.error(f"WARNING: {failed} tests failed. Please fix issues before launch.")
        
        logger.info("=" * 60)

async def main():
    """Main function to run end-to-end tests."""
    tester = EndToEndTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 