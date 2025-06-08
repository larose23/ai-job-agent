"""
Gmail email sending module for the AI Job Agent application.

This module provides the GmailSender class that handles:
1. Sending individual emails via Gmail SMTP
2. Sending bulk emails with templates
3. Handling attachments and HTML content
4. Error handling and retry logic

Example usage:
    sender = GmailSender("user@gmail.com", "app_password")
    sender.send_email(
        to_email="recipient@example.com",
        subject="Test Email",
        body="<h1>Hello</h1><p>This is a test.</p>"
    )
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any, Union, TypedDict

from helpers import (
    retry_network,
    retry_auth,
    safe_operation,
    logger,
    notify_slack
)

class AttachmentDict(TypedDict):
    """Type definition for email attachment dictionary."""
    filename: str
    content: str

class RecipientDict(TypedDict):
    """Type definition for email recipient dictionary."""
    email: str
    data: Dict[str, Any]

class BulkEmailResults(TypedDict):
    """Type definition for bulk email results dictionary."""
    total: int
    success: int
    failed: int
    errors: List[Dict[str, str]]

class GmailSender:
    """
    Gmail email sender with retry logic and bulk sending capabilities.
    
    This class provides methods for:
    1. Sending individual emails with HTML support
    2. Sending bulk emails with templates
    3. Handling attachments
    4. Managing CC and BCC recipients
    5. Error handling and retry logic
    
    Attributes:
        email (str): Gmail address to send from
        app_password (str): Gmail app password for authentication
        smtp_server (str): SMTP server address
        smtp_port (int): SMTP server port
    """
    
    def __init__(self, email: str, app_password: str) -> None:
        """
        Initialize Gmail sender with credentials.
        
        Args:
            email: Gmail address to send from
            app_password: Gmail app password for authentication
            
        Example:
            sender = GmailSender("user@gmail.com", "app_password")
        """
        self.email = email
        self.app_password = app_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
    @retry_auth
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[AttachmentDict]] = None
    ) -> bool:
        """
        Send an email using Gmail SMTP with retry logic.
        
        This method:
        1. Creates a multipart email message
        2. Adds HTML body content
        3. Handles CC and BCC recipients
        4. Attaches files if provided
        5. Sends the email via SMTP
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (HTML supported)
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)
            attachments: List of attachment dictionaries with:
                - filename: Name of the file
                - content: File content as string
                
        Returns:
            bool: True if email was sent successfully
            
        Raises:
            Exception: If email sending fails after retries
            
        Example:
            sender.send_email(
                to_email="recipient@example.com",
                subject="Test Email",
                body="<h1>Hello</h1><p>This is a test.</p>",
                cc=["cc@example.com"],
                attachments=[{
                    'filename': 'test.txt',
                    'content': 'Hello World'
                }]
            )
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add CC and BCC
            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
                
            # Add body
            msg.attach(MIMEText(body, 'html'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEText(attachment['content'])
                    part.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=attachment['filename']
                    )
                    msg.attach(part)
                    
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email, self.app_password)
                
                # Get all recipients
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                    
                # Send email
                server.send_message(msg, self.email, recipients)
                
            logger.info(f"Successfully sent email to {to_email}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def send_bulk_emails(
        self,
        recipients: List[RecipientDict],
        subject: str,
        body_template: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> BulkEmailResults:
        """
        Send bulk emails with retry logic.
        
        This method:
        1. Iterates through recipient list
        2. Formats email body using template and recipient data
        3. Sends individual emails
        4. Tracks success and failure counts
        5. Reports errors for failed sends
        
        Args:
            recipients: List of recipient dictionaries with:
                - email: Recipient email address
                - data: Dictionary of template variables
            subject: Email subject
            body_template: Email body template with placeholders
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)
            
        Returns:
            BulkEmailResults: Dictionary containing:
                - total: Total number of emails attempted
                - success: Number of successful sends
                - failed: Number of failed sends
                - errors: List of error dictionaries with:
                    - email: Failed recipient email
                    - error: Error message
                    
        Example:
            results = sender.send_bulk_emails(
                recipients=[
                    {
                        'email': 'user1@example.com',
                        'data': {'name': 'User 1'}
                    },
                    {
                        'email': 'user2@example.com',
                        'data': {'name': 'User 2'}
                    }
                ],
                subject="Hello {name}",
                body_template="<h1>Hello {name}</h1><p>Welcome!</p>"
            )
        """
        results: BulkEmailResults = {
            'total': len(recipients),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for recipient in recipients:
            try:
                # Format body with recipient data
                body = body_template.format(**recipient['data'])
                
                # Send email
                success = self.send_email(
                    to_email=recipient['email'],
                    subject=subject,
                    body=body,
                    cc=cc,
                    bcc=bcc
                )
                
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'email': recipient['email'],
                        'error': 'Email sending failed'
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'email': recipient['email'],
                    'error': str(e)
                })
                
        # Log results
        logger.info(
            f"Bulk email sending completed: "
            f"{results['success']} successful, "
            f"{results['failed']} failed"
        )
        
        # Notify on failures
        if results['failed'] > 0:
            notify_slack(
                f"Bulk email sending had {results['failed']} failures. "
                f"Check logs for details."
            )
            
        return results


def create_gmail_sender() -> GmailSender:
    """
    Create a GmailSender instance using environment variables.
    
    Returns:
        GmailSender: Configured Gmail sender instance
        
    Raises:
        ValueError: If required environment variables are missing
        
    Example:
        sender = create_gmail_sender()
    """
    email = os.getenv('GMAIL_ADDRESS')
    app_password = os.getenv('GMAIL_APP_PASSWORD')
    
    if not email or not app_password:
        error_msg = "Gmail credentials not found in environment variables"
        logger.error(error_msg)
        notify_slack(error_msg)
        raise ValueError(error_msg)
        
    return GmailSender(email=email, app_password=app_password)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Test email sending
        sender = create_gmail_sender()
        
        # Test single email
        sender.send_email(
            to_email="test@example.com",
            subject="Test Email",
            body="<h1>Test</h1><p>This is a test email.</p>"
        )
        
        # Test bulk emails
        recipients = [
            {
                'email': 'test1@example.com',
                'data': {'name': 'Test User 1'}
            },
            {
                'email': 'test2@example.com',
                'data': {'name': 'Test User 2'}
            }
        ]
        
        results = sender.send_bulk_emails(
            recipients=recipients,
            subject="Bulk Test",
            body_template="<h1>Hello {name}</h1><p>This is a test email.</p>"
        )
        
        logger.info(f"Test results: {results}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise 