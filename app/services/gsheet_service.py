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
        self.range_name = os.getenv("SHEET_RANGE", "Sheet1!A:D")
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
            # 1. Fetch current rules to determine next ID
            current_rules = self.fetch_merchant_rules(force_refresh=True)
            next_id = 1
            if current_rules:
                ids = []
                for r in current_rules:
                    val = r.get("id")
                    if val is not None:
                        try:
                            ids.append(int(val))
                        except (ValueError, TypeError):
                            continue
                if ids:
                    next_id = max(ids) + 1

            creds = self._get_credentials()
            service = build('sheets', 'v4', credentials=creds)
            
            # Prepare the row data
            # Rule dictionary expects keys: merchant, category, tag
            row_data = [
                next_id,
                rule.get("merchant", ""),
                rule.get("category", ""),
                rule.get("tag", "")
            ]
            
            body = {
                'values': [row_data]
            }
            
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
            logger.info(f"Successfully added new merchant rule (ID: {next_id}) to Google Sheets: {rule}")
            return True

        except Exception as e:
            logger.error(f"Error adding to Google Sheets: {str(e)}")
            raise e

    def update_merchant_rule(self, rule_id: int, rule: Dict[str, str]) -> bool:
        """
        Updates an existing merchant rule by ID.
        """
        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID not set in environment")
            return False

        try:
            creds = self._get_credentials()
            service = build('sheets', 'v4', credentials=creds)
            
            # 1. Fetch values to find the row index
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            values = result.get('values', [])
            
            if not values:
                logger.error("No values found in Google Sheets")
                return False

            # Find the row index (headers are in values[0])
            row_index = -1
            for i, row in enumerate(values[1:], start=2):
                if row and len(row) > 0 and str(row[0]) == str(rule_id):
                    row_index = i
                    break
            
            if row_index == -1:
                logger.error(f"Rule with ID {rule_id} not found")
                return False

            # 2. Prepare updated row data
            # Keeping the ID the same
            row_data = [
                rule_id,
                rule.get("merchant", ""),
                rule.get("category", ""),
                rule.get("tag", "")
            ]
            
            # Map column index to letters (A=0, B=1, etc.)
            sheet_name = self.range_name.split('!')[0] if '!' in self.range_name else "Sheet1"
            update_range = f"{sheet_name}!A{row_index}:D{row_index}"
            
            body = {
                'values': [row_data]
            }
            
            service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            # Invalidate cache
            self._cache = None
            logger.info(f"Successfully updated merchant rule (ID: {rule_id})")
            return True

        except Exception as e:
            logger.error(f"Error updating Google Sheets: {str(e)}")
            raise e

    def delete_merchant_rule(self, rule_id: int) -> bool:
        """
        Deletes a merchant rule by ID.
        """
        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID not set in environment")
            return False

        try:
            creds = self._get_credentials()
            service = build('sheets', 'v4', credentials=creds)
            
            # 1. Fetch values to find the row index
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            values = result.get('values', [])
            
            if not values:
                logger.error("No values found in Google Sheets")
                return False

            # Find the row index
            target_row_idx = -1
            for i, row in enumerate(values[1:], start=1): # 0-indexed for batchUpdate, 1 is row after header
                if row and len(row) > 0 and str(row[0]) == str(rule_id):
                    target_row_idx = i
                    break
            
            if target_row_idx == -1:
                logger.error(f"Rule with ID {rule_id} not found")
                return False

            # 2. Delete the row using batchUpdate
            sheet_metadata = service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_name = self.range_name.split('!')[0] if '!' in self.range_name else "Sheet1"
            sheet_id = 0
            for s in sheet_metadata.get('sheets', []):
                if s.get('properties', {}).get('title') == sheet_name:
                    sheet_id = s.get('properties', {}).get('sheetId')
                    break

            batch_update_request = {
                'requests': [
                    {
                        'deleteDimension': {
                            'range': {
                                'sheetId': sheet_id,
                                'dimension': 'ROWS',
                                'startIndex': target_row_idx,
                                'endIndex': target_row_idx + 1
                            }
                        }
                    }
                ]
            }
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=batch_update_request
            ).execute()
            
            # Invalidate cache
            self._cache = None
            logger.info(f"Successfully deleted merchant rule (ID: {rule_id})")
            return True

        except Exception as e:
            logger.error(f"Error deleting from Google Sheets: {str(e)}")
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