#!/usr/bin/env python3
"""
Test script for the AI Lead Finder.
"""

import asyncio
import sys
import os
from lead_finder import LeadFinder, find_ai_automation_leads
from logger import logger

async def test_lead_finder():
    """Test the lead finder functionality."""
    print("🧪 Testing AI Lead Finder...")
    
    try:
        # Test with minimal parameters
        leads = await find_ai_automation_leads(
            keywords=["AI automation"],
            max_posts_per_source=5,
            max_interactions=20,
            output_file="test_leads.csv"
        )
        
        print(f"✅ Test completed successfully!")
        print(f"📊 Found {len(leads)} test leads")
        
        if leads:
            print(f"\n📋 Sample leads:")
            for i, lead in enumerate(leads[:3], 1):
                platform = lead.get('platform', 'Unknown')
                title = lead.get('title', 'No title')[:60]
                print(f"  {i}. [{platform}] {title}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Lead finder test failed: {e}")
        return False

async def test_individual_sources():
    """Test each source individually."""
    print("\n🔍 Testing individual sources...")
    
    from lead_finder import RedditSource, TwitterSource, LinkedInSource, FacebookGroupsSource
    from helpers import load_config
    
    config = load_config()
    sources = {
        'Reddit': RedditSource(config),
        'Twitter': TwitterSource(config),
        'LinkedIn': LinkedInSource(config),
        'Facebook': FacebookGroupsSource(config)
    }
    
    results = {}
    
    for name, source in sources.items():
        try:
            print(f"  Testing {name}...")
            leads = await source.search_leads(["AI automation"], max_posts=3)
            results[name] = len(leads) > 0
            print(f"    {name}: {'✅ PASS' if results[name] else '❌ FAIL'} ({len(leads)} leads)")
        except Exception as e:
            print(f"    {name}: ❌ FAIL - {e}")
            results[name] = False
        finally:
            await source.close()
    
    return results

def main():
    """Main test function."""
    print("🤖 AI Lead Finder Test Suite")
    print("=" * 40)
    
    # Test 1: Basic functionality
    print("\n1. Testing basic lead finder...")
    basic_test = asyncio.run(test_lead_finder())
    
    # Test 2: Individual sources
    print("\n2. Testing individual sources...")
    source_tests = asyncio.run(test_individual_sources())
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 TEST SUMMARY")
    print("=" * 40)
    
    print(f"Basic functionality: {'✅ PASS' if basic_test else '❌ FAIL'}")
    
    print("\nSource tests:")
    for source, passed in source_tests.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {source}: {status}")
    
    # Overall result
    all_passed = basic_test and all(source_tests.values())
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Your AI Lead Finder is ready to use!")
        print("Run 'python run_lead_finder.py' to start finding leads.")
    else:
        print("\n⚠️  Some tests failed. Check the logs for details.")
        print("You may need to:")
        print("  - Check your internet connection")
        print("  - Verify platform accessibility")
        print("  - Update selectors if platforms changed")

if __name__ == "__main__":
    main()