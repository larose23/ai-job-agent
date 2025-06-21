#!/usr/bin/env python3
"""
Command-line interface for the AI Job Agent.
Provides a user-friendly way to run different components of the job search pipeline.

This module implements a CLI using Typer that allows users to:
1. Search for jobs and send alerts
2. Set up the job agent components
3. Check configuration validity

Example usage:
    job-agent search --keywords "python developer" --location "dubai" --recipient-email "user@example.com"
    job-agent setup
    job-agent check-config
"""

import os
import typer
from typing import Optional, Dict, Any
from pathlib import Path
import sys
from datetime import datetime
from job_agent import JobAgent
from helpers import (
    retry_network,
    retry_auth,
    safe_operation,
    logger,
    notify_slack,
    load_config
)

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import project modules
from job_scraper import JobScraper
from email_sender import EmailSender
from resume_tailor import ResumeTailor
from sheets_logger import SheetsLogger

# Create Typer app
app = typer.Typer(
    name="job-agent",
    help="AI-powered job search automation tool",
    add_completion=False
)

def validate_config(config_path: str) -> bool:
    """
    Validate that the config file exists and is valid.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        bool: True if config is valid, False otherwise
        
    Example:
        is_valid = validate_config("config.json")
    """
    try:
        from helpers import load_config
        load_config(config_path)
        return True
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return False

@app.command()
@safe_operation
def search(
    keywords: str = typer.Option(..., help="Job search keywords"),
    location: str = typer.Option(..., help="Location to search in"),
    recipient_email: str = typer.Option(..., help="Email to send alerts to"),
    max_pages: int = typer.Option(5, help="Maximum number of pages to scrape"),
    config_path: str = typer.Option("config.json", help="Path to config file")
) -> None:
    """
    Search for jobs and send alerts.
    
    This command performs the following steps:
    1. Initializes the job agent with the provided configuration
    2. Runs the job search with the specified parameters
    3. Sends alerts to the specified email address
    4. Reports the results of the operation
    
    Args:
        keywords: Job search keywords (e.g., "python developer")
        location: Location to search in (e.g., "dubai")
        recipient_email: Email address to send alerts to
        max_pages: Maximum number of pages to scrape (default: 5)
        config_path: Path to the configuration file (default: config.json)
        
    Example:
        job-agent search --keywords "python developer" --location "dubai" --recipient-email "user@example.com"
    """
    try:
        # Initialize job agent
        agent = JobAgent(config_path)
        
        # Run job search
        results = agent.run(
            keywords=keywords,
            location=location,
            recipient_email=recipient_email,
            max_pages=max_pages
        )
        
        # Print results
        if results['status'] == 'success':
            typer.echo(f"Found {results['jobs_found']} jobs")
            typer.echo(f"Analyzed {results['jobs_analyzed']} jobs")
            typer.echo(f"Alert status: {results['alert_status']}")
        else:
            typer.echo(f"Error: {results['message']}")
            
    except Exception as e:
        error_msg = f"CLI command failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        notify_slack(error_msg)
        typer.echo(f"Error: {error_msg}")
        raise typer.Exit(1)

@app.command()
@safe_operation
def setup(
    config_path: str = typer.Option("config.json", help="Path to config file")
) -> None:
    """
    Set up the job agent components.
    
    This command performs the following steps:
    1. Initializes the job agent with the provided configuration
    2. Sets up all required components (scrapers, email sender, etc.)
    3. Verifies the setup was successful
    
    Args:
        config_path: Path to the configuration file (default: config.json)
        
    Example:
        job-agent setup
    """
    try:
        # Initialize job agent
        agent = JobAgent(config_path)
        
        # Set up components
        agent.setup()
        
        typer.echo("Successfully set up job agent components")
        
    except Exception as e:
        error_msg = f"Setup failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        notify_slack(error_msg)
        typer.echo(f"Error: {error_msg}")
        raise typer.Exit(1)

@app.command()
@safe_operation
def check_config(
    config_path: str = typer.Option("config.json", help="Path to config file")
) -> None:
    """
    Check the configuration file.
    
    This command performs the following checks:
    1. Validates the configuration file format
    2. Verifies all required environment variables are set
    3. Reports any missing or invalid configuration
    
    Args:
        config_path: Path to the configuration file (default: config.json)
        
    Example:
        job-agent check-config
    """
    try:
        # Load config
        config = load_config(config_path)
        
        # Check required environment variables
        required_vars = [
            "OPENAI_API_KEY",
            "GMAIL_SENDER_EMAIL",
            "GMAIL_APP_PASSWORD",
            "LINKEDIN_EMAIL",
            "LINKEDIN_PASSWORD",
            "SPREADSHEET_ID"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            typer.echo("Missing required environment variables:")
            for var in missing_vars:
                typer.echo(f"- {var}")
            raise typer.Exit(1)
            
        typer.echo("Configuration is valid")
        
    except Exception as e:
        error_msg = f"Config check failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        notify_slack(error_msg)
        typer.echo(f"Error: {error_msg}")
        raise typer.Exit(1)

@app.command()
@safe_operation
def run(
    config_path: str = typer.Option("config.json", help="Path to config file"),
    auto_apply: bool = typer.Option(None, help="Enable auto-apply (overrides config)"),
    review_before_apply: bool = typer.Option(None, help="Enable review before apply (overrides config)")
):
    """
    Run the job agent with specified config and feature flags.
    """
    config = load_config(config_path)
    if auto_apply is not None:
        config['auto_apply_enabled'] = auto_apply
    if review_before_apply is not None:
        config['review_before_apply'] = review_before_apply
    # ... rest of the run logic, passing config to dispatcher ...

@app.command()
@safe_operation
def process_review_queue(
    config_path: str = typer.Option("config.json", help="Path to config file")
):
    """
    Process jobs marked as Approved in the Review sheet and trigger applications.
    """
    import asyncio
    from application_dispatcher import ApplicationDispatcher
    from sheets_logger import SheetsLogger
    config = load_config(config_path)
    user_profile = config.get('user_profile', {})
    sheets_logger = SheetsLogger(config_path)
    approved_jobs = sheets_logger.get_approved_review_jobs()
    dispatcher = ApplicationDispatcher(config, user_profile)
    async def process_jobs():
        for job in approved_jobs:
            await dispatcher.dispatch(job)
    asyncio.run(process_jobs())

def main() -> None:
    """
    Entry point for the CLI.
    
    This function:
    1. Runs the Typer application
    2. Handles any uncaught exceptions
    3. Ensures proper exit codes
    
    Example:
        if __name__ == "__main__":
            main()
    """
    try:
        app()
    except Exception as e:
        logger.error(f"CLI failed: {e}")
        notify_slack(f"CLI failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 