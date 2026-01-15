from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from app.services.pdf_parser import PDFParserService
from app.models.schemas import ParseResult, ErrorResponse
import logging
import json
import os

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/parse-pdf", response_model=ParseResult, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def parse_pdf(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        parser = PDFParserService()
        
        # Extract structured transaction data
        structured_transactions = parser.parse_and_structure_pdf(content, password=password)
        
        result = ParseResult(
            filename=file.filename,
            total_transactions=len(structured_transactions),
            transactions=structured_transactions,
            metadata={
                "content_type": file.content_type,
                "size": len(content)
            }
        )

        # Auto-save ONLY transactions to JSON file as a structured list
        try:
            save_path = os.path.join(os.getcwd(), "parsed_data.json")
            with open(save_path, "w", encoding="utf-8") as f:
                # User asked to structure the JSON only of the transaction data
                json.dump(structured_transactions, f, indent=4)
            logger.info(f"Successfully auto-saved structured transactions to {save_path}")
        except Exception as save_error:
            logger.error(f"Failed to auto-save JSON: {str(save_error)}")

        return result
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to parse PDF: {error_msg}")
        
        if "password" in error_msg.lower() or "authenticate" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Password required or incorrect password")
            
        raise HTTPException(status_code=500, detail=error_msg)
