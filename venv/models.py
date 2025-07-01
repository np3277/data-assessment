from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.types import TypeDecorator
import json
from database import Base
from datetime import datetime

# Custom TypeDecorator for JSON data in SQLite
class JSONEncodedDict(TypeDecorator):
    type = SQLiteJSON # Use SQLite JSON type
    impl = Text # Use Text for other backends if needed (not directly used here for SQLite)

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

class UploadedDataItem(Base):
    __tablename__ = "uploaded_data"

    id = Column(Integer, primary_key=True, index=True)
    # Store original filename for reference
    original_filename = Column(String, index=True)
    # Store row number from original CSV for reference
    row_number = Column(Integer)
    # Use JSONEncodedDict to store the row data as a dictionary
    data = Column(MutableDict.as_mutable(JSONEncodedDict), nullable=False)
    # Timestamp of when the data was uploaded
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UploadedDataItem(id={self.id}, filename='{self.original_filename}', row_number={self.row_number})>"