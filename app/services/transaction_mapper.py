import logging
import json
import os
from app.services.gsheet_service import gsheet_service

logger = logging.getLogger(__name__)

class TransactionMapperService:
    def __init__(self):
        pass

    def load_merchant_rules(self):
        """
        Loads merchant rules from Google Sheets with fallback to local JSON.
        Using GSheetService which has its own TTL cache.
        """
        try:
            # Try fetching from Google Sheets first
            rules = gsheet_service.fetch_merchant_rules()
            if rules:
                logger.debug(f"Loaded {len(rules)} rules from GSheetService")
                return rules
            logger.warning("No merchant rules found in Google Sheets, trying local fallback")
        except Exception as e:
            logger.error(f"Error fetching merchant rules from Google Sheets: {e}")

        # Fallback to local JSON
        try:
            rules_path = os.path.join(os.path.dirname(__file__), "..", "merchant_rules.json")
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading local merchant rules: {e}")
            return []

    def map_row_to_transaction(self, row: list, rules: list, col_map: dict = None) -> dict:
        """
        Maps a raw table row to a structured transaction dictionary using provided rules.
        """
        if not row or not any(row):
            return None

        # Clean helper
        def clean_num(val):
            if val is None or str(val).strip() in ["", "-", "None"]:
                return None
            try:
                # Remove spaces and commas
                clean_val = str(val).replace(",", "").replace(" ", "").strip()
                if not clean_val:
                    return None
                return float(clean_val)
            except:
                return None

        # Custom logic for SBI-like statements if col_map isn't provided
        if not col_map:
            if len(row) >= 7:
                col_map = {"date": 0, "ref": 1, "chq": 2, "debit": 4, "credit": 5, "balance": 6}
            elif len(row) == 6:
                col_map = {"date": 0, "ref": 1, "chq": 2, "debit": 3, "credit": 4, "balance": 5}
            else:
                return None

        # Validate date
        date_val = str(row[col_map.get("date", 0)] or "").strip()
        if not date_val or not date_val[0].isdigit():
            return None

        description = str(row[col_map.get("ref", 1)] or "").strip()
        keys = [k.strip() for k in description.split("/") if k.strip()]

        # Categorization logic
        category = "other"
        tag = "other"
        
        all_potential_keys = []
        for key in keys:
            all_potential_keys.append(key.lower())
            words = [w.strip().lower() for w in key.split() if w.strip()]
            all_potential_keys.extend(words)

        for key_lower in all_potential_keys:
            matched = False
            for rule in rules:
                if key_lower == rule["merchant"].lower():
                    category = rule["category"].lower()
                    tag = rule["tag"].lower()
                    matched = True
                    break
            if matched:
                break

        return {
            "date": date_val,
            "transaction reference": description,
            "ref_keys": keys,
            "category": category,
            "tag": tag,
            "ref.no/chq.no": str(row[col_map.get("chq", 2)] or "").strip(),
            "debit": clean_num(row[col_map.get("debit", 3)]),
            "credit": clean_num(row[col_map.get("credit", 4)]),
            "balance": clean_num(row[col_map.get("balance", 5)])
        }

# Singleton instance
transaction_mapper = TransactionMapperService()
