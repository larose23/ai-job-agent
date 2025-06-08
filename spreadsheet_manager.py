"""
Google Sheets management module for the AI Job Agent application.
Handles authentication and operations with Google Sheets API.
"""

import os
from typing import List, Dict, Any, Optional, Union
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from helpers import (
    retry_network,
    retry_auth,
    safe_operation,
    logger,
    notify_slack
)

class SpreadsheetManager:
    """Google Sheets manager with authentication and CRUD operations."""
    
    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json") -> None:
        """
        Initialize spreadsheet manager with credentials.
        
        Args:
            spreadsheet_id: ID of the Google Sheet to manage
            credentials_path: Path to Google API credentials file
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.service = None
        self.creds = None
        
    @retry_auth
    def authenticate(self) -> None:
        """
        Authenticate with Google Sheets API with retry logic.
        
        Raises:
            Exception: If authentication fails after retries
        """
        try:
            # Load credentials from file
            if os.path.exists('token.json'):
                self.creds = Credentials.from_authorized_user_file('token.json')
                
            # Refresh credentials if expired
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path,
                        ['https://www.googleapis.com/auth/spreadsheets']
                    )
                    self.creds = flow.run_local_server(port=0)
                    
                # Save credentials
                with open('token.json', 'w') as token:
                    token.write(self.creds.to_json())
                    
            # Build service
            self.service = build('sheets', 'v4', credentials=self.creds)
            logger.info("Successfully authenticated with Google Sheets API")
            
        except Exception as e:
            error_msg = f"Google Sheets authentication failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def append_rows(
        self,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Append rows to a Google Sheet with retry logic.
        
        Args:
            range_name: A1 notation of the range to append to
            values: List of rows to append
            value_input_option: How input data should be interpreted
                - USER_ENTERED: Values are parsed as if typed into the UI
                - RAW: Values are not parsed and inserted as-is
                
        Returns:
            Dict containing:
                - spreadsheetId: ID of the spreadsheet
                - tableRange: Range that was updated
                - updates: Details about the update
                
        Raises:
            Exception: If append operation fails after retries
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Successfully appended {len(values)} rows to {range_name}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to append rows to {range_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def update_cells(
        self,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Update cells in a Google Sheet with retry logic.
        
        Args:
            range_name: A1 notation of the range to update
            values: List of rows to update
            value_input_option: How input data should be interpreted
                - USER_ENTERED: Values are parsed as if typed into the UI
                - RAW: Values are not parsed and inserted as-is
                
        Returns:
            Dict containing:
                - spreadsheetId: ID of the spreadsheet
                - updatedRange: Range that was updated
                - updatedRows: Number of rows updated
                - updatedColumns: Number of columns updated
                - updatedCells: Number of cells updated
                
        Raises:
            Exception: If update operation fails after retries
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            
            logger.info(f"Successfully updated cells in {range_name}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to update cells in {range_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def get_values(
        self,
        range_name: str,
        major_dimension: str = "ROWS"
    ) -> Optional[List[List[Any]]]:
        """
        Get values from a Google Sheet with retry logic.
        
        Args:
            range_name: A1 notation of the range to get
            major_dimension: The major dimension that results should use
                - ROWS: Results are returned as rows
                - COLUMNS: Results are returned as columns
                
        Returns:
            Optional[List[List[Any]]]: Values from the range, or None if range is empty
            
        Raises:
            Exception: If get operation fails after retries
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                majorDimension=major_dimension
            ).execute()
            
            values = result.get('values', [])
            logger.info(f"Successfully retrieved {len(values)} rows from {range_name}")
            return values
            
        except Exception as e:
            error_msg = f"Failed to get values from {range_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise
            
    @retry_network
    def clear_range(self, range_name: str) -> Dict[str, Any]:
        """
        Clear values from a range in a Google Sheet with retry logic.
        
        Args:
            range_name: A1 notation of the range to clear
            
        Returns:
            Dict containing:
                - spreadsheetId: ID of the spreadsheet
                - clearedRange: Range that was cleared
                
        Raises:
            Exception: If clear operation fails after retries
        """
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            logger.info(f"Successfully cleared range {range_name}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to clear range {range_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            notify_slack(error_msg)
            raise


def create_spreadsheet_manager() -> SpreadsheetManager:
    """
    Create a SpreadsheetManager instance using environment variables.
    
    Returns:
        SpreadsheetManager instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    
    if not spreadsheet_id:
        error_msg = "Google Sheet ID not found in environment variables"
        logger.error(error_msg)
        notify_slack(error_msg)
        raise ValueError(error_msg)
        
    return SpreadsheetManager(spreadsheet_id, credentials_path)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Test spreadsheet operations
        manager = create_spreadsheet_manager()
        manager.authenticate()
        
        # Test append
        test_data = [
            ['Test', 'Data', 'Row 1'],
            ['Test', 'Data', 'Row 2']
        ]
        result = manager.append_rows('Sheet1!A1', test_data)
        logger.info(f"Append result: {result}")
        
        # Test get
        values = manager.get_values('Sheet1!A1:C2')
        logger.info(f"Retrieved values: {values}")
        
        # Test clear
        result = manager.clear_range('Sheet1!A1:C2')
        logger.info(f"Clear result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1) 