"""
Utility functions for the AI Job Agent application.
Provides helper functions, configuration management, and retry decorators.
"""

import json
import logging
import time
import random
import requests
from functools import wraps
from typing import Dict, Any, Optional, Callable, TypeVar, cast, Union, List
from pathlib import Path
import re
import hashlib
import os
from datetime import datetime
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from logger import logger, notify_slack

# Type variable for generic function typing
T = TypeVar('T')

# Common exceptions that should trigger retries
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
    json.JSONDecodeError,
    Exception  # Generic exception as fallback
)

def create_retry_decorator(
    max_attempts: int = 5,
    min_wait: int = 4,
    max_wait: int = 60,
    exceptions: tuple = RETRYABLE_EXCEPTIONS,
    notify_on_failure: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Create a retry decorator with consistent configuration.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries in seconds
        max_wait: Maximum wait time between retries in seconds
        exceptions: Tuple of exceptions that should trigger retries
        notify_on_failure: Whether to send Slack notification on final failure
        
    Returns:
        Callable: Retry decorator that wraps a function with retry logic
        
    Example:
        @create_retry_decorator(max_attempts=3)
        def my_function():
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.INFO)
        )
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the failure
                logger.error(
                    f"Function {func.__name__} failed after {max_attempts} attempts: {str(e)}",
                    exc_info=True
                )
                
                # Notify on critical failures
                if notify_on_failure:
                    notify_slack(
                        f"Critical failure in {func.__name__}: {str(e)}\n"
                        f"Last attempt: {datetime.now()}"
                    )
                raise
                
        return cast(Callable[..., T], wrapper)
    return decorator

# Create commonly used retry decorators
retry_network = create_retry_decorator(
    max_attempts=5,
    min_wait=4,
    max_wait=60,
    exceptions=(ConnectionError, TimeoutError),
    notify_on_failure=True
)

retry_file = create_retry_decorator(
    max_attempts=3,
    min_wait=2,
    max_wait=10,
    exceptions=(OSError, FileNotFoundError),
    notify_on_failure=False
)

retry_auth = create_retry_decorator(
    max_attempts=3,
    min_wait=5,
    max_wait=30,
    exceptions=(Exception,),
    notify_on_failure=True
)

def safe_operation(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for operations that should not be retried but need error handling.
    
    Args:
        func: Function to wrap with error handling
        
    Returns:
        Callable: Wrapped function with error handling
        
    Example:
        @safe_operation
        def my_function():
            pass
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Operation {func.__name__} failed: {str(e)}",
                exc_info=True
            )
            raise
    return cast(Callable[..., T], wrapper)

@safe_operation
def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file and replace environment variables.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dict[str, Any]: Configuration dictionary with environment variables replaced
        
    Raises:
        FileNotFoundError: If config file is missing
        ValueError: If required environment variables are missing or config is invalid
        
    Example:
        config = load_config("my_config.json")
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Required environment variables
        required_vars = [
            "OPENAI_API_KEY",
            "GMAIL_SENDER_EMAIL",
            "GMAIL_APP_PASSWORD",
            "LINKEDIN_EMAIL",
            "LINKEDIN_PASSWORD",
            "SPREADSHEET_ID"
        ]
        
        # Check for missing environment variables
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise ValueError(error_msg)
            
        # Replace environment variables in config
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.getenv(env_var)
                
        return config
        
    except FileNotFoundError:
        error_msg = f"Configuration file not found: {config_path}"
        logger.error(error_msg)
        notify_slack(error_msg)
        raise FileNotFoundError(error_msg)
    except json.JSONDecodeError:
        error_msg = f"Invalid JSON in configuration file: {config_path}"
        logger.error(error_msg)
        notify_slack(error_msg)
        raise ValueError(error_msg)

@retry_file
def create_directory_if_not_exists(path: str) -> None:
    """
    Create directory if it doesn't exist.
    
    Args:
        path: Directory path to create
        
    Example:
        create_directory_if_not_exists("data/logs")
    """
    os.makedirs(path, exist_ok=True)

@retry_file
def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to be safe for all operating systems.
    
    Args:
        filename: Original filename to sanitize
        
    Returns:
        str: Sanitized filename safe for all operating systems
        
    Example:
        safe_name = sanitize_filename("my file:name.txt")
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    return filename

@retry_network
def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if email format is valid, False otherwise
        
    Example:
        is_valid = validate_email("user@example.com")
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Add random delay between operations to avoid rate limiting.
    
    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
        
    Example:
        random_delay(2.0, 5.0)  # Wait 2-5 seconds
    """
    time.sleep(random.uniform(min_seconds, max_seconds))

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        logging.Logger: Configured logger instance
        
    Example:
        logger = setup_logging("DEBUG")
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("ai_job_agent.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def parse_salary_text(salary_text: str) -> Optional[int]:
    """
    Parse salary text and convert to AED amount.
    
    Args:
        salary_text: Salary text to parse (e.g., "AED 15,000", "USD 5,000")
        
    Returns:
        Optional[int]: Salary amount in AED, or None if parsing fails
        
    Example:
        salary = parse_salary_text("AED 15,000")  # Returns 15000
        salary = parse_salary_text("USD 5,000")   # Returns 18350 (5000 * 3.67)
    """
    if not salary_text:
        return None

    salary_text = salary_text.replace(",", "").lower()

    if match := re.search(r'aed\s*(\d+)', salary_text):
        return int(match.group(1))
    if match := re.search(r'cad\s*(\d+)', salary_text):
        return int(int(match.group(1)) * 2.7)
    if match := re.search(r'usd\s*(\d+)', salary_text):
        return int(int(match.group(1)) * 3.67)
    if match := re.search(r'(\d+)', salary_text):
        return int(match.group(1))

    return None

def hash_job(title: str, company: str, location: str) -> str:
    """
    Create a unique hash for a job posting.
    
    Args:
        title: Job title
        company: Company name
        location: Job location
        
    Returns:
        str: MD5 hash of the job details
        
    Example:
        job_hash = hash_job("Python Developer", "Tech Corp", "Dubai")
    """
    job_string = f"{title.strip().lower()}_{company.strip().lower()}_{location.strip().lower()}"
    return hashlib.md5(job_string.encode()).hexdigest()

def format_currency(amount: int, currency: str = "AED") -> str:
    return f"{currency} {amount:,}"

logger = setup_logging()

def test_indeed_scraping(self):
    """Test Indeed job scraping functionality."""
    try:
        # Test with a simple search
        jobs = self.scraper.scrape_indeed_jobs(
            keywords="python developer",
            location="Dubai",
            max_pages=1
        )
        
        if not isinstance(jobs, list):
            raise ValueError("Expected list of jobs")
            
        self.logger.info(f"Indeed scraping completed: {len(jobs)} jobs found")
        return True
        
    except Exception as e:
        self.logger.error(f"Scraper test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Test helper functions
        logger.info("Testing helper functions...")
        
        # Test directory creation
        create_directory_if_not_exists("test_dir")
        logger.info("Directory creation test passed")
        
        # Test filename sanitization
        test_filename = "test:file/name.txt"
        safe_name = sanitize_filename(test_filename)
        logger.info(f"Filename sanitization test passed: {safe_name}")
        
        # Test email validation
        test_email = "test@example.com"
        is_valid = validate_email(test_email)
        logger.info(f"Email validation test passed: {is_valid}")
        
        # Test salary parsing
        test_salary = "AED 15,000"
        salary = parse_salary_text(test_salary)
        logger.info(f"Salary parsing test passed: {salary}")
        
        # Test job hashing
        job_hash = hash_job("Test Job", "Test Company", "Test Location")
        logger.info(f"Job hashing test passed: {job_hash}")
        
        logger.info("All helper function tests passed")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
