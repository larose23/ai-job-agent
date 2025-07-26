#!/usr/bin/env python3
"""
Simplified Lead Finder for AI Automation Agency
Works with basic packages: requests, beautifulsoup4, python-dotenv
"""

import requests
import json
import csv
import time
import random
from datetime import datetime
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# User agents to avoid blocking
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
]

def search_reddit_leads(keywords, max_posts=20):
    """Search Reddit for AI automation leads."""
    leads = []
    
    subreddits = ['forhire', 'freelance', 'startups', 'entrepreneur', 'smallbusiness']
    
    for subreddit in subreddits:
        for keyword in keywords:
            try:
                # Reddit search URL
                search_url = f"https://www.reddit.com/r/{subreddit}/search.json?q={quote_plus(keyword)}&restrict_sr=1&sort=new&t=week"
                
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'application/json'
                }
                
                response = requests.get(search_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                for post in posts[:max_posts//len(subreddits)]:
                    post_data = post.get('data', {})
                    
                    # Check if post is looking for services
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
                
                # Small delay to be respectful
                time.sleep(1)
                
            except Exception as e:
                print(f"Error searching r/{subreddit} for {keyword}: {e}")
    
    return leads

def search_twitter_leads(keywords, max_posts=20):
    """Search Twitter for AI automation leads (simplified)."""
    leads = []
    
    # Note: Twitter scraping is more complex and may require additional tools
    # For now, we'll return a placeholder
    print("Twitter search requires additional setup (browser automation)")
    print("Consider using Twitter API or browser automation tools")
    
    return leads

def filter_leads_by_interactions(leads, max_interactions=10):
    """Filter leads to only include those with low interaction counts."""
    filtered_leads = []
    
    for lead in leads:
        # Calculate interaction score (comments + likes/upvotes)
        interactions = lead.get('num_comments', 0) + lead.get('score', 0)
        
        if interactions <= max_interactions:
            filtered_leads.append(lead)
            
    return filtered_leads

def sort_leads_by_date(leads):
    """Sort leads by date (most recent first)."""
    return sorted(leads, key=lambda x: x.get('created_utc', 0), reverse=True)

def save_leads_to_csv(leads, filename="ai_automation_leads.csv"):
    """Save leads to CSV file."""
    if not leads:
        print("No leads to save")
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
            
    print(f"Saved {len(leads)} leads to {filename}")

def find_ai_automation_leads():
    """Main function to find AI automation leads."""
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
    
    print("🤖 AI Lead Finder Starting...")
    print("=" * 40)
    
    # Search Reddit
    print("🔍 Searching Reddit...")
    reddit_leads = search_reddit_leads(keywords, max_posts=50)
    print(f"   Found {len(reddit_leads)} leads from Reddit")
    
    # Search Twitter (placeholder)
    print("🔍 Searching Twitter...")
    twitter_leads = search_twitter_leads(keywords, max_posts=20)
    print(f"   Found {len(twitter_leads)} leads from Twitter")
    
    # Combine all leads
    all_leads = reddit_leads + twitter_leads
    
    if not all_leads:
        print("❌ No leads found. This could be due to:")
        print("   - Network connectivity issues")
        print("   - Platform rate limiting")
        print("   - No recent posts matching criteria")
        return []
    
    # Filter by interactions
    print(f"\n📊 Filtering {len(all_leads)} leads by interaction count...")
    filtered_leads = filter_leads_by_interactions(all_leads, max_interactions=10)
    print(f"   {len(filtered_leads)} leads with low interactions")
    
    # Sort by date
    sorted_leads = sort_leads_by_date(filtered_leads)
    
    # Save to CSV
    save_leads_to_csv(sorted_leads)
    
    # Show summary
    print(f"\n✅ Lead search completed!")
    print(f"📊 Found {len(sorted_leads)} potential AI automation clients")
    
    if sorted_leads:
        print(f"\n📋 Top leads found:")
        for i, lead in enumerate(sorted_leads[:5], 1):
            platform = lead.get('platform', 'Unknown')
            title = lead.get('title', 'No title')[:80]
            interactions = lead.get('num_comments', 0) + lead.get('score', 0)
            print(f"  {i}. [{platform}] {title} (interactions: {interactions})")
    
    return sorted_leads

if __name__ == "__main__":
    leads = find_ai_automation_leads()