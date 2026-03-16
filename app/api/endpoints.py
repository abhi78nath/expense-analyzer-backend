from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
from app.services.pdf_parser import PDFParserService
from app.models.schemas import ParseResult, ErrorResponse, MerchantRule
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
            
from app.services.gsheet_service import gsheet_service

@router.get("/transaction-tags")
async def get_transaction_tags(refresh: bool = False):
    """
    Fetch and return merchant rules from Google Sheets with fallback to local JSON
    """
    try:
        # Fetch rules from Google Sheets
        rules = gsheet_service.fetch_merchant_rules(force_refresh=refresh)

        if rules:
            logger.info(f"Returning {len(rules)} merchant rules from Google Sheets")
            return rules
        
        logger.warning("No rules found in Google Sheets, trying fallback")

    except Exception as e:
        logger.error(f"Error fetching merchant rules from Google Sheets: {str(e)}")

    # Fallback to local JSON
    try:
        rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "merchant_rules.json")
        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Returning rules from fallback JSON")
                return data
        raise HTTPException(status_code=404, detail="merchant_rules.json not found and GSheet fetch failed")
    except Exception as e:
        logger.error(f"Fallback failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch merchant rules")

@router.post("/merchant-rules")
async def add_merchant_rule(rule: MerchantRule):
    """
    Add a new merchant rule to Google Sheets
    """
    try:
        success = gsheet_service.add_merchant_rule(rule.model_dump())
        if success:
            return {"message": "Merchant rule added successfully"}
        raise HTTPException(status_code=500, detail="Failed to add merchant rule")
    except Exception as e:
        logger.error(f"Error adding merchant rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.put("/merchant-rules/{rule_id}")
async def update_merchant_rule(rule_id: int, rule: MerchantRule):
    """
    Update an existing merchant rule in Google Sheets
    """
    try:
        success = gsheet_service.update_merchant_rule(rule_id, rule.model_dump())
        if success:
            return {"message": f"Merchant rule {rule_id} updated successfully"}
        raise HTTPException(status_code=404, detail=f"Merchant rule {rule_id} not found")
    except Exception as e:
        logger.error(f"Error updating merchant rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.delete("/merchant-rules/{rule_id}")
async def delete_merchant_rule(rule_id: int):
    """
    Delete a merchant rule from Google Sheets
    """
    try:
        success = gsheet_service.delete_merchant_rule(rule_id)
        if success:
            return {"message": f"Merchant rule {rule_id} deleted successfully"}
        raise HTTPException(status_code=404, detail=f"Merchant rule {rule_id} not found")
    except Exception as e:
        logger.error(f"Error deleting merchant rule: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
