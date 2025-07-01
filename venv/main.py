import pandas as pd
from io import StringIO
import uuid
from typing import List, Optional
# Import datetime.date specifically if you want to use it for isinstance checks
from datetime import datetime, date # <--- ADDED 'date' HERE

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
# from datetime import datetime # <--- ORIGINAL, NOW MOVED UP TO INCLUDE 'date'

from database import engine, Base, get_db
from models import UploadedDataItem
from validation import validate_csv_data
from logger import log_api_activity

# Initialize FastAPI app
app = FastAPI(
    title="Data Upload and Query API",
    description="A simple backend system to upload CSV data, validate it, store it, and query it.",
    version="1.0.0"
)

# Create database tables on startup
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    print("Database tables created/checked.")

@app.middleware("http")
async def log_requests(request, call_next):
    """
    Middleware to log every incoming API request.
    """
    request_id = str(uuid.uuid4()) # Generate a unique ID for each request
    endpoint = request.url.path
    method = request.method
    start_time = datetime.now()

    # Log request start
    log_api_activity(request_id, endpoint, method, message="Request started")

    response = await call_next(request)

    # Log request end with status code
    process_time = (datetime.now() - start_time).total_seconds() * 1000 # in ms
    log_api_activity(
        request_id,
        endpoint,
        method,
        status_code=response.status_code,
        message=f"Request finished. Processed in {process_time:.2f} ms"
    )
    return response

@app.post("/upload-csv/", summary="Upload a CSV file and store its data")
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload"),
    db: Session = Depends(get_db)
):
    """
    Uploads a CSV file, validates its content, and stores the valid rows in the database.
    Returns validation errors if any.
    """
    request_id = str(uuid.uuid4()) # For specific logging within the endpoint

    if not file.filename.endswith(".csv"):
        log_api_activity(request_id, "/upload-csv/", "POST", 400, "Invalid file format. Only CSV files are allowed.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only CSV files are allowed."
        )

    try:
        # Read CSV content
        contents = await file.read()
        s_io = StringIO(contents.decode('utf-8'))
        df = pd.read_csv(s_io)

        # Validate data using Pandera
        is_valid, validation_message, validated_df = validate_csv_data(df)

        if not is_valid:
            log_api_activity(request_id, "/upload-csv/", "POST", 400, f"Validation failed: {validation_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV data validation failed: {validation_message}"
            )

        # Store valid data in the database
        items_to_create = []
        for index, row in validated_df.iterrows():
            # Convert row to dictionary, handle potential non-serializable types if any, though Pandera handles most
            row_data_dict = row.to_dict()

            # --- NEW CODE START ---
            # Convert any datetime.date objects to ISO 8601 strings for JSON serialization
            for key, value in row_data_dict.items():
                if isinstance(value, date): # Check against datetime.date
                    row_data_dict[key] = value.isoformat()
            # --- NEW CODE END ---

            # Store the original filename and row number
            item = UploadedDataItem(
                original_filename=file.filename,
                row_number=index + 1, # CSV rows are 1-indexed for users
                data=row_data_dict
            )
            items_to_create.append(item)

        db.add_all(items_to_create)
        db.commit()

        log_api_activity(request_id, "/upload-csv/", "POST", 200, f"Successfully uploaded and stored {len(items_to_create)} rows from {file.filename}.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": f"Successfully uploaded and stored {len(items_to_create)} rows.", "filename": file.filename}
        )

    except pd.errors.EmptyDataError:
        log_api_activity(request_id, "/upload-csv/", "POST", 400, "The uploaded CSV file is empty.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded CSV file is empty.")
    except Exception as e:
        log_api_activity(request_id, "/upload-csv/", "POST", 500, f"Internal server error during upload: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process CSV: {str(e)}")


@app.get("/data/", summary="Retrieve all uploaded data or filter by criteria")
async def get_all_data(
    skip: int = 0,
    limit: int = 100,
    # Allow filtering by any column present in the data
    # Example: /data/?filter_column=name&filter_value=Alice
    filter_column: Optional[str] = Query(None, description="Column name to filter by"),
    filter_value: Optional[str] = Query(None, description="Value to filter by"),
    db: Session = Depends(get_db)
):
    """
    Retrieves all uploaded data items. Supports pagination and basic filtering.
    """
    query = db.query(UploadedDataItem)

    if filter_column and filter_value:
        # Construct a raw SQL WHERE clause for JSON data
        # This assumes the 'data' column is stored as JSON text or similar.
        # For SQLite JSON, it's efficient to query directly.
        # Example: WHERE json_extract(data, '$.<filter_column>') = '<filter_value>'
        # Note: json_extract returns text, so comparison might need casting for numbers etc.
        # For simplicity, we'll compare as text here.
        # For case-insensitive search, you might need to use lower() or COLLATE NOCASE
        # However, for SQLite JSON functions are case-sensitive by default for keys.
        json_path = f"$.{filter_column}"
        # Using text() for raw SQL expression
        query = query.filter(text(f"json_extract(data, '{json_path}') = :value")).params(value=filter_value)
        log_api_activity(str(uuid.uuid4()), "/data/", "GET", message=f"Filtering data by {filter_column}={filter_value}")

    data_items = query.offset(skip).limit(limit).all()

    if not data_items:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "No data found matching criteria."}
        )

    # Convert ORM objects to dictionaries for API response
    response_data = [
        {"id": item.id, "original_filename": item.original_filename, "row_number": item.row_number, "data": item.data, "uploaded_at": item.uploaded_at.isoformat()}
        for item in data_items
    ]
    log_api_activity(str(uuid.uuid4()), "/data/", "GET", 200, f"Retrieved {len(response_data)} data items.")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Data retrieved successfully.", "data": response_data, "count": len(response_data)}
    )

@app.get("/data/{item_id}", summary="Retrieve a single uploaded data item by ID")
async def get_data_by_id(item_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single uploaded data item by its unique ID.
    """
    item = db.query(UploadedDataItem).filter(UploadedDataItem.id == item_id).first()
    request_id = str(uuid.uuid4()) # For specific logging within the endpoint

    if not item:
        log_api_activity(request_id, f"/data/{item_id}", "GET", 404, f"Data item with ID {item_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data item with ID {item_id} not found."
        )

    response_data = {
        "id": item.id,
        "original_filename": item.original_filename,
        "row_number": item.row_number,
        "data": item.data,
        "uploaded_at": item.uploaded_at.isoformat()
    }
    log_api_activity(request_id, f"/data/{item_id}", "GET", 200, f"Retrieved data item with ID {item_id}.")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Data item retrieved successfully.", "data": response_data}
    )

@app.delete("/data/{item_id}", summary="Delete a single uploaded data item by ID")
async def delete_data_by_id(item_id: int, db: Session = Depends(get_db)):
    """
    Deletes a single uploaded data item by its unique ID.
    """
    item = db.query(UploadedDataItem).filter(UploadedDataItem.id == item_id).first()
    request_id = str(uuid.uuid4()) # For specific logging within the endpoint

    if not item:
        log_api_activity(request_id, f"/data/{item_id}", "DELETE", 404, f"Data item with ID {item_id} not found for deletion.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data item with ID {item_id} not found."
        )

    db.delete(item)
    db.commit()

    log_api_activity(request_id, f"/data/{item_id}", "DELETE", 200, f"Successfully deleted data item with ID {item_id}.")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": f"Data item with ID {item_id} deleted successfully."}
    )