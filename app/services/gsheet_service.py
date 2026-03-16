import os
import logging
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import time

load_dotenv()

logger = logging.getLogger(__name__)

class GSheetService:
    def __init__(self):
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.range_name = os.getenv("SHEET_RANGE", "Sheet1!A:C")
        self.creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "app/service-account.json")
        self._cache: Optional[List[Dict[str, str]]] = None
        self._last_fetch_time: float = 0
        self._cache_ttl: int = 60  # 1 minute cache

    def _get_credentials(self):
        if not os.path.exists(self.creds_path):
            raise FileNotFoundError(f"Service account file not found at {self.creds_path}")
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        return service_account.Credentials.from_service_account_file(
            self.creds_path, scopes=scopes
        )

    def fetch_merchant_rules(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Fetches merchant rules from Google Sheets and returns them as a list of dicts.
        """
        # Check cache
        current_time = time.time()
        if not force_refresh and self._cache and (current_time - self._last_fetch_time < self._cache_ttl):
            logger.info("Returning cached merchant rules")
            return self._cache

        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID not set in environment")
            return []

        try:
            creds = self._get_credentials()
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.warning("No data found in Google Sheet")
                return []

            # Assume first row is header: merchant, category, tag
            headers = [h.lower() for h in values[0]]
            rules = []
            
            for row in values[1:]:
                if not row:
                    continue
                # Ensure we have at least 3 columns, fill with empty string if missing
                rule = {}
                for i, header in enumerate(headers):
                    rule[header] = row[i] if i < len(row) else ""
                rules.append(rule)

            self._cache = rules
            self._last_fetch_time = current_time
            logger.info(f"Successfully fetched {len(rules)} merchant rules from Google Sheets")
            return rules

        except Exception as e:
            logger.error(f"Error fetching from Google Sheets: {str(e)}")
            # If fetch fails but we have cache, return cache as fallback
            if self._cache:
                logger.warning("Fetch failed, returning stale cache")
                return self._cache
            raise e

    def add_merchant_rule(self, rule: Dict[str, str]) -> bool:
        """
        Appends a new merchant rule (merchant, category, tag) to the Google Sheet.
        """
        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID not set in environment")
            return False

        try:
            creds = self._get_credentials()
            service = build('sheets', 'v4', credentials=creds)
            
            # Prepare the row data
            # Rule dictionary expects keys: merchant, category, tag
            row_data = [
                rule.get("merchant", ""),
                rule.get("category", ""),
                rule.get("tag", "")
            ]
            
            body = {
                'values': [row_data]
            }
            
            # Range for appending - using the same range but without A:C if it's dynamic
            # sheet_name = self.range_name.split('!')[0] if '!' in self.range_name else "Sheet1"
            append_range = self.range_name
            
            result = service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=append_range,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            # Invalidate cache
            self._cache = None
            logger.info(f"Successfully added new merchant rule to Google Sheets: {rule}")
            return True

        except Exception as e:
            logger.error(f"Error adding to Google Sheets: {str(e)}")
            raise e

# Singleton instance
gsheet_service = GSheetService()


# -------------------------------
# Run this block if script is executed directly
# -------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        rules = gsheet_service.fetch_merchant_rules()
        if not rules:
            logger.info("No merchant rules to display.")
        else:
            logger.info("First 10 merchant rules:")
            for i, rule in enumerate(rules[:10], start=1):
                logger.info(f"{i}: {rule}")
    except Exception as ex:
        logger.error(f"Failed to fetch merchant rules: {ex}")