# AI Job Agent

An intelligent job search assistant that automates the process of finding, analyzing, and applying to jobs using AI and web automation.

## Features

- 🔍 Automated job searching on LinkedIn
- 🤖 AI-powered job analysis and matching
- 📧 Automated email notifications for new job matches
- 📊 Google Sheets integration for job tracking
- 📝 AI-powered resume tailoring
- 🔄 Retry logic and error handling
- 📈 Progress tracking and logging

## Prerequisites

- Python 3.8+
- Google Cloud Platform account
- LinkedIn account
- Gmail account with App Password
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-job-agent.git
cd ai-job-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Create a `.env` file with the following variables:
```
OPENAI_API_KEY=your_openai_api_key
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password
GMAIL_ADDRESS=your_gmail_address
GMAIL_APP_PASSWORD=your_gmail_app_password
SPREADSHEET_ID=your_google_sheet_id
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

## Usage

1. Run the setup command to initialize the system:
```bash
python cli.py setup
```

2. Start a job search:
```bash
python cli.py search --keywords "python developer" --location "remote"
```

3. Check configuration:
```bash
python cli.py check-config
```

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the AI capabilities
- Google Cloud Platform for spreadsheet integration
- LinkedIn for job data 