#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

print("=== Environment Variables Check ===")
print(f"LINKEDIN_EMAIL: {os.getenv('LINKEDIN_EMAIL')}")
print(f"USER_FULL_NAME: {os.getenv('USER_FULL_NAME')}")
print(f"USER_EMAIL: {os.getenv('USER_EMAIL')}")
print(f"GMAIL_SENDER_EMAIL: {os.getenv('GMAIL_SENDER_EMAIL')}")
print(f"GOOGLE_GMAIL_CREDENTIALS_PATH: {os.getenv('GOOGLE_GMAIL_CREDENTIALS_PATH')}")
print(f"GOOGLE_SHEETS_CREDENTIALS_PATH: {os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')}")

print("\n=== Configuration Check ===")
try:
    from helpers import load_config
    config = load_config("config.json")
    
    print(f"Auto-apply enabled: {config.get('auto_apply', {}).get('enabled', False)}")
    print(f"User profile: {config.get('user_profile', {})}")
    print(f"LinkedIn credentials: {'Present' if config.get('credentials', {}).get('linkedin') else 'Missing'}")
    
except Exception as e:
    print(f"Error loading config: {e}") 