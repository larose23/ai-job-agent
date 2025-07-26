#!/usr/bin/env python3
"""
Main orchestration module for the AI Lead Finder.
Searches for people willing to pay for AI automation services across multiple platforms.

Usage:
    python lead_finder_main.py                    # Run with default config
    python lead_finder_main.py --config custom.json  # Run with custom config
    python lead_finder_main.py --help             # Show help
"""

import argparse
import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List
import asyncio
import traceback
import json

from dotenv import load_dotenv
load_dotenv()

# Custom modules
import lead_finder
from helpers import load_config
from logger import logger, notify_slack

class LeadFinderAgent:
    """Main lead finder agent that coordinates the search process."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the lead finder agent.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logger
        self.finder = lead_finder.LeadFinder(config_path)
        
    async def search_mode(self):
        """Search for AI automation leads across all platforms."""
        try:
            self.logger.info("Starting AI automation lead search...")
            
            # Get search parameters from config
            keywords = self.config.get('lead_search', {}).get('keywords', [
                "pay for AI automation",
                "looking for AI automation", 
                "need AI automation help",
                "hire AI automation",
                "AI automation services",
                "automation project",
                "AI automation budget",
                "automation freelancer",
                "AI automation contractor"
            ])
            
            max_posts_per_source = self.config.get('lead_search', {}).get('max_posts_per_source', 50)
            max_interactions = self.config.get('lead_search', {}).get('max_interactions', 10)
            output_file = self.config.get('lead_search', {}).get('output_file', 'ai_automation_leads.csv')
            
            self.logger.info(f"Searching with keywords: {keywords}")
            self.logger.info(f"Max posts per source: {max_posts_per_source}")
            self.logger.info(f"Max interactions filter: {max_interactions}")
            
            # Search for leads
            all_leads = await self.finder.search_all_leads(keywords, max_posts_per_source)
            self.logger.info(f"Found {len(all_leads)} total leads")
            
            # Filter by interactions
            filtered_leads = self.finder.filter_leads_by_interactions(all_leads, max_interactions)
            self.logger.info(f"After filtering, {len(filtered_leads)} leads with low interactions")
            
            # Sort by date
            sorted_leads = self.finder.sort_leads_by_date(filtered_leads)
            
            # Save to CSV
            self.finder.save_leads_to_csv(sorted_leads, output_file)
            
            # Log summary
            self._log_lead_summary(sorted_leads)
            
            # Send notification
            notify_slack(f"Lead search completed! Found {len(sorted_leads)} potential AI automation clients. Check {output_file}")
            
            return sorted_leads
            
        except Exception as e:
            self.logger.error(f"Error in search mode: {e}")
            notify_slack(f"Lead search failed: {e}")
            raise
            
    def _log_lead_summary(self, leads: List[Dict]):
        """Log a summary of found leads."""
        if not leads:
            self.logger.info("No leads found")
            return
            
        # Group by platform
        platform_counts = {}
        for lead in leads:
            platform = lead.get('platform', 'Unknown')
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
        self.logger.info("Lead Summary:")
        for platform, count in platform_counts.items():
            self.logger.info(f"  {platform}: {count} leads")
            
        # Show top keywords
        keyword_counts = {}
        for lead in leads:
            keyword = lead.get('keyword_matched', 'Unknown')
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            
        self.logger.info("Top Keywords:")
        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            self.logger.info(f"  {keyword}: {count} leads")
    
    async def test_mode(self) -> Dict[str, bool]:
        """Test all lead sources to ensure they're working."""
        results = {}
        
        for source_name, source in self.finder.sources.items():
            try:
                self.logger.info(f"Testing {source_name} source...")
                
                # Test with a single keyword
                test_keywords = ["AI automation"]
                leads = await source.search_leads(test_keywords, max_posts=5)
                
                results[source_name] = len(leads) > 0
                self.logger.info(f"{source_name}: {'PASS' if results[source_name] else 'FAIL'}")
                
            except Exception as e:
                self.logger.error(f"Error testing {source_name}: {e}")
                results[source_name] = False
                
        return results
    
    async def close(self):
        """Clean up resources."""
        await self.finder.close_all_sources()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Lead Finder for Automation Agency")
    parser.add_argument(
        "--config", 
        default="config.json", 
        help="Path to configuration file"
    )
    parser.add_argument(
        "--mode", 
        choices=["search", "test"], 
        default="search",
        help="Mode to run in"
    )
    parser.add_argument(
        "--keywords", 
        nargs="+",
        help="Custom keywords to search for"
    )
    parser.add_argument(
        "--max-posts", 
        type=int, 
        default=50,
        help="Maximum posts per source"
    )
    parser.add_argument(
        "--max-interactions", 
        type=int, 
        default=10,
        help="Maximum interactions filter"
    )
    parser.add_argument(
        "--output", 
        default="ai_automation_leads.csv",
        help="Output CSV file name"
    )
    
    return parser.parse_args()

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('lead_finder.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

async def main():
    """Main function."""
    args = parse_args()
    setup_logging()
    
    try:
        agent = LeadFinderAgent(args.config)
        
        if args.mode == "search":
            # Override config with command line args if provided
            if args.keywords:
                agent.config['lead_search']['keywords'] = args.keywords
            if args.max_posts:
                agent.config['lead_search']['max_posts_per_source'] = args.max_posts
            if args.max_interactions:
                agent.config['lead_search']['max_interactions'] = args.max_interactions
            if args.output:
                agent.config['lead_search']['output_file'] = args.output
                
            leads = await agent.search_mode()
            logger.info(f"Search completed successfully. Found {len(leads)} leads.")
            
        elif args.mode == "test":
            results = await agent.test_mode()
            logger.info("Test Results:")
            for source, passed in results.items():
                logger.info(f"  {source}: {'PASS' if passed else 'FAIL'}")
                
    except Exception as e:
        logger.error(f"Error in main: {e}")
        notify_slack(f"Lead finder failed: {e}")
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())