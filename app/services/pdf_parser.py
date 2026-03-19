import pdfplumber
import io
import logging
import json
import os
import re

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from app.services.transaction_mapper import transaction_mapper

# First 4 chars of IFSC → bank name
IFSC_BANK_MAP = {
    "HDFC": "HDFC Bank",
    "SBIN": "State Bank of India",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank",
    "IOBA": "Indian Overseas Bank",
    "YESB": "Yes Bank",
    "IDBI": "IDBI Bank",
    "INDB": "IndusInd Bank",
    "FDRL": "Federal Bank",
    "KVBL": "Karur Vysya Bank",
    "CITI": "Citibank",
    "HSBC": "HSBC Bank",
    "SCBL": "Standard Chartered",
    "RATN": "RBL Bank",
    "IDFB": "IDFC First Bank",
    "BDBL": "Bandhan Bank",
}

IFSC_PATTERN = re.compile(r'\b([A-Z]{4}0[A-Z0-9]{6})\b')
class PDFParserService:
    def __init__(self):
        pass

    def parse_and_structure_pdf(self, file_content: bytes, pdf_id: str, password: str = None) -> list:
        """
        Parses PDF and returns structured transaction data.
        """
        structured_data = []
        ifsc_code  = None
        bank_name  = "Unknown Bank"
        # Fetch rules once per parse call to ensure they are fresh (honors gsheet cache TTL)
        rules = transaction_mapper.load_merchant_rules()
        logger.info(f"Using {len(rules)} merchant rules for transaction mapping")
        
        try:
            with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                for page in pdf.pages:
                    # ── Extract IFSC from raw text ──────────────────
                    if ifsc_code is None:
                        text = page.extract_text() or ""
                        ifsc_code = PDFParserService._extract_ifsc(text)
                        if ifsc_code:
                            bank_name = PDFParserService._bank_name_from_ifsc(ifsc_code)
                            logger.info(f"Found IFSC: {ifsc_code} and Bank Name: {bank_name}")
                        else:
                            logger.info("No IFSC code found")


                    tables = page.extract_tables()
                    for table in tables:
                        if not table: continue
                        
                        col_map = PDFParserService.get_column_mapping(table)
                        
                        for row in table:
                            mapped = transaction_mapper.map_row_to_transaction(row, rules, col_map)
                            if mapped:
                                mapped["pdf_id"] = pdf_id
                                structured_data.append(mapped)
            return {
                "transactions": structured_data,
                "ifsc_code":    ifsc_code,
                "bank_name":    bank_name,
            }
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            raise e

    @staticmethod
    def get_column_mapping(table: list) -> dict:
        """
        Tries to find a header row and return column indices.
        """
        for row in table:
            row_str = " ".join([str(cell).lower() for cell in row if cell])
            if "date" in row_str and ("balance" in row_str or "credit" in row_str or "debit" in row_str):
                col_map = {}
                for i, cell in enumerate(row):
                    if not cell: continue
                    txt = str(cell).lower()
                    if "date" in txt and "value" not in txt: col_map["date"] = i
                    elif "narration" in txt or "ref" in txt or "description" in txt:
                        if "ref" in txt and "chq" in txt: col_map["chq"] = i
                        else: col_map["ref"] = i
                    elif "chq" in txt or "ref" in txt: col_map["chq"] = i
                    elif "withdrawal" in txt or "debit" in txt: col_map["debit"] = i
                    elif "deposit" in txt or "credit" in txt: col_map["credit"] = i
                    elif "balance" in txt: col_map["balance"] = i
                return col_map
        return None

    def parse_pdf(self, file_content: bytes, password: str = None) -> list:
        # Re-using the logic inside parse_and_structure_pdf or keep for raw access
        all_data = []
        with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if any(row): all_data.append(row)
        return all_data

    def extract_text(self, file_content: bytes, password: str = None) -> str:
        """
        Extracts raw text from PDF.
        """
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            return full_text
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            raise e

    @staticmethod
    def _extract_ifsc(text: str) -> str | None:
        """
        Scans raw page text for a valid IFSC code.
        Returns the first match or None.
        """
        match = IFSC_PATTERN.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _bank_name_from_ifsc(ifsc_code: str) -> str:
        """
        Derives bank name from first 4 chars of IFSC.
        Falls back to the 4-char code itself if not in map.
        """
        prefix = ifsc_code[:4].upper()
        return IFSC_BANK_MAP.get(prefix, f"Bank ({prefix})")