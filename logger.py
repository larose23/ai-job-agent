import os
import logging
from logging.handlers import RotatingFileHandler
import requests
from datetime import datetime
from typing import Optional

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

def setup_logger(name: str = 'job_agent') -> logging.Logger:
    """
    Set up a logger with both file and console handlers.
    
    Args:
        name: Name of the logger
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # File handler (rotating)
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def notify_slack(message: str, webhook_url: Optional[str] = None) -> None:
    """
    Send error notifications to Slack if webhook URL is configured.
    
    Args:
        message: Message to send
        webhook_url: Optional Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
    """
    webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        return
        
    try:
        payload = {
            'text': f"🚨 Job Agent Error - {datetime.now()}\n{message}"
        }
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except Exception as e:
        # Don't raise the exception, just log it
        logging.error(f"Failed to send Slack notification: {e}")

# Create default logger instance
logger = setup_logger()

# Example usage:
# from logger import logger
# logger.info("Application started")
# logger.error("An error occurred", exc_info=True)
# logger.warning("Warning message") 