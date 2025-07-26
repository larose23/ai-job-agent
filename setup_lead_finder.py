#!/usr/bin/env python3
"""
Setup script for the AI Lead Finder.
"""

import os
import json
import shutil
from pathlib import Path

def setup_lead_finder():
    """Setup the lead finder configuration."""
    print("🤖 AI Lead Finder Setup")
    print("=" * 40)
    
    # Check if config.json exists
    if os.path.exists("config.json"):
        print("✅ config.json already exists")
        backup_config()
    else:
        print("📝 Creating config.json from template...")
        create_config()
    
    # Check if .env exists
    if os.path.exists(".env"):
        print("✅ .env file already exists")
    else:
        print("⚠️  .env file not found")
        print("   Please create .env file with your API keys")
        print("   See .env.template for required variables")
    
    # Create output directory
    os.makedirs("data", exist_ok=True)
    print("✅ Data directory ready")
    
    # Test the setup
    print("\n🧪 Testing setup...")
    test_setup()
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Run: python test_lead_finder.py")
    print("2. Run: python run_lead_finder.py")
    print("3. Check ai_automation_leads.csv for results")

def backup_config():
    """Backup existing config and add lead search section."""
    print("📋 Backing up existing config...")
    
    # Read existing config
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # Add lead search section if not present
    if "lead_search" not in config:
        print("➕ Adding lead search configuration...")
        config["lead_search"] = {
            "enabled": True,
            "keywords": [
                "pay for AI automation",
                "looking for AI automation",
                "need AI automation help",
                "hire AI automation",
                "AI automation services",
                "automation project",
                "AI automation budget",
                "automation freelancer",
                "AI automation contractor"
            ],
            "max_posts_per_source": 50,
            "max_interactions": 10,
            "output_file": "ai_automation_leads.csv",
            "platforms": ["reddit", "twitter", "linkedin", "facebook"],
            "search_frequency_hours": 24
        }
        
        # Write updated config
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        print("✅ Lead search configuration added")
    else:
        print("✅ Lead search configuration already present")

def create_config():
    """Create a new config.json file."""
    config = {
        "lead_search": {
            "enabled": True,
            "keywords": [
                "pay for AI automation",
                "looking for AI automation",
                "need AI automation help",
                "hire AI automation",
                "AI automation services",
                "automation project",
                "AI automation budget",
                "automation freelancer",
                "AI automation contractor"
            ],
            "max_posts_per_source": 50,
            "max_interactions": 10,
            "output_file": "ai_automation_leads.csv",
            "platforms": ["reddit", "twitter", "linkedin", "facebook"],
            "search_frequency_hours": 24
        },
        "notification_preferences": {
            "email": {
                "enabled": True,
                "recipient_list": ["your-email@example.com"]
            },
            "slack": {
                "enabled": False,
                "webhook_url": "${SLACK_WEBHOOK_URL}"
            }
        },
        "proxy_settings": {
            "enabled": False,
            "http_proxy": "${HTTP_PROXY}",
            "https_proxy": "${HTTPS_PROXY}"
        }
    }
    
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("✅ config.json created")

def test_setup():
    """Test the basic setup."""
    try:
        # Test config loading
        from helpers import load_config
        config = load_config()
        
        if "lead_search" in config:
            print("✅ Configuration loaded successfully")
            
            lead_config = config["lead_search"]
            print(f"   Keywords: {len(lead_config.get('keywords', []))}")
            print(f"   Platforms: {lead_config.get('platforms', [])}")
            print(f"   Max posts: {lead_config.get('max_posts_per_source', 50)}")
            print(f"   Max interactions: {lead_config.get('max_interactions', 10)}")
        else:
            print("❌ Lead search configuration not found")
            
    except Exception as e:
        print(f"❌ Setup test failed: {e}")

def main():
    """Main setup function."""
    try:
        setup_lead_finder()
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        print("\nManual setup required:")
        print("1. Copy lead_finder_config_example.json to config.json")
        print("2. Create .env file with your API keys")
        print("3. Run: python test_lead_finder.py")

if __name__ == "__main__":
    main()