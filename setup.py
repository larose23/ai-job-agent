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
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        logger.error("Python 3.9 or higher is required")
        logger.error(f"Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    logger.info(f"Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def install_dependencies() -> bool:
    """Install Python dependencies.
    
    Returns:
        bool: True if installation was successful, False otherwise
    """
    logger.info("Installing Python dependencies...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        logger.info("Python dependencies installed")
        
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
    """Help user set up configuration.
    
    Returns:
        bool: True if configuration was successful, False otherwise
    """
    config_path = "config.json"
    template_path = "config.json.template"
    
    if os.path.exists(config_path):
        response = input(f"Config file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            logger.info("Keeping existing config file")
            return True
    
    if not os.path.exists(template_path):
        logger.error(f"Template file {template_path} not found")
        return False
    
    # Copy template to config
    with open(template_path, 'r') as f:
        config_data = json.load(f)
    
    logger.info("Setting up configuration...")
    logger.info("You can edit config.json manually later with your actual credentials")
    
    # Basic prompts for essential settings
    openai_key = input("Enter your OpenAI API key (or press Enter to skip): ").strip()
    if openai_key:
        config_data["openai_api_key"] = openai_key
    
    sheet_id = input("Enter your Google Sheets ID (or press Enter to skip): ").strip()
    if sheet_id:
        config_data["spreadsheet_id"] = sheet_id
    
    gmail = input("Enter your Gmail address (or press Enter to skip): ").strip()
    if gmail:
        config_data["gmail_sender_email"] = gmail
    
    # Save config
    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    logger.info(f"Configuration saved to {config_path}")
    logger.info("Remember to edit config.json with your actual credentials!")
    return True

def setup_resume() -> bool:
    """Help user set up base resume.
    
    Returns:
        bool: True if resume setup was successful, False otherwise
    """
    resume_path = "data/base_resume.txt"
    
    if os.path.exists(resume_path):
        response = input("Base resume already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            logger.info("Keeping existing resume file")
            return True
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    logger.info("Setting up base resume...")
    logger.info("You can edit data/base_resume.txt later with your actual resume content")
    
    # Create a basic template
    resume_template = """[Your Name]
[Your Email] | [Your Phone] | [Your Location] | [LinkedIn Profile]

PROFESSIONAL SUMMARY
[Brief summary of your experience and skills]

TECHNICAL SKILLS
• Programming Languages: [List your languages]
• Frameworks & Tools: [List frameworks and tools]
• Databases: [List database technologies]
• Cloud Platforms: [List cloud platforms]

PROFESSIONAL EXPERIENCE

[Job Title] | [Company Name] | [Location] | [Start Date] - [End Date]
• [Achievement/responsibility with quantifiable results]
• [Achievement/responsibility with quantifiable results]
• [Achievement/responsibility with quantifiable results]

[Job Title] | [Company Name] | [Location] | [Start Date] - [End Date]
• [Achievement/responsibility with quantifiable results]
• [Achievement/responsibility with quantifiable results]

EDUCATION
[Degree] in [Field] | [University Name] | [Location] | [Graduation Year]

CERTIFICATIONS
• [Certification Name] - [Issuing Organization] ([Year])

PROJECTS
[Project Name] | [Technologies Used] | [Year]
• [Brief description of project and your role]
• [Key achievements or outcomes]
"""
    
    with open(resume_path, 'w') as f:
        f.write(resume_template)
    
    logger.info(f"Base resume template created at {resume_path}")
    logger.info("Please edit this file with your actual resume content!")
    return True

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
        "main.py",
        "google_credentials.json"  # Required for Google Sheets API authentication
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"Missing files: {missing_files}")
        if "google_credentials.json" in missing_files:
            logger.warning("IMPORTANT: google_credentials.json is required for Google Sheets API authentication.")
            logger.info("Please obtain this file from the Google Cloud Console:")
            logger.info("1. Go to https://console.cloud.google.com")
            logger.info("2. Create a new project or select an existing one")
            logger.info("3. Enable the Google Sheets API")
            logger.info("4. Create a service account and download the credentials JSON file")
            logger.info("5. Rename the downloaded file to 'google_credentials.json' and place it in the project root")
        return False
    
    # Check config file
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        required_keys = ["openai_api_key", "spreadsheet_id", "gmail_sender_email"]
        missing_keys = [key for key in required_keys if not config.get(key) or "your-" in config.get(key, "")]
        
        if missing_keys:
            logger.warning(f"Config needs attention: {missing_keys}")
            logger.info("Please edit config.json with your actual credentials")
        else:
            logger.info("Configuration looks good")
            
    except Exception as e:
        logger.error(f"Config file error: {e}")
        return False
    
    logger.info("Setup verification completed")
    return True

def show_next_steps() -> None:
    """Show user what to do next."""
    print_header("Next Steps")
    
    logger.info("1. Edit config.json with your actual credentials:")
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

