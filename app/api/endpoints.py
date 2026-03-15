from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
from app.services.pdf_parser import PDFParserService
from app.models.schemas import ParseResult, ErrorResponse
import logging
import json
import os

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/parse-pdf", response_model=ParseResult, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def parse_pdf(
    files: List[UploadFile] = File(...),
    password: Optional[str] = Form(None)
):
    all_transactions = []
    filenames = []
    total_size = 0
    
    for file in files:
        if not file.filename.endswith(".pdf"):
            continue
            # Optionally raise error if user expects ONLY PDFs and provided something else
            # raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")

        try:
            content = await file.read()
            filenames.append(file.filename)
            total_size += len(content)
            
            parser = PDFParserService()
            
            # Extract structured transaction data
            structured_transactions = parser.parse_and_structure_pdf(content, password=password)
            all_transactions.extend(structured_transactions)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to parse PDF {file.filename}: {error_msg}")
            
            if "password" in error_msg.lower() or "authenticate" in error_msg.lower():
                # If one file fails due to password, we might want to inform the user
                # For now, we'll raise for the first one that fails
                raise HTTPException(status_code=401, detail=f"Password required or incorrect for {file.filename}")
            # Other errors might be skipped or reported. Here we raise for simplicity.
            raise HTTPException(status_code=500, detail=f"Error parsing {file.filename}: {error_msg}")

    if not all_transactions and files:
        raise HTTPException(status_code=400, detail="No valid transactions found in the provided PDF(s)")

    result = ParseResult(
        filenames=filenames,
        total_transactions=len(all_transactions),
        transactions=all_transactions,
        metadata={
            "file_count": len(filenames),
            "total_size": total_size
        }
    )

    # Auto-save ALL transactions to JSON file
    try:
        save_path = os.path.join(os.getcwd(), "parsed_data.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(all_transactions, f, indent=4)
        logger.info(f"Successfully auto-saved {len(all_transactions)} transactions to {save_path}")
    except Exception as save_error:
        logger.error(f"Failed to auto-save JSON: {str(save_error)}")

    return result
            
@router.get("/transaction-tags")
async def get_transaction_tags():
    """
    Load and return the data from merchant_rules.json
    """
    try:
        rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "merchant_rules.json")
        if not os.path.exists(rules_path):
            raise HTTPException(status_code=404, detail="merchant_rules.json not found")
        
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to decode merchant_rules.json")
    except Exception as e:
        logger.error(f"Error reading merchant rules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
