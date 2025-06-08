"""
Email scanning and parsing module for the AI Job Agent application.
Handles reading job alert emails from Gmail and extracting job information.
"""

import base64
import email
import logging
import os
import re
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup

from helpers import load_config, retry_on_failure, hash_job


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
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Gmail API using service account."""
        try:
            credentials_path = self.config.get('google_credentials_json_path', './google_credentials.json')
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Google credentials file not found at {credentials_path}. "
                    "Please download it from Google Cloud Console."
                )
            
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/gmail.readonly',
                       'https://www.googleapis.com/auth/gmail.modify']
            )
            
            self.service = build('gmail', 'v1', credentials=credentials)
            self.logger.info("Successfully authenticated with Gmail API")
            
        except Exception as e:
            self.logger.error(f"Failed to authenticate with Gmail API: {e}")
            raise
    
    @retry_on_failure(max_retries=3)
    def fetch_labeled_emails(self, label: str, max_emails: int = 50) -> List[Dict]:
        """
        Fetch unread emails with a specific label from Gmail.
        
        Args:
            label: Gmail label to filter emails
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries with metadata and body
        """
        self.logger.info(f"Fetching emails with label '{label}'")
        
        try:
            # Get label ID
            labels_result = self.service.users().labels().list(userId='me').execute()
            labels = labels_result.get('labels', [])
            
            label_id = None
            for lbl in labels:
                if lbl['name'].lower() == label.lower():
                    label_id = lbl['id']
                    break
            
            if not label_id:
                self.logger.warning(f"Label '{label}' not found. Available labels: {[l['name'] for l in labels]}")
                return []
            
            # Search for unread emails with the label
            query = f'label:{label} is:unread'
            results = self.service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=max_emails
            ).execute()
            
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
            self.logger.error(f"Gmail API error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            raise
    
    def _get_email_content(self, message_id: str) -> Optional[Dict]:
        """
        Get the content of a specific email.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if error
        """
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id, 
                format='full'
            ).execute()
            
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
        
        # LinkedIn job alert patterns
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s+at\s+(?P<company>[^\n]+?)\s*\n.*?'
            r'(?P<location>[^\n]+?)\s*\n.*?'
            r'(?:https://www\.linkedin\.com/jobs/view/(?P<job_id>\d+))',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = job_pattern.finditer(email_body)
        
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            job_id = match.group('job_id')
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else ""
            
            # Extract salary if present
            salary_text = ""
            salary_match = re.search(
                r'(?:salary|pay|compensation)[:\s]*([^\n]+)',
                email_body[match.start():match.end()],
                re.IGNORECASE
            )
            if salary_match:
                salary_text = salary_match.group(1).strip()
            
            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'salary_text': salary_text,
                'job_url': job_url,
                'full_description': "",
                'source': 'LinkedIn Email'
            })
        
        return jobs
    
    def _parse_indeed_job_alert(self, email_body: str) -> List[Dict]:
        """Parse Indeed job alert emails."""
        jobs = []
        
        # Indeed job alert patterns
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s*\n\s*(?P<company>[^\n]+?)\s*\n\s*(?P<location>[^\n]+?)\s*\n.*?'
            r'(?:https://[a-z]{2}\.indeed\.com/viewjob\?jk=(?P<job_id>[a-zA-Z0-9]+))',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = job_pattern.finditer(email_body)
        
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            job_id = match.group('job_id')
            job_url = f"https://ae.indeed.com/viewjob?jk={job_id}" if job_id else ""
            
            # Extract salary if present
            salary_text = ""
            salary_match = re.search(
                r'(?:AED|CAD|USD)\s*[\d,]+(?:\s*-\s*(?:AED|CAD|USD)\s*[\d,]+)?',
                email_body[match.start():match.end()],
                re.IGNORECASE
            )
            if salary_match:
                salary_text = salary_match.group(0).strip()
            
            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'salary_text': salary_text,
                'job_url': job_url,
                'full_description': "",
                'source': 'Indeed Email'
            })
        
        return jobs
    
    def _parse_glassdoor_job_alert(self, email_body: str) -> List[Dict]:
        """Parse Glassdoor job alert emails."""
        jobs = []
        
        # Glassdoor job alert patterns
        job_pattern = re.compile(
            r'(?P<title>[^\n]+?)\s*\n\s*(?P<company>[^\n]+?)\s*\n\s*(?P<location>[^\n]+?)\s*\n.*?'
            r'(?:https://www\.glassdoor\.com/job-listing/[^\s]+)',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = job_pattern.finditer(email_body)
        
        for match in matches:
            title = match.group('title').strip()
            company = match.group('company').strip()
            location = match.group('location').strip()
            
            # Find the URL in the match
            url_match = re.search(r'https://www\.glassdoor\.com/job-listing/[^\s]+', 
                                email_body[match.start():match.end()])
            job_url = url_match.group(0) if url_match else ""
            
            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'salary_text': "",
                'job_url': job_url,
                'full_description': "",
                'source': 'Glassdoor Email'
            })
        
        return jobs
    
    def _parse_generic_job_alert(self, email_body: str) -> List[Dict]:
        """Parse generic job alert emails using common patterns."""
        jobs = []
        
        # Generic patterns for job information
        lines = email_body.split('\n')
        
        for i, line in enumerate(lines):
            # Look for job title patterns
            if any(keyword in line.lower() for keyword in ['engineer', 'manager', 'analyst', 'developer', 'specialist']):
                title = line.strip()
                
                # Look for company in next few lines
                company = ""
                location = ""
                job_url = ""
                
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    
                    # Company patterns
                    if not company and next_line and not any(char in next_line for char in ['http', '@', 'salary']):
                        company = next_line
                    
                    # Location patterns
                    elif not location and any(loc_word in next_line.lower() for loc_word in ['dubai', 'canada', 'remote', 'uae']):
                        location = next_line
                    
                    # URL patterns
                    elif 'http' in next_line:
                        url_match = re.search(r'https?://[^\s]+', next_line)
                        if url_match:
                            job_url = url_match.group(0)
                
                if title and company:
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'salary_text': "",
                        'job_url': job_url,
                        'full_description': "",
                        'source': 'Generic Email'
                    })
        
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
    Scan Gmail for job alert emails and extract job information.
    
    Args:
        label: Gmail label to filter emails (defaults to config value)
        max_emails: Maximum number of emails to process
        
    Returns:
        List of job dictionaries extracted from emails
    """
    scanner = EmailScanner()
    
    if label is None:
        label = scanner.config.get('job_alert_label', 'Job Alerts')
    
    # Fetch emails
    emails = scanner.fetch_labeled_emails(label, max_emails)
    
    # Parse jobs from all emails
    all_jobs = []
    for email_data in emails:
        jobs = scanner.parse_job_email(email_data['body'])
        all_jobs.extend(jobs)
    
    logging.getLogger(__name__).info(f"Extracted {len(all_jobs)} jobs from {len(emails)} emails")
    return all_jobs


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

