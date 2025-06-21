"""
Email scanning and parsing module for the AI Job Agent application.
Handles reading job alert emails from Gmail and extracting job information.
"""

import base64
import email
import logging
import os
import re
import traceback
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup

from helpers import load_config, hash_job

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class EmailScanner:
    """Gmail email scanner for job alerts."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the email scanner with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logging.getLogger(__name__)
        self.service = None
        self.credentials_path = self._get_credentials_path()
        self._authenticate()
    
    def _get_credentials_path(self) -> str:
        """
        Get the path to Google credentials file for Gmail OAuth.
        """
        creds_path = self.config.get('credentials', {}).get('google', {}).get('gmail_credentials_json_path')
        if not creds_path:
            raise ValueError("Google Gmail credentials path not found in config")
        # Handle environment variable
        if creds_path.startswith('${') and creds_path.endswith('}'):
            env_var = creds_path[2:-1]
            creds_path = os.getenv(env_var)
            if not creds_path:
                raise ValueError(f"Environment variable {env_var} not set")
        if not os.path.isabs(creds_path):
            creds_path = os.path.abspath(creds_path)
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Google Gmail credentials file not found at: {creds_path}")
        return creds_path
    
    def _authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth2.
        
        This method:
        1. Checks for existing token
        2. Refreshes token if expired
        3. Creates new token if needed
        4. Builds Gmail service
        
        Raises:
            Exception: If authentication fails
        """
        try:
            creds = None
            token_path = 'token.json'
            
            # Check for existing token
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                    self.logger.debug("Loaded existing token")
                except Exception as e:
                    self.logger.warning(f"Failed to load token.json: {e}")
                    # If token is invalid, remove it
                    os.remove(token_path)
            
            # Handle token refresh or creation
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        self.logger.debug("Refreshed expired token")
                    except Exception as e:
                        self.logger.warning(f"Failed to refresh token: {e}")
                        creds = None
                
                if not creds:
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_path, SCOPES)
                        creds = flow.run_local_server(port=0)
                        self.logger.debug("Created new token")
                    except Exception as e:
                        error_msg = f"Failed to create OAuth flow: {e}"
                        self.logger.error(error_msg)
                        self.logger.error("Make sure google_credentials.json is for an installed app")
                        raise Exception(error_msg)
                
                # Save the credentials for the next run
                try:
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                    self.logger.debug("Saved new token")
                except Exception as e:
                    self.logger.error(f"Failed to save token: {e}")
                    # Continue even if token save fails
            
            # Build Gmail service
            try:
                self.service = build('gmail', 'v1', credentials=creds)
                self.logger.info("Successfully authenticated with Gmail API")
            except Exception as e:
                error_msg = f"Failed to build Gmail service: {e}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to authenticate with Gmail API: {e}"
            self.logger.error(error_msg)
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(error_msg)
    
    def fetch_labeled_emails(self, label: str, max_emails: int = 50) -> List[Dict]:
        """
        Fetch unread emails with a specific label from Gmail.
        
        Args:
            label: Gmail label to filter emails
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries with metadata and body
            
        Raises:
            Exception: If email fetching fails
        """
        self.logger.info(f"Fetching emails with label '{label}'")
        
        try:
            # Get label ID with retry logic
            labels_result = self._retry_api_call(
                lambda: self.service.users().labels().list(userId='me').execute(),
                "fetching labels"
            )
            labels = labels_result.get('labels', [])
            
            label_id = None
            for lbl in labels:
                if lbl['name'].lower() == label.lower():
                    label_id = lbl['id']
                    break
            
            if not label_id:
                error_msg = f"Label '{label}' not found. Available labels: {[l['name'] for l in labels]}"
                self.logger.warning(error_msg)
                return []
            
            # Search for unread emails with the label
            query = f'label:{label} is:unread'
            results = self._retry_api_call(
                lambda: self.service.users().messages().list(
                    userId='me', 
                    q=query, 
                    maxResults=max_emails
                ).execute(),
                "searching messages"
            )
            
            messages = results.get('messages', [])
            self.logger.info(f"Found {len(messages)} unread emails with label '{label}'")
            
            emails = []
            for message in messages:
                try:
                    email_data = self._get_email_content(message['id'])
                    if email_data:
                        emails.append(email_data)
                        # Mark as read
                        self._mark_email_as_read(message['id'])
                        
                except Exception as e:
                    self.logger.warning(f"Error processing email {message['id']}: {e}")
                    continue
            
            return emails
            
        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error fetching emails: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def _retry_api_call(self, api_call, operation_name, max_retries=3, base_delay=2):
        """
        Retry an API call with exponential backoff.
        
        Args:
            api_call: Lambda function containing the API call
            operation_name: Name of the operation for logging
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            
        Returns:
            API call result
            
        Raises:
            Exception: If all retries fail
        """
        import time
        
        for attempt in range(max_retries + 1):
            try:
                return api_call()
            except Exception as e:
                if attempt == max_retries:
                    raise e
                
                delay = base_delay * (2 ** attempt)
                self.logger.warning(f"API call failed for {operation_name} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                self.logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
    
    def _get_email_content(self, message_id: str) -> Optional[Dict]:
        """
        Get the content of a specific email.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if error
        """
        try:
            message = self._retry_api_call(
                lambda: self.service.users().messages().get(
                    userId='me', 
                    id=message_id, 
                    format='full'
                ).execute(),
                f"fetching email {message_id}"
            )
            
            headers = message['payload'].get('headers', [])
            
            # Extract headers
            subject = ""
            sender = ""
            date = ""
            
            for header in headers:
                name = header['name'].lower()
                if name == 'subject':
                    subject = header['value']
                elif name == 'from':
                    sender = header['value']
                elif name == 'date':
                    date = header['value']
            
            # Extract body
            body = self._extract_email_body(message['payload'])
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body
            }
            
        except Exception as e:
            self.logger.warning(f"Error getting email content for {message_id}: {e}")
            return None
    
    def _extract_email_body(self, payload: Dict) -> str:
        """
        Extract email body from Gmail message payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Email body text
        """
        body = ""
        
        if 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body'].get('data', '')
                    if data:
                        html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                        # Convert HTML to text
                        soup = BeautifulSoup(html_content, 'html.parser')
                        body += soup.get_text()
        else:
            # Single part message
            if payload['mimeType'] in ['text/plain', 'text/html']:
                data = payload['body'].get('data', '')
                if data:
                    content = base64.urlsafe_b64decode(data).decode('utf-8')
                    if payload['mimeType'] == 'text/html':
                        soup = BeautifulSoup(content, 'html.parser')
                        body = soup.get_text()
                    else:
                        body = content
        
        return body.strip()
    
    def _mark_email_as_read(self, message_id: str) -> None:
        """
        Mark an email as read.
        
        Args:
            message_id: Gmail message ID
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
        except Exception as e:
            self.logger.warning(f"Error marking email {message_id} as read: {e}")
    
    def parse_job_email(self, email_body: str) -> List[Dict]:
        """
        Parse job information from email body.
        
        Args:
            email_body: Email body text
            
        Returns:
            List of job dictionaries extracted from email
        """
        jobs = []
        
        # Common job email patterns
        patterns = [
            self._parse_linkedin_job_alert,
            self._parse_indeed_job_alert,
            self._parse_glassdoor_job_alert,
            self._parse_generic_job_alert
        ]
        
        for pattern_func in patterns:
            try:
                parsed_jobs = pattern_func(email_body)
                jobs.extend(parsed_jobs)
            except Exception as e:
                self.logger.warning(f"Error with pattern {pattern_func.__name__}: {e}")
                continue
        
        # Deduplicate jobs
        unique_jobs = []
        seen_hashes = set()
        
        for job in jobs:
            job_hash = hash_job(
                job.get('title', ''),
                job.get('company', ''),
                job.get('location', '')
            )
            
            if job_hash not in seen_hashes:
                unique_jobs.append(job)
                seen_hashes.add(job_hash)
        
        self.logger.info(f"Parsed {len(unique_jobs)} unique jobs from email")
        return unique_jobs
    
    def _parse_linkedin_job_alert(self, email_body: str) -> List[Dict]:
        """Parse LinkedIn job alert emails."""
        jobs = []
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s+at\s+(?P<company>[^\n]+?)\s*\n.*?'
            r'(?P<location>[^\n]+?)\s*\n.*?'
            r'(https://www\.linkedin\.com/jobs/view/(?P<job_id>\d+))',
            re.DOTALL | re.IGNORECASE
        )
        matches = job_pattern.finditer(email_body)
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            job_url = match.group(4).strip()
            apply_url = ''
            # Look for a direct apply link (if present and different)
            apply_link_match = re.search(r'(https://www\.linkedin\.com/jobs/apply/[^\s]+)', email_body)
            if apply_link_match:
                apply_url = apply_link_match.group(1).strip()
                if apply_url == job_url:
                    apply_url = ''
            salary_text = ""
            salary_match = re.search(
                r'(?:salary|pay|compensation)[:\s]*([^\n]+)',
                email_body[match.start():match.end()],
                re.IGNORECASE
            )
            if salary_match:
                salary_text = salary_match.group(1).strip()
            job = {
                'title': title,
                'company': company,
                'location': location,
                'salary_text': salary_text,
                'job_url': job_url,
                'full_description': "",
                'source': 'LinkedIn Email'
            }
            job['apply_url'] = apply_url or job_url
            jobs.append(job)
        return jobs
    
    def _parse_indeed_job_alert(self, email_body: str) -> List[Dict]:
        """Parse Indeed job alert emails."""
        jobs = []
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s*\n\s*(?P<company>[^\n]+?)\s*\n\s*(?P<location>[^\n]+?)\s*\n.*?'
            r'(https://[a-z]{2}\.indeed\.com/viewjob\?jk=(?P<job_id>[a-zA-Z0-9]+))',
            re.DOTALL | re.IGNORECASE
        )
        matches = job_pattern.finditer(email_body)
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            job_url = match.group(4).strip()
            apply_url = ''
            # Look for a direct apply link (if present and different)
            apply_link_match = re.search(r'(https://[a-z]{2}\.indeed\.com/applystart/[^\s]+)', email_body)
            if apply_link_match:
                apply_url = apply_link_match.group(1).strip()
                if apply_url == job_url:
                    apply_url = ''
            salary_text = ""
            salary_match = re.search(
                r'(?:AED|CAD|USD)\s*[\d,]+(?:\s*-\s*(?:AED|CAD|USD)\s*[\d,]+)?',
                email_body[match.start():match.end()],
                re.IGNORECASE
            )
            if salary_match:
                salary_text = salary_match.group(0).strip()
            job = {
                'title': title,
                'company': company,
                'location': location,
                'salary_text': salary_text,
                'job_url': job_url,
                'full_description': "",
                'source': 'Indeed Email'
            }
            job['apply_url'] = apply_url or job_url
            jobs.append(job)
        return jobs
    
    def _parse_glassdoor_job_alert(self, email_body: str) -> List[Dict]:
        """Parse Glassdoor job alert emails."""
        jobs = []
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s*\n\s*(?P<company>[^\n]+?)\s*\n\s*(?P<location>[^\n]+?)\s*\n.*?'
            r'(https://www\.glassdoor\.com/job-listing/[^\s]+)',
            re.DOTALL | re.IGNORECASE
        )
        matches = job_pattern.finditer(email_body)
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            job_url = match.group(4).strip()
            apply_url = ''
            # Look for a direct apply link (if present and different)
            apply_link_match = re.search(r'(https://www\.glassdoor\.com/partner/jobListing/applyJobListing.htm\?jobListingId=\d+)', email_body)
            if apply_link_match:
                apply_url = apply_link_match.group(1).strip()
                if apply_url == job_url:
                    apply_url = ''
            job = {
                'title': title,
                'company': company,
                'location': location,
                'salary_text': "",
                'job_url': job_url,
                'full_description': "",
                'source': 'Glassdoor Email'
            }
            job['apply_url'] = apply_url or job_url
            jobs.append(job)
        return jobs
    
    def _parse_generic_job_alert(self, email_body: str) -> List[Dict]:
        """Parse generic job alert emails using common patterns."""
        jobs = []
        lines = email_body.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['engineer', 'manager', 'analyst', 'developer', 'specialist']):
                title = line.strip()
                company = ""
                location = ""
                job_url = ""
                apply_url = ""
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    if not company and next_line and not any(char in next_line for char in ['http', '@', 'salary']):
                        company = next_line
                    elif not location and any(loc_word in next_line.lower() for loc_word in ['dubai', 'canada', 'remote', 'uae']):
                        location = next_line
                    elif 'http' in next_line:
                        url_match = re.search(r'https?://[^\s]+', next_line)
                        if url_match:
                            if not job_url:
                                job_url = url_match.group(0)
                            else:
                                apply_url = url_match.group(0)
                if title and company:
                    job = {
                        'title': title,
                        'company': company,
                        'location': location,
                        'salary_text': "",
                        'job_url': job_url,
                        'full_description': "",
                        'source': 'Generic Email'
                    }
                    job['apply_url'] = apply_url or job_url
                    jobs.append(job)
        return jobs


# Main functions for external use
def fetch_labeled_emails(label: str, max_emails: int = 50) -> List[Dict]:
    """
    Fetch emails with a specific label.
    
    Args:
        label: Gmail label to filter emails
        max_emails: Maximum number of emails to fetch
        
    Returns:
        List of email dictionaries
    """
    scanner = EmailScanner()
    return scanner.fetch_labeled_emails(label, max_emails)


def parse_job_email(email_body: str) -> List[Dict]:
    """
    Parse job information from email body.
    
    Args:
        email_body: Email body text
        
    Returns:
        List of job dictionaries
    """
    scanner = EmailScanner()
    return scanner.parse_job_email(email_body)


def scan_job_emails(label: str = None, max_emails: int = 50) -> List[Dict]:
    """
    Scan job alert emails and extract job information.
    
    Args:
        label: Gmail label to filter emails (default: from config)
        max_emails: Maximum number of emails to process
        
    Returns:
        List of job dictionaries
    """
    scanner = EmailScanner()
    
    # If authentication failed, return empty list
    if not scanner.service:
        logger.warning("Skipping email scanning due to authentication failure")
        return []
    
    try:
        # Use label from config if not specified
        if not label:
            label = scanner.config.get('gmail_label', 'Job Alerts')
        
        emails = scanner.fetch_labeled_emails(label, max_emails)
        jobs = []
        
        for email in emails:
            try:
                email_jobs = scanner.parse_job_email(email['body'])
                jobs.extend(email_jobs)
            except Exception as e:
                logger.error(f"Error parsing email {email.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Found {len(jobs)} jobs in {len(emails)} emails")
        return jobs
        
    except Exception as e:
        logger.error(f"Error scanning job emails: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []


if __name__ == "__main__":
    # Test the email scanner
    import os
    
    print("Testing email scanner...")
    
    # Test email parsing with sample data
    sample_email = """
    New Job Alert from LinkedIn
    
    Senior AI Engineer at TechCorp
    Dubai, UAE
    AED 15,000 - 20,000 per month
    https://www.linkedin.com/jobs/view/12345
    
    Data Scientist at DataCorp
    Remote Canada
    CAD 80,000 - 100,000 per year
    https://www.linkedin.com/jobs/view/67890
    """
    
    scanner = EmailScanner()
    jobs = scanner.parse_job_email(sample_email)
    print(f"Parsed {len(jobs)} jobs from sample email")
    
    for job in jobs:
        print(f"- {job['title']} at {job['company']} ({job['location']})")
    
    # Test Gmail API (requires authentication)
    try:
        emails = scan_job_emails(max_emails=5)
        print(f"Scanned {len(emails)} jobs from Gmail")
    except Exception as e:
        print(f"Gmail scanning test failed (expected if not authenticated): {e}")

