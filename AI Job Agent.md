# AI Job Agent

A modular, production-ready Python application that functions as a near-fully automated AI Job Search Assistant. The system scrapes high-paying jobs in the UAE and fully remote roles in Canada, parses job alert emails, tailors resumes using AI, generates cover letters, semi-automates applications, sends cold outreach emails, and tracks everything in Google Sheets.

## Features

- **Multi-Source Job Scraping**: Automatically scrapes jobs from LinkedIn and Indeed
- **Email Integration**: Parses job alert emails from Gmail
- **AI-Powered Customization**: Uses OpenAI GPT-4 to tailor resumes and generate cover letters
- **Google Sheets Tracking**: Comprehensive job application tracking and metrics
- **Email Automation**: Sends personalized cold outreach emails to recruiters
- **Deduplication**: Intelligent job deduplication across all sources
- **Salary Filtering**: Filters jobs based on minimum salary requirements
- **Anti-Bot Measures**: Implements rate limiting and stealth browsing
- **Modular Design**: Clean, maintainable code with clear separation of concerns

## Project Structure

```
ai_job_agent/
├── main.py                 # Main orchestration and CLI interface
├── job_scraper.py          # LinkedIn and Indeed job scraping
├── resume_tailor.py        # AI-powered resume tailoring and cover letters
├── email_scanner.py        # Gmail job alert parsing
├── sheets_logger.py        # Google Sheets integration
├── email_sender.py         # Cold email automation
├── utils.py                # Common utilities and helpers
├── config.json             # Configuration file (create from template)
├── requirements.txt        # Python dependencies
└── data/
    ├── base_resume.txt     # Your base resume template
    ├── jobs.csv            # Local job data cache
    └── cover_letters/      # Generated cover letters and delta resumes
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Google Cloud Console account (for Gmail and Sheets APIs)
- OpenAI API account
- LinkedIn account (for job scraping)

### Step 1: Clone and Setup

```bash
# Clone or download the project
cd ai_job_agent

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Step 2: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the following APIs:
   - Gmail API
   - Google Sheets API
4. Create credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
   - Choose "Desktop Application"
   - Download the JSON file and save as `credentials.json` in the project root

### Step 3: Google Sheets Setup

1. Create a new Google Spreadsheet
2. Copy the spreadsheet ID from the URL (the long string between `/d/` and `/edit`)
3. Share the spreadsheet with your Google account email

### Step 4: Configuration

1. Copy the configuration template:
```bash
cp config.json config.json.example  # Backup template
```

2. Edit `config.json` with your credentials:

```json
{
  "openai_api_key": "sk-your-openai-api-key",
  "spreadsheet_id": "your-google-sheet-id",
  "gmail_sender_email": "your-email@gmail.com",
  "gmail_app_password": "your-app-specific-password",
  "google_credentials_json_path": "credentials.json",
  "linkedin_email": "your-linkedin-email",
  "linkedin_password": "your-linkedin-password",
  "keywords": ["AI Engineer", "Data Scientist", "Product Manager"],
  "locations": ["Dubai", "Remote Canada"],
  "min_salary_aed": 10000,
  "max_results_per_source": 20,
  "job_alert_label": "Job Alerts",
  "sheet_name": "Jobs",
  "metrics_sheet_name": "Metrics"
}
```

### Step 5: Gmail App Password Setup

1. Enable 2-Factor Authentication on your Google account
2. Go to Google Account settings → Security → App passwords
3. Generate an app password for "Mail"
4. Use this password in the `gmail_app_password` field

### Step 6: Resume Setup

Edit `data/base_resume.txt` with your resume content. This will be used as the foundation for AI-powered tailoring.

## Usage

### Command Line Interface

The application provides several modes of operation:

```bash
# Scrape new jobs and tailor resumes
python main.py --scrape

# Send cold outreach emails
python main.py --send_emails

# Mark jobs as applied (provide row numbers from Google Sheets)
python main.py --mark_applied 5 7 12

# Test all system components
python main.py --test

# Show system status
python main.py --status

# Use custom config file
python main.py --config my_config.json --scrape

# Set logging level
python main.py --log-level DEBUG --test
```

### Typical Workflow

1. **Initial Setup**: Run `python main.py --test` to verify all components
2. **Job Discovery**: Run `python main.py --scrape` to find and process new jobs
3. **Email Outreach**: Run `python main.py --send_emails` to send cold emails
4. **Application Tracking**: Use `python main.py --mark_applied <row_numbers>` when you apply
5. **Monitoring**: Use `python main.py --status` to check system health

### Automation with Cron

Set up automated job searching with cron jobs:

```bash
# Edit crontab
crontab -e

# Add these lines for automation:
# Scrape jobs every 6 hours
0 */6 * * * cd /path/to/ai_job_agent && python main.py --scrape

# Send cold emails every 12 hours
0 */12 * * * cd /path/to/ai_job_agent && python main.py --send_emails

# Daily status check
0 9 * * * cd /path/to/ai_job_agent && python main.py --status
```

## Configuration Reference

### Required Settings

| Setting | Description | Example |
|---------|-------------|---------|
| `openai_api_key` | OpenAI API key for GPT-4 | `sk-...` |
| `spreadsheet_id` | Google Sheets ID | `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms` |
| `gmail_sender_email` | Your Gmail address | `user@gmail.com` |
| `keywords` | Job search keywords | `["AI Engineer", "Data Scientist"]` |
| `locations` | Target locations | `["Dubai", "Remote Canada"]` |

### Optional Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `min_salary_aed` | Minimum salary in AED | `10000` |
| `max_results_per_source` | Max jobs per source | `20` |
| `job_alert_label` | Gmail label for job alerts | `"Job Alerts"` |
| `sheet_name` | Main tracking sheet name | `"Jobs"` |
| `metrics_sheet_name` | Metrics sheet name | `"Metrics"` |

## Google Sheets Structure

The application automatically creates two sheets:

### Jobs Sheet Columns
- **Date**: When the job was found
- **Title**: Job title
- **Company**: Company name
- **Location**: Job location
- **Salary**: Salary information
- **Job URL**: Link to job posting
- **Status**: Application status (New, Applied, etc.)
- **Delta Resume File**: Path to tailored resume
- **Cover Letter File**: Path to cover letter
- **Recruiter Email**: Extracted recruiter email
- **Cold Email Sent**: Whether outreach email was sent
- **Applied**: Whether you applied to the job
- **Source**: Where the job was found
- **Notes**: Additional notes

### Metrics Sheet Columns
- **Date**: Date of metrics
- **Jobs Scraped**: Number of jobs found
- **Resumes Tailored**: Number of resumes customized
- **Cover Letters Generated**: Number of cover letters created
- **Emails Sent**: Number of cold emails sent
- **Applications Submitted**: Number of applications made
- **Responses Received**: Number of responses (manual entry)

## Troubleshooting

### Common Issues

**"Configuration file not found"**
- Ensure `config.json` exists in the project root
- Check file permissions

**"Google credentials file not found"**
- Download `credentials.json` from Google Cloud Console
- Place it in the project root directory

**"LinkedIn login failed"**
- Verify LinkedIn credentials in config
- Check if account has 2FA enabled
- LinkedIn may require manual verification

**"OpenAI API error"**
- Verify API key is correct and active
- Check OpenAI account billing status
- Ensure sufficient API credits

**"Gmail authentication failed"**
- Use app-specific password, not regular password
- Enable 2-Factor Authentication first
- Check Gmail API is enabled in Google Cloud

**"No jobs found"**
- Adjust search keywords and locations
- Check minimum salary requirements
- Verify job sites are accessible

### Debug Mode

Run with debug logging for detailed information:

```bash
python main.py --log-level DEBUG --test
```

### Testing Individual Components

Each module can be tested independently:

```bash
# Test job scraping
python job_scraper.py

# Test email scanning
python email_scanner.py

# Test resume tailoring
python resume_tailor.py

# Test Google Sheets
python sheets_logger.py

# Test email sending
python email_sender.py
```

## Security Considerations

- **API Keys**: Never commit `config.json` to version control
- **Credentials**: Store Google credentials securely
- **Rate Limiting**: Built-in delays prevent being blocked
- **Email Limits**: Gmail has daily sending limits
- **LinkedIn ToS**: Use responsibly to avoid account restrictions

## Performance Optimization

- **Batch Processing**: Emails sent in batches to avoid rate limits
- **Caching**: Local CSV cache reduces API calls
- **Deduplication**: Prevents processing duplicate jobs
- **Error Handling**: Robust error handling with retries
- **Logging**: Comprehensive logging for monitoring

## Extending the System

### Adding New Job Sources

1. Create scraping function in `job_scraper.py`
2. Follow existing patterns for data structure
3. Add to `scrape_all_jobs()` function

### Custom Email Templates

Modify `email_sender.py`:
- `create_cold_email_body()` for email content
- `create_subject_line()` for subject formatting

### Additional Metrics

Add new metrics in `sheets_logger.py`:
- Update `METRICS_HEADERS`
- Modify `log_daily_metrics()`

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files (`ai_job_agent.log`)
3. Test individual components
4. Verify all credentials and configurations

## License

This project is for personal use. Ensure compliance with:
- LinkedIn Terms of Service
- Indeed Terms of Service
- OpenAI Usage Policies
- Google API Terms of Service

---

**Disclaimer**: This tool is for personal job search automation. Use responsibly and in compliance with all applicable terms of service and local laws.

