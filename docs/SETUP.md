# Setup Guide

## Google Sheet Setup

### 1. Create a Google Sheet
1. Go to [Google Sheets](https://sheets.google.com)
2. Click "+ New" to create a new spreadsheet
3. Name it something like "Job Scraper Data"
4. Create the following columns in the first sheet:
   - Job Title
   - Company
   - Location
   - URL
   - Date Posted
   - Status
   - Notes

### 2. Find Your Service Account Email
1. Open your `google_credentials.json` file
2. Look for the `client_email` field
3. Copy the email address (it looks like: `something@project-id.iam.gserviceaccount.com`)

### 3. Share the Sheet with Service Account
1. In your Google Sheet, click the "Share" button (top right)
2. Paste the service account email in the "Add people and groups" field
3. Set permission to "Editor"
4. Uncheck "Notify people"
5. Click "Share"

### 4. Get the Sheet URL
1. Copy the URL from your browser's address bar
2. It should look like: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit#gid=0`
3. Use this URL in your `config.json` file:
   ```json
   {
     "google_sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit#gid=0"
   }
   ```

### 5. Verify Access
1. Run the script with:
   ```bash
   python main.py --config config.json --headful
   ```
2. Check the logs for successful sheet access
3. If you see a 404 error, double-check:
   - The sheet ID is correct
   - The service account has Editor access
   - The credentials file is properly loaded

### ⚠️ Important Notes
- The Google Sheet setup is **critical** for the app to function
- Without proper sheet access, job scraping will fail
- Keep your credentials secure and never commit them to version control
- If you change the sheet structure, update the code accordingly

### Troubleshooting
If you get a 404 error:
1. Verify the sheet ID in the URL
2. Check service account permissions
3. Ensure the credentials file is valid
4. Try accessing the sheet manually with the service account email

### Additional Resources
- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Service Account Setup Guide](https://developers.google.com/identity/protocols/oauth2/service-account)
- [Google Sheets Sharing Guide](https://support.google.com/docs/answer/2494822) 