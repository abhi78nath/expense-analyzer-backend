# Expense Analyser PDF Parser API

A modular Python API built with FastAPI and pdfplumber for parsing PDF expense statements.

## Project Structure

```
expense-analyzer-python/
├── app/
│   ├── api/
│   │   └── endpoints.py    # API route definitions
│   ├── models/
│   │   └── schemas.py      # Pydantic models
│   ├── services/
│   │   └── pdf_parser.py   # Core PDF parsing logic
│   └── main.py             # FastAPI entry point
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the API

Start the server using `uvicorn`:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
- **Swagger Documentation:** `http://localhost:8000/docs`
- **Root Endpoint:** `http://localhost:8000/`

## API Endpoints

### `POST /api/v1/parse-pdf`

Upload a PDF file to extract table data.

**Request:**
- `file`: PDF file (multipart/form-data)

**Response:**
```json
{
  "filename": "statement.pdf",
  "total_transactions": 10,
  "transactions": [
    ["Date", "Description", "Amount", "Balance"],
    ["01-01-2023", "Salary", "5000", "5000"],
    ...
  ],
  "metadata": {
    "content_type": "application/pdf",
    "size": 12345
  }
}
```
