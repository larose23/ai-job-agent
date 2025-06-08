import os
import logging
from typing import Dict, List, Optional
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
from datetime import datetime
from helpers import logger, retry_on_failure
from logger import notify_slack
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()


def get_existing_job_urls(sheet_url: str, worksheet_name: str = "Jobs") -> list:
    """Fetches a list of existing job URLs from the Google Sheet to avoid duplicates."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("./google_credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet(worksheet_name)

    # Assumes the job URL is in the first column
    job_urls = worksheet.col_values(1)
    return job_urls


class SheetsLogger:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.logger = logger
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        
        if not self.spreadsheet_id:
            error_msg = "Google Sheets ID not found in environment variables"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise ValueError(error_msg)
            
        try:
            self.gc = gspread.service_account(filename='google_credentials.json')
            self.spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            logger.info(f"Connected to Google Sheet: {self.spreadsheet.title}")
        except Exception as e:
            error_msg = f"Failed to connect to Google Sheets: {e}"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise

        self.sheet_name = self.config["sheet_name"]
        self.metrics_sheet_name = self.config["metrics_sheet_name"]

        # Open and cache sheets
        self.jobs_sheet = self.spreadsheet.worksheet(self.sheet_name)
        self.metrics_sheet = self.spreadsheet.worksheet(self.metrics_sheet_name)

    @retry_on_failure
    def get_existing_job_urls(self) -> List[str]:
        try:
            urls = self.jobs_sheet.col_values(6)  # Assuming column 6 is job URL
            return urls[1:]  # Skip header
        except Exception as e:
            self.logger.error(f"Error reading job URLs from sheet: {e}")
            return []

    @retry_on_failure
    def append_job_row(self, job: Dict, tailor_output: Optional[Dict] = None) -> None:
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

    @retry_on_failure
    def mark_applied(self, job_url: str) -> None:
        self._update_cell_by_url(job_url, col_index=11, value="Yes")

    @retry_on_failure
    def mark_cold_email_sent(self, job_url: str) -> None:
        self._update_cell_by_url(job_url, col_index=12, value="Yes")

    @retry_on_failure
    def update_notes(self, job_url: str, notes: str) -> None:
        self._update_cell_by_url(job_url, col_index=13, value=notes)

    @retry_on_failure
    def update_recruiter_email(self, job_url: str, email: str) -> None:
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

    @retry_on_failure
    def update_job_status(self, job_url: str, status: str) -> None:
        self._update_cell_by_url(job_url, col_index=11, value=status)

    @retry_on_failure
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

    @retry_on_failure
    def log_daily_metrics(self, total_found: int, total_applied: int, total_emailed: int) -> None:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            row = [today, str(total_found), str(total_applied), str(total_emailed)]
            self.metrics_sheet.append_row(row, value_input_option="USER_ENTERED")
            self.logger.info(f"Logged metrics for {today}")
        except Exception as e:
            self.logger.error(f"Failed to log metrics: {e}")
