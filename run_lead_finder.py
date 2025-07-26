#!/usr/bin/env python3
"""
Simple script to run the AI Lead Finder.
"""

import asyncio
import sys
import os
from lead_finder_main import LeadFinderAgent, setup_logging
from logger import logger

async def run_lead_search():
    """Run the lead search process."""
    try:
        # Setup logging
        setup_logging()
        
        # Initialize agent
        agent = LeadFinderAgent()
        
        # Run search
        leads = await agent.search_mode()
        
        print(f"\n✅ Lead search completed successfully!")
        print(f"📊 Found {len(leads)} potential AI automation clients")
        print(f"💾 Results saved to: ai_automation_leads.csv")
        
        if leads:
            print(f"\n📋 Top leads found:")
            for i, lead in enumerate(leads[:5], 1):
                platform = lead.get('platform', 'Unknown')
                title = lead.get('title', 'No title')[:80]
                interactions = lead.get('num_comments', 0) + lead.get('score', 0)
                print(f"  {i}. [{platform}] {title} (interactions: {interactions})")
        
        return leads
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Lead search failed: {e}")
        return []

async def test_sources():
    """Test all lead sources."""
    try:
        setup_logging()
        agent = LeadFinderAgent()
        
        print("🧪 Testing lead sources...")
        results = await agent.test_mode()
        
        print("\n📊 Test Results:")
        for source, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {source}: {status}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error testing sources: {e}")
        return {}

def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            asyncio.run(test_sources())
        elif command == "search":
            asyncio.run(run_lead_search())
        elif command == "help":
            print("""
🤖 AI Lead Finder for Automation Agency

Usage:
  python run_lead_finder.py          # Run lead search
  python run_lead_finder.py search   # Run lead search
  python run_lead_finder.py test     # Test all sources
  python run_lead_finder.py help     # Show this help

The lead finder searches for people willing to pay for AI automation services
across Reddit, Twitter, LinkedIn, and Facebook Groups.
            """)
        else:
            print(f"❌ Unknown command: {command}")
            print("Use 'python run_lead_finder.py help' for usage information")
    else:
        # Default to search
        asyncio.run(run_lead_search())

if __name__ == "__main__":
    main()