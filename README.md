# AI Job Agent & Lead Finder

An AI-powered automation tool with two main functions:

## 🤖 Job Application Mode (Original)
- Automated job searching across multiple platforms
- AI-powered resume tailoring
- Automated email outreach
- Job tracking and metrics
- Multi-platform support (LinkedIn, Indeed, Bayt, etc.)

## 🎯 Lead Finder Mode (NEW)
- **AI Automation Agency Lead Generation**
- Searches for people willing to pay for AI automation services
- Multi-platform lead discovery (Reddit, Twitter, LinkedIn, Facebook)
- Filters for low-engagement, recent posts
- Exports qualified leads to CSV
- **NO job applications** - only lead discovery

## Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account (for Google Sheets API)
- OpenAI API key
- Gmail account with App Password
- LinkedIn account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-job-agent.git
cd ai-job-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.template` to `.env`
   - Fill in all required environment variables

## Environment Variables

Required environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key
- `GMAIL_SENDER_EMAIL`: Your Gmail address
- `GMAIL_APP_PASSWORD`: Gmail App Password (not your regular password)
- `SPREADSHEET_ID`: Google Sheets ID for job tracking
- `GOOGLE_CREDENTIALS_JSON_PATH`: Path to Google Cloud credentials JSON file
- `LINKEDIN_EMAIL`: Your LinkedIn email
- `LINKEDIN_PASSWORD`: Your LinkedIn password

Optional environment variables:

- `FIXER_IO_API_KEY`: API key for currency conversion
- `SLACK_WEBHOOK_URL`: Slack webhook URL for notifications
- `HTTP_PROXY`: HTTP proxy URL (if needed)
- `HTTPS_PROXY`: HTTPS proxy URL (if needed)
- `USER_FULL_NAME`: Your full name
- `USER_EMAIL`: Your email address
- `USER_PHONE`: Your phone number
- `RESUME_FILE_PATH`: Path to your resume file
- `LINKEDIN_PROFILE_URL`: Your LinkedIn profile URL
- `NOTIFICATION_EMAIL`: Email for job alerts

## Setup

1. Set up Google Cloud:
   - Create a new project
   - Enable Google Sheets API
   - Create service account credentials
   - Download credentials JSON file
   - Share your Google Sheet with the service account email

2. Set up Gmail:
   - Enable 2-factor authentication
   - Generate an App Password
   - Add the App Password to your .env file

3. Configure the application:
   - Edit config.json with your preferences
   - Set up your resume in data/base_resume.txt
   - For lead finder: Configure keywords and platforms in config.json lead_search section

## Usage

### Job Application Mode (Original)

1. Test the setup:
```bash
python main.py --test
```

2. Start job searching:
```bash
python main.py --scrape
```

3. Send application emails:
```bash
python main.py --send-emails
```

### Lead Finder Mode (NEW)

1. Test the lead finder:
```bash
python test_lead_finder.py
```

2. Run lead search:
```bash
python run_lead_finder.py
```

3. Test individual sources:
```bash
python run_lead_finder.py test
```

4. Advanced lead search:
```bash
python lead_finder_main.py --keywords "AI automation" "automation help" --max-posts 100
```

**📋 Lead Finder Output**: Results are saved to `ai_automation_leads.csv` with platform, content, URL, and interaction data.

## Security Notes

- Never commit your .env file or credentials
- Keep your API keys and passwords secure
- Regularly rotate your credentials
- Use environment variables for all sensitive data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Project Structure

```
ai-job-agent/
├── cli.py              # Command-line interface
├── job_agent.py        # Main job agent logic
├── job_scraper.py      # Job scraping functionality
├── linkedin_scraper.py # LinkedIn-specific scraping
├── gmail_sender.py     # Email notification system
├── spreadsheet_manager.py # Google Sheets integration
├── resume_tailor.py    # Resume customization
├── helpers.py          # Utility functions
├── requirements.txt    # Project dependencies
└── README.md          # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

### Automation Policy

For every code change, improvement, or bug fix, the contributor must include a Cursor AI automation prompt that allows the change to be implemented automatically. This ensures consistent and fast development, especially for infrastructure and repetitive updates.

#### Requirements for Tasks:
- [ ] Include a Cursor AI automation prompt with each task or update
- [ ] Ensure the prompt is clear and actionable
- [ ] Test the automation before submitting changes
- [ ] Document any manual steps that cannot be automated

Example automation prompt format:
```markdown
💡 Goal: [Clear description of the change]

🎯 Tasks (automate in sequence):
1. [Step 1]
2. [Step 2]
3. [Step 3]

✅ Success Criteria:
- [ ] [Criterion 1]
- [ ] [Criterion 2]
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the AI capabilities
- Google Cloud Platform for spreadsheet integration
- LinkedIn for job data 