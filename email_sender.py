"""
Email sending automation module for the AI Job Agent application.
Handles sending cold outreach emails to recruiters using Gmail SMTP.
"""

import base64
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from dotenv import load_dotenv

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from helpers import load_config, retry_on_failure, validate_email
from logger import logger, notify_slack

load_dotenv()

class EmailSender:
    """Gmail email sender for cold outreach."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the email sender with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logger
        self.sender_email = os.getenv('GMAIL_SENDER_EMAIL')
        self.app_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if not self.sender_email or not self.app_password:
            error_msg = "Gmail credentials not found in environment variables"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Email sender initialized with {self.sender_email}")
        
        # Choose authentication method
        if self.config.get('gmail_app_password'):
            self.use_smtp = True
            logger.info("Using SMTP with app password for email sending")
        else:
            self.use_smtp = False
            self._authenticate_gmail_api()
            logger.info("Using Gmail API for email sending")
    
    def _authenticate_gmail_api(self) -> None:
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
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info("Successfully authenticated with Gmail API")
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Gmail API: {e}")
            raise
    
    @retry_on_failure(max_retries=3)
    def send_cold_email(
        self, 
        to_address: str, 
        subject: str, 
        body: str, 
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send a cold outreach email with optional attachments.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body text
            attachments: List of file paths to attach
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not validate_email(to_address):
            logger.error(f"Invalid email address: {to_address}")
            return False
        
        try:
            if self.use_smtp:
                return self._send_via_smtp(to_address, subject, body, attachments)
            else:
                return self._send_via_gmail_api(to_address, subject, body, attachments)
                
        except Exception as e:
            logger.error(f"Error sending email to {to_address}: {e}")
            return False
    
    def _send_via_smtp(
        self, 
        to_address: str, 
        subject: str, 
        body: str, 
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send email using SMTP with app password.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body text
            attachments: List of file paths to attach
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_address
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            attachment.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=os.path.basename(file_path)
                            )
                            msg.attach(attachment)
                    else:
                        logger.warning(f"Attachment file not found: {file_path}")
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_address} via SMTP")
            return True
            
        except Exception as e:
            logger.error(f"SMTP sending failed: {e}")
            return False
    
    def _send_via_gmail_api(
        self, 
        to_address: str, 
        subject: str, 
        body: str, 
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send email using Gmail API.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body text
            attachments: List of file paths to attach
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_address
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            attachment.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=os.path.basename(file_path)
                            )
                            msg.attach(attachment)
                    else:
                        logger.warning(f"Attachment file not found: {file_path}")
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            # Send via Gmail API
            message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to_address} via Gmail API (ID: {message['id']})")
            return True
            
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Gmail API sending failed: {e}")
            return False
    
    def create_cold_email_body(
        self, 
        job_title: str, 
        company: str, 
        cover_letter_text: str,
        applicant_name: str = "Job Applicant"
    ) -> str:
        """
        Create a professional cold email body.
        
        Args:
            job_title: Job title
            company: Company name
            cover_letter_text: Generated cover letter text
            applicant_name: Name of the applicant
            
        Returns:
            Formatted email body
        """
        email_body = f"""Dear Hiring Manager,

I hope this email finds you well. I am writing to express my strong interest in the {job_title} position at {company}.

{cover_letter_text}

I have attached my tailored resume for your review. I would welcome the opportunity to discuss how my background and skills align with your team's needs.

Thank you for your time and consideration. I look forward to hearing from you.

Best regards,
{applicant_name}

---
This email was sent as part of my job search process. If you have received this in error or would prefer not to receive such emails, please let me know.
"""
        return email_body
    
    def create_subject_line(self, job_title: str, company: str) -> str:
        """
        Create a professional subject line for cold emails.
        
        Args:
            job_title: Job title
            company: Company name
            
        Returns:
            Email subject line
        """
        return f"Application for {job_title} Position at {company}"
    
    def send_bulk_cold_emails(self, jobs_data: List[dict]) -> dict:
        """
        Send cold emails for multiple jobs.
        
        Args:
            jobs_data: List of job dictionaries with email details
            
        Returns:
            Dictionary with sending results
        """
        results = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for job_data in jobs_data:
            try:
                # Read cover letter content
                cover_letter_file = job_data.get('cover_letter_file', '')
                cover_letter_text = ""
                
                if cover_letter_file and os.path.exists(cover_letter_file):
                    with open(cover_letter_file, 'r', encoding='utf-8') as f:
                        cover_letter_text = f.read()
                        # Remove header lines if present
                        lines = cover_letter_text.split('\n')
                        if len(lines) > 3 and '=' in lines[2]:
                            cover_letter_text = '\n'.join(lines[4:])  # Skip header
                
                # Create email content
                subject = self.create_subject_line(
                    job_data.get('title', ''),
                    job_data.get('company', '')
                )
                
                body = self.create_cold_email_body(
                    job_data.get('title', ''),
                    job_data.get('company', ''),
                    cover_letter_text
                )
                
                # Prepare attachments
                attachments = []
                if job_data.get('cover_letter_file') and os.path.exists(job_data['cover_letter_file']):
                    attachments.append(job_data['cover_letter_file'])
                if job_data.get('delta_resume_file') and os.path.exists(job_data['delta_resume_file']):
                    attachments.append(job_data['delta_resume_file'])
                
                # Send email
                success = self.send_cold_email(
                    job_data.get('recruiter_email', ''),
                    subject,
                    body,
                    attachments
                )
                
                if success:
                    results['sent'] += 1
                    logger.info(f"Cold email sent for {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')}")
                else:
                    results['failed'] += 1
                    error_msg = f"Failed to send email for {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
                
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error processing job {job_data.get('title', 'Unknown')}: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Bulk email sending completed: {results['sent']} sent, {results['failed']} failed")
        return results
    
    def test_email_connection(self) -> bool:
        """
        Test email connection and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.use_smtp:
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(self.sender_email, self.app_password)
                logger.info("SMTP connection test successful")
                return True
            else:
                # Test Gmail API by getting user profile
                profile = self.service.users().getProfile(userId='me').execute()
                logger.info(f"Gmail API connection test successful for {profile.get('emailAddress', 'unknown')}")
                return True
                
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False


# Main functions for external use
def send_cold_email(
    to_address: str, 
    subject: str, 
    body: str, 
    attachments: Optional[List[str]] = None
) -> bool:
    """
    Send a cold outreach email.
    
    Args:
        to_address: Recipient email address
        subject: Email subject
        body: Email body text
        attachments: List of file paths to attach
        
    Returns:
        True if successful, False otherwise
    """
    sender = EmailSender()
    return sender.send_cold_email(to_address, subject, body, attachments)


def send_bulk_cold_emails(jobs_data: List[dict]) -> dict:
    """
    Send cold emails for multiple jobs.
    
    Args:
        jobs_data: List of job dictionaries
        
    Returns:
        Sending results dictionary
    """
    sender = EmailSender()
    return sender.send_bulk_cold_emails(jobs_data)


def test_email_setup() -> bool:
    """
    Test email configuration and connection.
    
    Returns:
        True if setup is working, False otherwise
    """
    sender = EmailSender()
    return sender.test_email_connection()


if __name__ == "__main__":
    # Test the email sender
    print("Testing email sender...")
    
    try:
        sender = EmailSender()
        
        # Test connection
        if sender.test_email_connection():
            print("Email connection test passed!")
        else:
            print("Email connection test failed!")
        
        # Test email creation
        subject = sender.create_subject_line("Software Engineer", "TechCorp")
        body = sender.create_cold_email_body(
            "Software Engineer",
            "TechCorp",
            "I am excited to apply for this position...",
            "John Doe"
        )
        
        print(f"Sample subject: {subject}")
        print(f"Sample body length: {len(body)} characters")
        
        # Uncomment to test actual email sending (requires valid recipient)
        # success = sender.send_cold_email(
        #     "test@example.com",
        #     subject,
        #     body
        # )
        # print(f"Test email sent: {success}")
        
        print("Email sender test completed!")
        
    except Exception as e:
        print(f"Email sender test failed: {e}")
        print("This is expected if email credentials are not configured.")

