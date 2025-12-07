"""
Custom exceptions untuk aplikasi
"""
from fastapi import HTTPException, status


class GoogleSheetsRateLimitError(HTTPException):
    """Exception untuk Google Sheets API rate limit"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Google Sheets API rate limit exceeded. "
                   "Please wait a moment and try again. "
                   "Data is cached for 30 seconds."
        )


class GoogleSheetsError(HTTPException):
    """Exception untuk Google Sheets API errors"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching spreadsheet data: {detail}"
        )


def handle_google_sheets_error(error: Exception) -> HTTPException:
    """
    Handle Google Sheets API errors dengan proper exception types
    
    Args:
        error: Exception dari Google Sheets API
    
    Returns:
        HTTPException yang sesuai
    """
    error_msg = str(error)
    
    if "429" in error_msg or "Quota exceeded" in error_msg:
        return GoogleSheetsRateLimitError()
    
    return GoogleSheetsError(error_msg)
