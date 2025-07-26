"""
Lead Finder for AI Automation Agency
Searches for people willing to pay for AI automation services across multiple platforms.
"""

import os
import asyncio
import random
import time
import logging
import json
import re
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote_plus, urljoin
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent
from datetime import datetime, timedelta
import csv

from helpers import (
    load_config,
    retry_network,
    retry_auth,
    safe_operation,
    random_delay,
    logger,
    notify_slack
)

load_dotenv()

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
]

class BaseLeadSource:
    """Base class for all lead sources."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        
    async def init_browser(self) -> None:
        """Initialize browser for scraping."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def search_leads(
        self,
        keywords: List[str],
        max_posts: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for leads from this source."""
        raise NotImplementedError("Subclasses must implement search_leads")
        
    def deduplicate_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate leads based on URL."""
        unique_leads = []
        seen_urls = set()
        
        for lead in leads:
            lead_url = lead.get('url', '')
            if lead_url and lead_url not in seen_urls:
                unique_leads.append(lead)
                seen_urls.add(lead_url)
        return unique_leads

class RedditSource(BaseLeadSource):
    """Reddit lead source for finding people looking for AI automation services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.subreddits = [
            'forhire', 'freelance', 'startups', 'entrepreneur', 
            'smallbusiness', 'business', 'automation', 'ai', 'machinelearning'
        ]
        
    async def search_leads(
        self,
        keywords: List[str],
        max_posts: int = 50
    ) -> List[Dict[str, Any]]:
        """Search Reddit for leads."""
        leads = []
        
        for subreddit in self.subreddits:
            for keyword in keywords:
                try:
                    sub_leads = await self._search_subreddit(subreddit, keyword, max_posts // len(self.subreddits))
                    leads.extend(sub_leads)
                    await random_delay(1, 3)
                except Exception as e:
                    self.logger.error(f"Error searching r/{subreddit} for {keyword}: {e}")
                    
        return self.deduplicate_leads(leads)
    
    async def _search_subreddit(self, subreddit: str, keyword: str, max_posts: int) -> List[Dict[str, Any]]:
        """Search a specific subreddit for leads."""
        leads = []
        
        # Reddit search URL
        search_url = f"https://www.reddit.com/r/{subreddit}/search.json?q={quote_plus(keyword)}&restrict_sr=1&sort=new&t=week"
        
        try:
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'application/json'
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            for post in posts[:max_posts]:
                post_data = post.get('data', {})
                
                # Check if post is looking for services (not offering)
                title = post_data.get('title', '').lower()
                selftext = post_data.get('selftext', '').lower()
                
                # Keywords that indicate someone is looking to pay for services
                looking_keywords = [
                    'looking for', 'need help', 'seeking', 'want to hire',
                    'pay for', 'budget', 'project', 'freelancer', 'contractor'
                ]
                
                # Keywords that indicate offering services (exclude these)
                offering_keywords = [
                    'offering', 'i can', 'i will', 'services available',
                    'hire me', 'i provide', 'i offer'
                ]
                
                is_looking = any(keyword in title or keyword in selftext for keyword in looking_keywords)
                is_offering = any(keyword in title or keyword in selftext for keyword in offering_keywords)
                
                if is_looking and not is_offering:
                    lead = {
                        'platform': 'Reddit',
                        'subreddit': subreddit,
                        'title': post_data.get('title', ''),
                        'content': post_data.get('selftext', ''),
                        'url': f"https://reddit.com{post_data.get('permalink', '')}",
                        'author': post_data.get('author', ''),
                        'score': post_data.get('score', 0),
                        'num_comments': post_data.get('num_comments', 0),
                        'created_utc': post_data.get('created_utc', 0),
                        'keyword_matched': keyword
                    }
                    leads.append(lead)
                    
        except Exception as e:
            self.logger.error(f"Error searching r/{subreddit}: {e}")
            
        return leads

class TwitterSource(BaseLeadSource):
    """Twitter lead source for finding people looking for AI automation services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
    async def search_leads(
        self,
        keywords: List[str],
        max_posts: int = 50
    ) -> List[Dict[str, Any]]:
        """Search Twitter for leads."""
        leads = []
        
        for keyword in keywords:
            try:
                keyword_leads = await self._search_twitter(keyword, max_posts // len(keywords))
                leads.extend(keyword_leads)
                await random_delay(2, 5)
            except Exception as e:
                self.logger.error(f"Error searching Twitter for {keyword}: {e}")
                
        return self.deduplicate_leads(leads)
    
    async def _search_twitter(self, keyword: str, max_posts: int) -> List[Dict[str, Any]]:
        """Search Twitter for leads."""
        leads = []
        
        # Using Twitter's search endpoint (note: this is simplified and may need API keys)
        search_url = f"https://twitter.com/search?q={quote_plus(keyword)}&src=typed_query&f=live"
        
        try:
            await self.init_browser()
            await self.page.goto(search_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Extract tweets
            tweets = await self.page.query_selector_all('article[data-testid="tweet"]')
            
            for tweet in tweets[:max_posts]:
                try:
                    # Extract tweet data
                    tweet_text = await tweet.query_selector('[data-testid="tweetText"]')
                    if tweet_text:
                        text = await tweet_text.inner_text()
                        
                        # Check if this is someone looking for services
                        looking_keywords = [
                            'looking for', 'need help', 'seeking', 'want to hire',
                            'pay for', 'budget', 'project', 'freelancer', 'contractor'
                        ]
                        
                        if any(keyword in text.lower() for keyword in looking_keywords):
                            # Get tweet URL
                            tweet_link = await tweet.query_selector('a[href*="/status/"]')
                            url = await tweet_link.get_attribute('href') if tweet_link else ''
                            if url and not url.startswith('http'):
                                url = f"https://twitter.com{url}"
                            
                            lead = {
                                'platform': 'Twitter',
                                'title': text[:100] + '...' if len(text) > 100 else text,
                                'content': text,
                                'url': url,
                                'author': '',  # Would need more complex extraction
                                'score': 0,  # Twitter doesn't have scores like Reddit
                                'num_comments': 0,
                                'created_utc': int(time.time()),
                                'keyword_matched': keyword
                            }
                            leads.append(lead)
                            
                except Exception as e:
                    self.logger.error(f"Error extracting tweet: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error searching Twitter: {e}")
            
        return leads

class LinkedInSource(BaseLeadSource):
    """LinkedIn lead source for finding people looking for AI automation services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
    async def search_leads(
        self,
        keywords: List[str],
        max_posts: int = 50
    ) -> List[Dict[str, Any]]:
        """Search LinkedIn for leads."""
        leads = []
        
        for keyword in keywords:
            try:
                keyword_leads = await self._search_linkedin(keyword, max_posts // len(keywords))
                leads.extend(keyword_leads)
                await random_delay(2, 5)
            except Exception as e:
                self.logger.error(f"Error searching LinkedIn for {keyword}: {e}")
                
        return self.deduplicate_leads(leads)
    
    async def _search_linkedin(self, keyword: str, max_posts: int) -> List[Dict[str, Any]]:
        """Search LinkedIn for leads."""
        leads = []
        
        try:
            await self.init_browser()
            
            # Search LinkedIn posts
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={quote_plus(keyword)}&origin=GLOBAL_SEARCH_HEADER"
            await self.page.goto(search_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Extract posts
            posts = await self.page.query_selector_all('.feed-shared-update-v2')
            
            for post in posts[:max_posts]:
                try:
                    # Extract post content
                    content_elem = await post.query_selector('.feed-shared-text')
                    if content_elem:
                        text = await content_elem.inner_text()
                        
                        # Check if this is someone looking for services
                        looking_keywords = [
                            'looking for', 'need help', 'seeking', 'want to hire',
                            'pay for', 'budget', 'project', 'freelancer', 'contractor'
                        ]
                        
                        if any(keyword in text.lower() for keyword in looking_keywords):
                            # Get post URL
                            post_link = await post.query_selector('a[href*="/posts/"]')
                            url = await post_link.get_attribute('href') if post_link else ''
                            if url and not url.startswith('http'):
                                url = f"https://linkedin.com{url}"
                            
                            lead = {
                                'platform': 'LinkedIn',
                                'title': text[:100] + '...' if len(text) > 100 else text,
                                'content': text,
                                'url': url,
                                'author': '',  # Would need more complex extraction
                                'score': 0,
                                'num_comments': 0,
                                'created_utc': int(time.time()),
                                'keyword_matched': keyword
                            }
                            leads.append(lead)
                            
                except Exception as e:
                    self.logger.error(f"Error extracting LinkedIn post: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error searching LinkedIn: {e}")
            
        return leads

class FacebookGroupsSource(BaseLeadSource):
    """Facebook Groups lead source for finding people looking for AI automation services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.groups = [
            'Freelancers & Remote Workers',
            'Startup Founders',
            'Small Business Owners',
            'Entrepreneurs Network',
            'AI & Automation'
        ]
        
    async def search_leads(
        self,
        keywords: List[str],
        max_posts: int = 50
    ) -> List[Dict[str, Any]]:
        """Search Facebook Groups for leads."""
        leads = []
        
        for group in self.groups:
            for keyword in keywords:
                try:
                    group_leads = await self._search_facebook_group(group, keyword, max_posts // (len(self.groups) * len(keywords)))
                    leads.extend(group_leads)
                    await random_delay(2, 5)
                except Exception as e:
                    self.logger.error(f"Error searching Facebook group {group} for {keyword}: {e}")
                    
        return self.deduplicate_leads(leads)
    
    async def _search_facebook_group(self, group: str, keyword: str, max_posts: int) -> List[Dict[str, Any]]:
        """Search a Facebook group for leads."""
        leads = []
        
        try:
            await self.init_browser()
            
            # Facebook group search URL (simplified)
            search_url = f"https://www.facebook.com/search/posts/?q={quote_plus(keyword)}&filters=eyJycF9hdXRob3IiOiJ7XCJuYW1lXCI6XCJhdXRob3JcIixcImFyZ3NcIjpcIlwifSJ9"
            await self.page.goto(search_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Extract posts
            posts = await self.page.query_selector_all('[data-testid="post_message"]')
            
            for post in posts[:max_posts]:
                try:
                    text = await post.inner_text()
                    
                    # Check if this is someone looking for services
                    looking_keywords = [
                        'looking for', 'need help', 'seeking', 'want to hire',
                        'pay for', 'budget', 'project', 'freelancer', 'contractor'
                    ]
                    
                    if any(keyword in text.lower() for keyword in looking_keywords):
                        lead = {
                            'platform': 'Facebook',
                            'group': group,
                            'title': text[:100] + '...' if len(text) > 100 else text,
                            'content': text,
                            'url': '',  # Facebook URLs are complex to extract
                            'author': '',
                            'score': 0,
                            'num_comments': 0,
                            'created_utc': int(time.time()),
                            'keyword_matched': keyword
                        }
                        leads.append(lead)
                        
                except Exception as e:
                    self.logger.error(f"Error extracting Facebook post: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error searching Facebook: {e}")
            
        return leads

class LeadFinder:
    """Main lead finder class that coordinates searching across multiple platforms."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.logger = logger
        self.sources = {
            'reddit': RedditSource(self.config),
            'twitter': TwitterSource(self.config),
            'linkedin': LinkedInSource(self.config),
            'facebook': FacebookGroupsSource(self.config)
        }
        
    async def search_all_leads(
        self,
        keywords: List[str],
        max_posts_per_source: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for leads across all platforms."""
        all_leads = []
        
        for source_name, source in self.sources.items():
            try:
                self.logger.info(f"Searching {source_name} for leads...")
                leads = await source.search_leads(keywords, max_posts_per_source)
                all_leads.extend(leads)
                self.logger.info(f"Found {len(leads)} leads from {source_name}")
            except Exception as e:
                self.logger.error(f"Error searching {source_name}: {e}")
                
        return all_leads
    
    def filter_leads_by_interactions(self, leads: List[Dict[str, Any]], max_interactions: int = 10) -> List[Dict[str, Any]]:
        """Filter leads to only include those with low interaction counts."""
        filtered_leads = []
        
        for lead in leads:
            # Calculate interaction score (comments + likes/upvotes)
            interactions = lead.get('num_comments', 0) + lead.get('score', 0)
            
            if interactions <= max_interactions:
                filtered_leads.append(lead)
                
        return filtered_leads
    
    def sort_leads_by_date(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort leads by date (most recent first)."""
        return sorted(leads, key=lambda x: x.get('created_utc', 0), reverse=True)
    
    def save_leads_to_csv(self, leads: List[Dict[str, Any]], filename: str = "ai_automation_leads.csv"):
        """Save leads to CSV file."""
        if not leads:
            self.logger.warning("No leads to save")
            return
            
        fieldnames = [
            'platform', 'title', 'content', 'url', 'author', 
            'score', 'num_comments', 'created_utc', 'keyword_matched'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                writer.writerow(lead)
                
        self.logger.info(f"Saved {len(leads)} leads to {filename}")
    
    async def close_all_sources(self):
        """Close all source browsers."""
        for source in self.sources.values():
            await source.close()

def get_lead_source(source_name: str, config: Dict[str, Any]) -> BaseLeadSource:
    """Factory function to get lead source by name."""
    sources = {
        'reddit': RedditSource,
        'twitter': TwitterSource,
        'linkedin': LinkedInSource,
        'facebook': FacebookGroupsSource
    }
    
    if source_name not in sources:
        raise ValueError(f"Unknown lead source: {source_name}")
        
    return sources[source_name](config)

async def find_ai_automation_leads(
    keywords: List[str] = None,
    max_posts_per_source: int = 50,
    max_interactions: int = 10,
    output_file: str = "ai_automation_leads.csv"
) -> List[Dict[str, Any]]:
    """Main function to find AI automation leads."""
    if keywords is None:
        keywords = [
            "pay for AI automation",
            "looking for AI automation",
            "need AI automation help",
            "hire AI automation",
            "AI automation services",
            "automation project",
            "AI automation budget",
            "automation freelancer",
            "AI automation contractor"
        ]
    
    config = load_config()
    finder = LeadFinder()
    
    try:
        # Search for leads
        all_leads = await finder.search_all_leads(keywords, max_posts_per_source)
        
        # Filter by interactions
        filtered_leads = finder.filter_leads_by_interactions(all_leads, max_interactions)
        
        # Sort by date
        sorted_leads = finder.sort_leads_by_date(filtered_leads)
        
        # Save to CSV
        finder.save_leads_to_csv(sorted_leads, output_file)
        
        logger.info(f"Found {len(sorted_leads)} leads with low interactions")
        
        return sorted_leads
        
    finally:
        await finder.close_all_sources()

if __name__ == "__main__":
    asyncio.run(find_ai_automation_leads())