#!/usr/bin/env python3
"""
AI Lead Generation Agency - Main Runner
"""

import os
import sys
import subprocess
import time
from datetime import datetime

def run_lead_finder():
    """Run the lead finder and return results."""
    print("🚀 Starting AI Lead Generation Agency...")
    print("=" * 50)
    
    try:
        # Run the production lead finder
        result = subprocess.run([
            sys.executable, "production_lead_finder.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Lead finder completed successfully!")
            return True
        else:
            print(f"❌ Lead finder failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error running lead finder: {e}")
        return False

def check_results():
    """Check and display results."""
    csv_file = "exports/ai_automation_leads.csv"
    
    if os.path.exists(csv_file):
        try:
            with open(csv_file, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:  # Has header + data
                    lead_count = len(lines) - 1
                    print(f"\n📊 Found {lead_count} leads in {csv_file}")
                    
                    # Show first few leads
                    print("\n📋 Sample leads:")
                    for i, line in enumerate(lines[1:6], 1):  # Skip header, show first 5
                        parts = line.strip().split(',')
                        if len(parts) >= 3:
                            platform = parts[0]
                            title = parts[2][:60]
                            print(f"  {i}. [{platform}] {title}...")
                    
                    return True
                else:
                    print("⚠️  CSV file is empty")
                    return False
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            return False
    else:
        print("⚠️  No results file found")
        return False

def show_next_steps():
    """Show next steps for the user."""
    print("\n" + "=" * 50)
    print("🎯 NEXT STEPS FOR YOUR AI AUTOMATION AGENCY")
    print("=" * 50)
    
    print("\n1. 📋 REVIEW LEADS")
    print("   - Check exports/ai_automation_leads.csv")
    print("   - Research each lead before contacting")
    print("   - Verify their needs match your services")
    
    print("\n2. 📧 PERSONALIZE OUTREACH")
    print("   - Customize messages based on their specific needs")
    print("   - Mention relevant experience and solutions")
    print("   - Include clear call-to-action")
    
    print("\n3. 📊 TRACK RESPONSES")
    print("   - Use a CRM to track all interactions")
    print("   - Monitor response rates and conversion")
    print("   - Optimize based on what works")
    
    print("\n4. 🔄 AUTOMATE THE PROCESS")
    print("   - Schedule daily runs: crontab -e")
    print("   - Add: 0 9 * * * cd /path/to/agency && python3 production_lead_finder.py")
    print("   - Set up email notifications for new leads")
    
    print("\n5. 📈 SCALE SUCCESS")
    print("   - Focus on platforms that work best")
    print("   - Expand keywords based on results")
    print("   - Build relationships with repeat clients")
    
    print("\n�� PRO TIPS:")
    print("   - Start with 5-10 leads per day")
    print("   - Follow up within 24 hours")
    print("   - Offer free consultation calls")
    print("   - Build case studies from successful projects")

def main():
    """Main function."""
    print("🤖 AI Lead Generation Agency")
    print("=" * 50)
    
    # Run lead finder
    success = run_lead_finder()
    
    if success:
        # Check results
        results_found = check_results()
        
        if results_found:
            print("\n🎉 SUCCESS! Your lead generation agency is working!")
            show_next_steps()
        else:
            print("\n⚠️  No leads found. Check configuration and try again.")
    else:
        print("\n❌ Lead finder failed. Check logs and try again.")

if __name__ == "__main__":
    main()
