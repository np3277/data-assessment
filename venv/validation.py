import pandas as pd
import pandera.pandas as pa # Change this line
from pandera.typing import DataFrame, Series # Keep this one as is

class CSVDataSchema(pa.DataFrameModel):
    id: Series[int] = pa.Field(unique=True, ge=1)
    name: Series[str] = pa.Field(nullable=False)
    age: Series[int] = pa.Field(nullable=False, ge=0, le=120)
    email: Series[str] = pa.Field(nullable=False, regex=r"^[^@]+@[^@]+\.[^@]+$")
    is_active: Series[bool] = pa.Field(nullable=False)
    signup_date: Series[pa.Date] = pa.Field(nullable=False)

    class Config:
        strict = True # Ensure no extra columns are present
        coerce = True # Coerce data types automatically

def validate_csv_data(df: pd.DataFrame) -> tuple[bool, str, pd.DataFrame | None]:
    """
    Validates a DataFrame against the CSVDataSchema.

    Returns:
        A tuple (is_valid, error_message, validated_df).
        If valid, validated_df contains the coerced DataFrame.
    """
    try:
        validated_df = CSVDataSchema.validate(df)
        return True, "Data validated successfully.", validated_df
    except pa.errors.SchemaErrors as e:
        error_details = []
        for check in e.schema_errors:
            error_details.append(f"Column '{check.column}' failed check '{check.check}' on row(s) {check.failure_cases['index'].tolist()}. Values: {check.failure_cases['failure_case'].tolist()}")
        return False, "Validation failed: " + "; ".join(error_details), None
    except Exception as e:
        return False, f"An unexpected error occurred during validation: {str(e)}", None

# Example of how to use it (can be used for testing)
if __name__ == "__main__":
    # Valid data
    data_valid = {
        'id': [1, 2],
        'name': ['Alice', 'Bob'],
        'age': [30, 25],
        'email': ['a@example.com', 'b@example.com'],
        'is_active': [True, False],
        'signup_date': ['2023-01-01', '2022-05-15']
    }
    df_valid = pd.DataFrame(data_valid)
    is_valid, message, _ = validate_csv_data(df_valid)
    print(f"Valid data check: {is_valid} - {message}")

    # Invalid data (missing age for id=3)
    data_invalid = {
        'id': [1, 2, 3],
        'name': ['Alice', 'Bob', 'Charlie'],
        'age': [30, 25, None], # Missing value
        'email': ['a@example.com', 'b@example.com', 'c@example.com'],
        'is_active': [True, False, True],
        'signup_date': ['2023-01-01', '2022-05-15', '2024-01-20']
    }
    df_invalid = pd.DataFrame(data_invalid)
    is_valid, message, _ = validate_csv_data(df_invalid)
    print(f"Invalid data check: {is_valid} - {message}")

    # Invalid data (wrong email format)
    data_invalid_email = {
        'id': [1],
        'name': ['Alice'],
        'age': [30],
        'email': ['invalid-email'],
        'is_active': [True],
        'signup_date': ['2023-01-01']
    }
    df_invalid_email = pd.DataFrame(data_invalid_email)
    is_valid, message, _ = validate_csv_data(df_invalid_email)
    print(f"Invalid email check: {is_valid} - {message}")