# AI Lead Generation Agency

## Quick Start

1. **Run the lead finder:**
   ```bash
   python3 production_lead_finder.py
   ```

2. **Check results:**
   ```bash
   cat exports/ai_automation_leads.csv
   ```

3. **Schedule regular runs:**
   ```bash
   # Add to crontab for daily runs
   0 9 * * * cd /path/to/agency && python3 production_lead_finder.py
   ```

## Configuration

Edit `config.json` to customize:
- Keywords to search for
- Maximum interactions filter
- Output file location
- Platforms to search

## Files

- `production_lead_finder.py` - Main lead finder
- `working_lead_finder.py` - Simple version
- `config.json` - Configuration
- `exports/` - Generated CSV files
- `logs/` - Log files

## Next Steps

1. Review leads in CSV file
2. Research each lead
3. Personalize outreach
4. Track responses
5. Scale successful approaches

## Support

For issues or questions, check the logs in the logs/ directory.
