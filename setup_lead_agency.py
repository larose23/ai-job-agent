#!/usr/bin/env python3
"""
Setup script for AI Lead Generation Agency
"""

import os
import json
import shutil
from pathlib import Path

def setup_lead_agency():
    """Setup the complete lead generation agency."""
    print("🤖 AI Lead Generation Agency Setup")
    print("=" * 50)
    
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("exports", exist_ok=True)
    
    print("✅ Created directories: data/, logs/, exports/")
    
    # Create configuration file
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
                "AI automation contractor",
                "automation consultant",
                "AI automation expert"
            ],
            "max_posts_per_source": 50,
            "max_interactions": 10,
            "output_file": "exports/ai_automation_leads.csv",
            "platforms": ["reddit", "indeed", "upwork", "linkedin"],
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
    
    print("✅ Created config.json with lead search settings")
    
    # Create .env template
    env_template = """# AI Lead Generation Agency Environment Variables
# Copy this to .env and fill in your values

# API Keys (optional - for enhanced functionality)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password

# Notification Settings
SLACK_WEBHOOK_URL=your_slack_webhook_url
EMAIL_RECIPIENT=your-email@example.com

# Proxy Settings (optional)
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=https://proxy:port
"""
    
    with open(".env.template", "w") as f:
        f.write(env_template)
    
    print("✅ Created .env.template")
    
    # Create README
    readme = """# AI Lead Generation Agency

## Quick Start

1. **Run the lead finder:**
   ```bash
   python3 production_lead_finder.py
   ```

2. **Check results:**
   ```bash
   cat exports/ai_automation_leads.csv
   ```

3. **Schedule regular runs:**
   ```bash
   # Add to crontab for daily runs
   0 9 * * * cd /path/to/agency && python3 production_lead_finder.py
   ```

## Configuration

Edit `config.json` to customize:
- Keywords to search for
- Maximum interactions filter
- Output file location
- Platforms to search

## Files

- `production_lead_finder.py` - Main lead finder
- `working_lead_finder.py` - Simple version
- `config.json` - Configuration
- `exports/` - Generated CSV files
- `logs/` - Log files

## Next Steps

1. Review leads in CSV file
2. Research each lead
3. Personalize outreach
4. Track responses
5. Scale successful approaches

## Support

For issues or questions, check the logs in the logs/ directory.
"""
    
    with open("README.md", "w") as f:
        f.write(readme)
    
    print("✅ Created README.md")
    
    # Test the setup
    print("\n🧪 Testing setup...")
    try:
        from production_lead_finder import ProductionLeadFinder
        finder = ProductionLeadFinder()
        print("✅ Lead finder imports successfully")
    except Exception as e:
        print(f"❌ Import error: {e}")
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Run: python3 production_lead_finder.py")
    print("2. Check: exports/ai_automation_leads.csv")
    print("3. Customize: config.json")
    print("4. Schedule: Add to crontab for daily runs")

if __name__ == "__main__":
    setup_lead_agency()
