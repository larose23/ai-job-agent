#!/usr/bin/env python3
"""
Setup script for AI Job Agent.
Helps users configure the application and verify setup.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_header(title: str) -> None:
    """Print a formatted header.
    
    Args:
        title: The title text to display in the header
    """
    logger.info("\n" + "="*60)
    logger.info(f" {title}")
    logger.info("="*60)

def print_step(step_num: int, title: str) -> None:
    """Print a formatted step.
    
    Args:
        step_num: The step number
        title: The step title
    """
    logger.info(f"\n[Step {step_num}] {title}")
    logger.info("-" * 40)

def check_python_version() -> bool:
    """Check if Python version is compatible.
    
    Returns:
        bool: True if Python version is compatible, False otherwise
    """
    required_version = (3, 8)
    current_version = sys.version_info[:2]
    
    if current_version < required_version:
        logger.error(f"Python {required_version[0]}.{required_version[1]} or higher is required")
        return False
    
    logger.info(f"Python version {sys.version.split()[0]} is compatible")
    return True

def install_dependencies() -> bool:
    """Install required dependencies.
    
    Returns:
        bool: True if installation was successful, False otherwise
    """
    logger.info("Installing Python dependencies...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        logger.info("Dependencies installed successfully")
        
        # Install Playwright browsers
        logger.info("Installing Playwright browsers...")
        subprocess.run([sys.executable, "-m", "playwright", "install"], 
                      check=True, capture_output=True)
        logger.info("Playwright browsers installed")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        return False

def setup_config() -> bool:
    """Set up configuration files.
    
    Returns:
        bool: True if configuration was successful, False otherwise
    """
    try:
        # Create .env from template if it doesn't exist
        if not os.path.exists(".env"):
            if os.path.exists(".env.template"):
                with open(".env.template", "r") as template:
                    with open(".env", "w") as env:
                        env.write(template.read())
                logger.info("Created .env file from template")
            else:
                logger.error(".env.template not found")
                return False
                
        # Create config.json from template if it doesn't exist
        if not os.path.exists("config.json"):
            if os.path.exists("config.json.template"):
                with open("config.json.template", "r") as template:
                    with open("config.json", "w") as config:
                        config.write(template.read())
                logger.info("Created config.json from template")
            else:
                logger.error("config.json.template not found")
                return False
                
            return True
    except Exception as e:
        logger.error(f"Failed to set up configuration: {e}")
        return False

def setup_resume() -> bool:
    """Set up resume file.
    
    Returns:
        bool: True if resume setup was successful, False otherwise
    """
    try:
        resume_dir = Path("data")
        resume_dir.mkdir(exist_ok=True)
        
        resume_file = resume_dir / "base_resume.txt"
        if not resume_file.exists():
            with open(resume_file, "w") as f:
                f.write("# Your Resume Content\n\n")
                f.write("Add your resume content here.\n")
            logger.info("Created base_resume.txt template")
            
    return True
    except Exception as e:
        logger.error(f"Failed to set up resume: {e}")
        return False

def verify_setup() -> bool:
    """Verify the setup is correct.
    
    Returns:
        bool: True if setup is correct, False otherwise
    """
    logger.info("Verifying setup...")
    
    # Check required files
    required_files = [
        "config.json",
        "data/base_resume.txt",
        "requirements.txt",
        "main.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"Missing files: {missing_files}")
        return False
        
    # Check environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "GMAIL_SENDER_EMAIL",
        "GMAIL_APP_PASSWORD",
        "SPREADSHEET_ID",
        "GOOGLE_CREDENTIALS_JSON_PATH"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        return False
    
    logger.info("Setup verification passed")
    return True

def show_next_steps() -> None:
    """Show user what to do next."""
    print_header("Next Steps")
    
    logger.info("1. Edit .env with your credentials:")
    logger.info("   • OpenAI API key")
    logger.info("   • Google Sheets ID") 
    logger.info("   • Gmail credentials")
    logger.info("   • LinkedIn credentials")
    
    logger.info("\n2. Edit data/base_resume.txt with your resume content")
    
    logger.info("\n3. Set up Google Cloud credentials:")
    logger.info("   • Download credentials.json from Google Cloud Console")
    logger.info("   • Place it in the project root directory")
    
    logger.info("\n4. Test the setup:")
    logger.info("   python main.py --test")
    
    logger.info("\n5. Start using the application:")
    logger.info("   python main.py --scrape")
    
    logger.info("\nFor detailed instructions, see README.md")

def main() -> bool:
    """Main setup function.
    
    Returns:
        bool: True if setup was successful, False otherwise
    """
    print_header("AI Job Agent Setup")
    logger.info("This script will help you set up the AI Job Agent application.")
    
    # Step 1: Check Python version
    print_step(1, "Checking Python Version")
    if not check_python_version():
        return False
    
    # Step 2: Install dependencies
    print_step(2, "Installing Dependencies")
    if not install_dependencies():
        return False
    
    # Step 3: Setup configuration
    print_step(3, "Setting Up Configuration")
    if not setup_config():
        return False
    
    # Step 4: Setup resume
    print_step(4, "Setting Up Resume")
    if not setup_resume():
        return False
    
    # Step 5: Verify setup
    print_step(5, "Verifying Setup")
    if not verify_setup():
        return False
    
    # Show next steps
    show_next_steps()
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nSetup failed with error: {e}")
        sys.exit(1)

