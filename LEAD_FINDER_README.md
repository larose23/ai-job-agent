# AI Lead Finder for Automation Agency

This module has been modified from the original job application automation system to find potential clients for your AI automation agency. Instead of applying for jobs, it searches for people who are willing to pay for AI automation services.

## 🎯 What It Does

The AI Lead Finder searches across multiple platforms to find people who:
- Are looking to pay for AI automation services
- Have posted recently (within the last week)
- Have low interaction counts (fewer comments/likes)
- Are actively seeking automation solutions

## 🚀 Quick Start

### 1. Basic Usage
```bash
# Run lead search (default)
python run_lead_finder.py

# Or explicitly
python run_lead_finder.py search
```

### 2. Test Sources
```bash
# Test all lead sources
python run_lead_finder.py test
```

### 3. Advanced Usage
```bash
# Use custom keywords
python lead_finder_main.py --keywords "AI automation" "automation help" --max-posts 100

# Custom output file
python lead_finder_main.py --output my_leads.csv --max-interactions 5
```

## 📊 Platforms Searched

The lead finder searches these platforms:

### Reddit
- **Subreddits**: r/forhire, r/freelance, r/startups, r/entrepreneur, r/smallbusiness, r/business, r/automation, r/ai, r/machinelearning
- **Search**: Recent posts with low interaction counts
- **Filter**: Posts looking for services (not offering)

### Twitter
- **Search**: Recent tweets about AI automation needs
- **Filter**: People seeking automation services
- **Method**: Public scraping (no API required)

### LinkedIn
- **Search**: Posts and discussions about automation needs
- **Filter**: Business owners seeking automation solutions
- **Method**: Public content scraping

### Facebook Groups
- **Groups**: Freelancers & Remote Workers, Startup Founders, Small Business Owners, Entrepreneurs Network, AI & Automation
- **Search**: Recent posts seeking automation services

## 🔍 Search Keywords

Default keywords that indicate someone is looking to pay for services:
- "pay for AI automation"
- "looking for AI automation"
- "need AI automation help"
- "hire AI automation"
- "AI automation services"
- "automation project"
- "AI automation budget"
- "automation freelancer"
- "AI automation contractor"
- "automation consultant"
- "AI automation expert"
- "automation setup"
- "AI automation implementation"
- "automation workflow"
- "AI automation tools"

## 📈 Output

The system generates a CSV file (`ai_automation_leads.csv`) with:
- **Platform**: Where the lead was found
- **Title**: Post title or summary
- **Content**: Full post content
- **URL**: Direct link to the post
- **Author**: Username (when available)
- **Score**: Upvotes/likes count
- **Num Comments**: Comment count
- **Created UTC**: Post timestamp
- **Keyword Matched**: Which keyword triggered the match

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "lead_search": {
    "enabled": true,
    "keywords": ["your", "custom", "keywords"],
    "max_posts_per_source": 50,
    "max_interactions": 10,
    "output_file": "ai_automation_leads.csv",
    "platforms": ["reddit", "twitter", "linkedin", "facebook"],
    "search_frequency_hours": 24
  }
}
```

## 🎯 Lead Qualification

The system automatically filters leads by:

1. **Intent**: Only posts seeking services (not offering)
2. **Recency**: Recent posts (within last week)
3. **Engagement**: Low interaction counts (≤10 by default)
4. **Relevance**: AI automation related keywords

## 📋 Sample Output

```
✅ Lead search completed successfully!
📊 Found 23 potential AI automation clients
💾 Results saved to: ai_automation_leads.csv

📋 Top leads found:
  1. [Reddit] Looking for AI automation help with customer service (interactions: 3)
  2. [Twitter] Need someone to set up automation for my e-commerce store (interactions: 1)
  3. [LinkedIn] Seeking AI automation expert for workflow optimization (interactions: 2)
  4. [Facebook] Pay for AI automation setup for small business (interactions: 0)
  5. [Reddit] Budget for automation project - need recommendations (interactions: 5)
```

## 🔧 Troubleshooting

### Common Issues

1. **No leads found**
   - Check your internet connection
   - Try different keywords
   - Increase `max_interactions` value
   - Run test mode to check sources

2. **Rate limiting**
   - The system includes delays between requests
   - If you get blocked, wait and try again later

3. **Platform changes**
   - Social media platforms update their structure
   - Check logs for selector errors
   - Update selectors if needed

### Testing Sources

```bash
python run_lead_finder.py test
```

This will test each platform individually and report which ones are working.

## 📝 Logs

Check `lead_finder.log` for detailed information about:
- Search progress
- Errors and warnings
- Lead counts by platform
- Performance metrics

## 🚨 Important Notes

- **No Application**: This tool only finds leads, it does NOT apply or contact anyone
- **Public Data**: Only searches publicly available content
- **Respectful**: Includes delays to avoid overwhelming platforms
- **Manual Follow-up**: You need to manually contact the leads found

## 🔄 Automation

To run automatically:

```bash
# Add to crontab for daily runs
0 9 * * * cd /path/to/project && python run_lead_finder.py

# Or use the built-in scheduling in config.json
```

## 📞 Next Steps

After finding leads:

1. **Review the CSV file** for quality leads
2. **Research each lead** before contacting
3. **Personalize your outreach** based on their specific needs
4. **Track responses** in your CRM
5. **Follow up** with non-responders

## 🤝 Support

If you need help:
1. Check the logs for error messages
2. Run test mode to isolate issues
3. Verify your configuration
4. Check platform accessibility

---

**Remember**: This tool finds opportunities, but building relationships and closing deals still requires human effort and skill!