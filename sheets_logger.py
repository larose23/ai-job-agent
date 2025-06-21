import os
import logging
from typing import Dict, List, Optional
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
from datetime import datetime
from helpers import logger, load_config
from logger import notify_slack
import traceback

load_dotenv()

def get_existing_job_urls(spreadsheet_id: str, sheet_name: str = "Jobs") -> list:
    """Fetches a list of existing job URLs from the Google Sheet to avoid duplicates."""
    try:
        config = load_config()
        credentials_path = config.get('credentials', {}).get('google', {}).get('sheets_credentials_json_path', 'google_service_account.json')
        gc = gspread.service_account(filename=credentials_path)
        sheet = gc.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(sheet_name)
        
        # Assumes the job URL is in column 6 (F)
        job_urls = worksheet.col_values(6)
        return job_urls[1:]  # Skip header
    except Exception as e:
        logger.error(f"Failed to get existing job URLs: {e}")
        return []

class SheetsLogger:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.logger = logger
        
        # Get Google Sheets config
        self.sheets_config = self.config.get('google_sheets', {})
        
        # Check if Google Sheets is enabled
        if not self.sheets_config.get('enabled', True):
            self.logger.info("Google Sheets integration disabled - using local logging only")
            self.gc = None
            self.spreadsheet = None
            self.jobs_sheet = None
            self.metrics_sheet = None
            return
            
        if not self.sheets_config.get('spreadsheet_id'):
            error_msg = "Google Sheets spreadsheet_id not found in config"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise ValueError(error_msg)
            
        try:
            credentials_path = self.config.get('credentials', {}).get('google', {}).get('sheets_credentials_json_path', 'google_service_account.json')
            self.gc = gspread.service_account(filename=credentials_path)
            self.spreadsheet = self.gc.open_by_key(self.sheets_config['spreadsheet_id'])
            logger.info(f"Connected to Google Sheet: {self.spreadsheet.title}")
        except Exception as e:
            error_msg = f"Failed to connect to Google Sheets: {e}"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise

        self.sheet_name = self.sheets_config['sheet_name']
        self.metrics_sheet_name = self.sheets_config.get('metrics_sheet_name', 'Metrics')

        # Open and cache sheets
        self.jobs_sheet = self.spreadsheet.worksheet(self.sheet_name)
        self.metrics_sheet = self.spreadsheet.worksheet(self.metrics_sheet_name)

    def get_existing_job_urls(self) -> List[str]:
        if not self.jobs_sheet:
            self.logger.info("Google Sheets disabled - returning empty job URLs list")
            return []
            
        try:
            urls = self.jobs_sheet.col_values(6)  # Column F is job URL
            return urls[1:]  # Skip header
        except Exception as e:
            self.logger.error(f"Error reading job URLs from sheet: {e}")
            return []

    def append_job_row(self, job: Dict, tailor_output: Optional[Dict] = None) -> None:
        if not self.jobs_sheet:
            self.logger.info(f"Google Sheets disabled - logging job locally: {job.get('title', 'Unknown')}")
            return
            
        try:
            row = [
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("source", ""),
                job.get("date_posted", ""),
                job.get("url", ""),
                tailor_output.get("tailored_resume", "") if tailor_output else "",
                tailor_output.get("tailored_cover_letter", "") if tailor_output else "",
                "",
                "",  # Recruiter email
                "",  # Applied?
                "",  # Cold email sent?
                "",  # Notes
            ]
            self.jobs_sheet.append_row(row, value_input_option="USER_ENTERED")
            self.logger.info(f"Appended job '{job.get('title', 'Unknown')}' to Google Sheet.")
        except Exception as e:
            self.logger.error(f"Failed to append job to sheet: {e}")

    def mark_applied(self, job_url: str) -> None:
        if not self.jobs_sheet:
            self.logger.info(f"Google Sheets disabled - marking job as applied locally: {job_url}")
            return
        self._update_cell_by_url(job_url, col_index=11, value="Yes")

    def mark_cold_email_sent(self, job_url: str) -> None:
        if not self.jobs_sheet:
            self.logger.info(f"Google Sheets disabled - marking cold email sent locally: {job_url}")
            return
        self._update_cell_by_url(job_url, col_index=12, value="Yes")

    def update_notes(self, job_url: str, notes: str) -> None:
        if not self.jobs_sheet:
            self.logger.info(f"Google Sheets disabled - updating notes locally: {job_url} - {notes}")
            return
        self._update_cell_by_url(job_url, col_index=13, value=notes)

    def update_recruiter_email(self, job_url: str, email: str) -> None:
        if not self.jobs_sheet:
            self.logger.info(f"Google Sheets disabled - updating recruiter email locally: {job_url} - {email}")
            return
        self._update_cell_by_url(job_url, col_index=10, value=email)

    def _update_cell_by_url(self, job_url: str, col_index: int, value: str) -> None:
        try:
            all_rows = self.jobs_sheet.get_all_values()
            for idx, row in enumerate(all_rows):
                if len(row) > 5 and row[5] == job_url:
                    self.jobs_sheet.update_cell(idx + 1, col_index, value)
                    self.logger.info(f"Updated column {col_index} for job '{job_url}'")
                    return
            self.logger.warning(f"Job URL not found in sheet: {job_url}")
        except Exception as e:
            self.logger.error(f"Error updating cell for job '{job_url}': {e}")

    def update_job_status(self, job_url: str, status: str) -> None:
        self._update_cell_by_url(job_url, col_index=11, value=status)

    def get_jobs_for_email_sending(self, applied=False, cold_email_sent=False) -> List[Dict]:
        try:
            jobs = []
            all_rows = self.jobs_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) < 12:
                    continue
                url = row[5]
                is_applied = row[10].strip().lower() == "yes"
                is_emailed = row[11].strip().lower() == "yes"

                if applied and not is_applied:
                    jobs.append({"url": url, "row": row})
                elif cold_email_sent and not is_emailed:
                    jobs.append({"url": url, "row": row})
            return jobs
        except Exception as e:
            self.logger.error(f"Failed to fetch jobs for emailing: {e}")
            return []

    def log_daily_metrics(self, metrics: Dict) -> None:
        """Log daily metrics to Google Sheets"""
        try:
            # Prepare metrics row
            today = datetime.now().strftime('%Y-%m-%d')
            metrics_row = [
                today,
                metrics.get('total_jobs', 0),
                metrics.get('new_jobs', 0),
                metrics.get('applications', 0),
                metrics.get('success_rate', 0),
                str(metrics.get('errors', []))  # Convert list to string for storage
            ]
            
            # Append to metrics sheet
            self.metrics_sheet.append_row(metrics_row)
            self.logger.info(f"Daily metrics logged successfully: {metrics}")
            
        except Exception as e:
            self.logger.error(f"Failed to log daily metrics: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def append_review_row(self, job: Dict) -> None:
        """Append a job to the Review sheet."""
        try:
            review_sheet_name = self.sheets_config.get('review_sheet_name', 'Review')
            review_sheet = self.spreadsheet.worksheet(review_sheet_name)
            row = [
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("apply_url", ""),
                "Pending",  # Status
                ""  # Notes
            ]
            review_sheet.append_row(row, value_input_option="USER_ENTERED")
            self.logger.info(f"Appended job '{job.get('title', 'Unknown')}' to Review sheet.")
        except Exception as e:
            self.logger.error(f"Failed to append job to Review sheet: {e}")

    def get_approved_review_jobs(self) -> list:
        """Fetch jobs marked as Approved in the Review sheet."""
        try:
            review_sheet_name = self.sheets_config.get('review_sheet_name', 'Review')
            review_sheet = self.spreadsheet.worksheet(review_sheet_name)
            all_rows = review_sheet.get_all_values()[1:]  # Skip header
            approved_jobs = []
            for row in all_rows:
                if len(row) >= 5 and row[4].strip().lower() == "approved":
                    approved_jobs.append({
                        "title": row[0],
                        "company": row[1],
                        "location": row[2],
                        "apply_url": row[3],
                        "status": row[4],
                        "notes": row[5] if len(row) > 5 else ""
                    })
            return approved_jobs
        except Exception as e:
            self.logger.error(f"Failed to fetch approved jobs from Review sheet: {e}")
            return []

def log_daily_metrics(metrics: Dict, spreadsheet_id: str, metrics_sheet_name: str) -> None:
    """Helper function to log daily metrics without instantiating SheetsLogger"""
    try:
        config = load_config()
        credentials_path = config.get('credentials', {}).get('google', {}).get('sheets_credentials_json_path', 'google_service_account.json')
        gc = gspread.service_account(filename=credentials_path)
        sheet = gc.open_by_key(spreadsheet_id)
        metrics_sheet = sheet.worksheet(metrics_sheet_name)
        
        # Prepare metrics row
        today = datetime.now().strftime('%Y-%m-%d')
        metrics_row = [
            today,
            metrics.get('total_jobs', 0),
            metrics.get('new_jobs', 0),
            metrics.get('applications', 0),
            metrics.get('success_rate', 0),
            str(metrics.get('errors', []))  # Convert list to string for storage
        ]
        
        # Append to metrics sheet
        metrics_sheet.append_row(metrics_row)
        logger.info(f"Daily metrics logged successfully: {metrics}")
        
    except Exception as e:
        logger.error(f"Failed to log daily metrics: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
