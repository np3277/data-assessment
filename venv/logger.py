import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "api_activity.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a rotating file handler
# Log file will be max 5MB, keeps up to 3 backup files
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_api_activity(request_id: str, endpoint: str, method: str, status_code: int = None, message: str = ""):
    """Logs API request activity."""
    log_entry = f"Request ID: {request_id} | Endpoint: {endpoint} | Method: {method}"
    if status_code:
        log_entry += f" | Status: {status_code}"
    if message:
        log_entry += f" | Message: {message}"
    logger.info(log_entry)

# Example usage (for testing)
if __name__ == "__main__":
    log_api_activity("req_123", "/upload", "POST", 200, "File uploaded successfully")
    log_api_activity("req_456", "/data/1", "GET", 404, "Data not found")
    print(f"Logs written to {LOG_FILE}")