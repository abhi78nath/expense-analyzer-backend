import pdfplumber
import io
import logging

logger = logging.getLogger(__name__)

class PDFParserService:
    @staticmethod
    def map_row_to_transaction(row: list, col_map: dict = None) -> dict:
        """
        Maps a raw table row to a structured transaction dictionary.
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
        # Often: 0:Date, 1:Narration, 2:Ref, 3:ValueDate (opt), 4:Debit, 5:Credit, 6:Balance
        # OR:    0:Date, 1:Narration, 2:Ref, 3:Debit, 4:Credit, 5:Balance
        
        if not col_map:
            # Check length to guess
            if len(row) >= 7:
                # Assumption with Value Date
                col_map = {"date": 0, "ref": 1, "chq": 2, "debit": 4, "credit": 5, "balance": 6}
            elif len(row) == 6:
                # Assumption without Value Date
                col_map = {"date": 0, "ref": 1, "chq": 2, "debit": 3, "credit": 4, "balance": 5}
            else:
                return None

        # Validate date
        date_val = str(row[col_map.get("date", 0)] or "").strip()
        if not date_val or not date_val[0].isdigit():
            return None

        return {
            "date": date_val,
            "transaction reference": str(row[col_map.get("ref", 1)] or "").strip(),
            "ref.no/chq.no": str(row[col_map.get("chq", 2)] or "").strip(),
            "debit": clean_num(row[col_map.get("debit", 3)]),
            "credit": clean_num(row[col_map.get("credit", 4)]),
            "balance": clean_num(row[col_map.get("balance", 5)])
        }

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

    @staticmethod
    def parse_and_structure_pdf(file_content: bytes, password: str = None) -> list:
        """
        Parses PDF and returns structured transaction data.
        """
        structured_data = []
        try:
            with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table: continue
                        
                        col_map = PDFParserService.get_column_mapping(table)
                        # logger.info(f"Found column mapping: {col_map}")
                        
                        for row in table:
                            mapped = PDFParserService.map_row_to_transaction(row, col_map)
                            if mapped:
                                structured_data.append(mapped)
            return structured_data
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            raise e

    @staticmethod
    def parse_pdf(file_content: bytes, password: str = None) -> list:
        # Re-using the logic inside parse_and_structure_pdf or keep for raw access
        all_data = []
        with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if any(row): all_data.append(row)
        return all_data

    @staticmethod
    def extract_text(file_content: bytes, password: str = None) -> str:
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
