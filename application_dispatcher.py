"""
Application Dispatcher module for the AI Job Agent application.
Routes jobs to the correct application method: cold email, web automation, or manual review.
"""

import logging
from typing import Dict, Any
from logger import logger
from job_application import JobApplication
from main import send_cold_email
from sheets_logger import SheetsLogger

class ApplicationDispatcher:
    def __init__(self, config: Dict[str, Any], user_profile: Dict[str, Any]):
        self.config = config
        self.user_profile = user_profile
        self.sheets_logger = SheetsLogger(config_path=config.get('config_path', 'config.json'))

    async def dispatch(self, job: Dict[str, Any]):
        try:
            if self.config.get('review_before_apply', False):
                logger.info(f"Review-before-apply enabled. Writing job to Review sheet: {job.get('title')} at {job.get('company')}")
                self.sheets_logger.append_review_row(job)
                return 'review_queue'
            if job.get('recruiter_email'):
                logger.info(f"Dispatching cold email for job: {job.get('title')} at {job.get('company')}")
                try:
                    send_cold_email(
                        recruiter_email=job['recruiter_email'],
                        job=job,
                        user_profile=self.user_profile,
                        gmail_config=self.config.get('gmail', {})
                    )
                    self.sheets_logger.mark_cold_email_sent(job.get('job_url', job.get('apply_url', '')))
                except Exception as e:
                    logger.error(f"Failed to send cold email: {e}")
                    self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), f"Cold email failed: {e}")
                return 'cold_email'
            elif job.get('apply_url'):
                if not self.config.get('auto_apply_enabled', True):
                    logger.info(f"Auto-apply disabled. Logging job for manual review: {job.get('title')} at {job.get('company')}")
                    self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required (auto-apply off)")
                    return 'manual_review'
                logger.info(f"Dispatching web form automation for job: {job.get('title')} at {job.get('company')}")
                try:
                    async with JobApplication(config_path=self.config.get('config_path', 'config.json')) as app:
                        result = await app.apply_to_job(job, self.user_profile)
                    if result:
                        self.sheets_logger.mark_applied(job.get('job_url', job.get('apply_url', '')))
                    else:
                        self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Web form automation failed")
                except Exception as e:
                    logger.error(f"Web form automation failed: {e}")
                    self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), f"Web form automation failed: {e}")
                return 'web_form'
            else:
                logger.info(f"Job requires manual review: {job.get('title')} at {job.get('company')}")
                self.sheets_logger.update_notes(job.get('job_url', job.get('apply_url', '')), "Manual review required")
                return 'manual_review'
        except Exception as e:
            logger.error(f"Dispatcher error: {e}")
            return 'error' 