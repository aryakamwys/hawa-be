"""
Weather API Endpoints
Endpoints untuk weather recommendations dan knowledge management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, ValidationError

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.services.weather.recommendation_service import WeatherRecommendationService
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.notification.whatsapp_service import WhatsAppService

if TYPE_CHECKING:
    from app.db.models.user import User

router = APIRouter(prefix="/weather", tags=["weather"])


class WeatherDataRequest(BaseModel):
    """Request untuk weather data langsung"""
    pm25: float | None = None
    pm10: float | None = None
    o3: float | None = None
    no2: float | None = None
    so2: float | None = None
    co: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    location: str = "Bandung"
    timestamp: str | None = None


class GoogleSheetsRequest(BaseModel):
    """Request untuk fetch dari Google Sheets"""
    spreadsheet_id: str
    worksheet_name: str = "Sheet1"


class SendNotificationRequest(BaseModel):
    """Request untuk kirim notifikasi WhatsApp"""
    send_whatsapp: bool = False
    phone_number: str | None = None  # Optional, akan gunakan dari user profile jika tidak ada


class GoogleSheetsRequestWithNotification(BaseModel):
    """Request wrapper untuk Google Sheets dengan optional notification"""
    spreadsheet_id: str
    worksheet_name: str = "Sheet1"
    notification: Optional[SendNotificationRequest] = None
    
    class Config:
        # Allow extra fields untuk backward compatibility
        extra = "ignore"


@router.post("/recommendation", status_code=status.HTTP_200_OK)
def get_recommendation(
    weather_data: Optional[WeatherDataRequest] = None,
    notification: Optional[SendNotificationRequest] = None,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized weather recommendation
    
    Bisa menggunakan weather_data langsung atau upload spreadsheet
    Optional: Kirim notifikasi ke WhatsApp
    """
    service = WeatherRecommendationService(db)
    
    try:
        weather_dict = weather_data.dict() if weather_data else None
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            weather_data=weather_dict
        )
        
        # Send WhatsApp notification jika diminta
        if notification and notification.send_whatsapp:
            whatsapp_service = WhatsAppService()
            phone_number = notification.phone_number or current_user.phone_e164
            
            if phone_number:
                # Hanya kirim jika risk level medium atau lebih tinggi
                risk_level = recommendation.get("risk_level", "").lower()
                if risk_level in ["medium", "high", "critical"]:
                    success = whatsapp_service.send_weather_warning_instant(
                        phone_number=phone_number,
                        recommendation=recommendation,
                        language=current_user.language.value if current_user.language else "id"
                    )
                    recommendation["notification_sent"] = success
                else:
                    recommendation["notification_sent"] = False
                    recommendation["notification_skipped"] = "Risk level too low"
            else:
                recommendation["notification_sent"] = False
                recommendation["notification_error"] = "Phone number not provided"
        
        return recommendation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recommendation: {str(e)}"
        )


@router.post("/recommendation/from-google-sheets", status_code=status.HTTP_200_OK)
def get_recommendation_from_google_sheets(
    request: GoogleSheetsRequestWithNotification,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendation dari Google Sheets
    
    Args:
        request: GoogleSheetsRequestWithNotification dengan spreadsheet_id, worksheet_name, dan optional notification
    
    Request Body Format:
    {
        "spreadsheet_id": "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA",
        "worksheet_name": "Sheet1",
        "notification": null  // optional
    }
    
    Returns:
        Personalized recommendation
    """
    service = WeatherRecommendationService(db)
    
    try:
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            google_sheets_id=request.spreadsheet_id,
            google_sheets_worksheet=request.worksheet_name
        )
        
        # Send WhatsApp notification jika diminta
        notification = request.notification
        if notification and notification.send_whatsapp:
            whatsapp_service = WhatsAppService()
            phone_number = notification.phone_number or current_user.phone_e164
            
            if phone_number:
                risk_level = recommendation.get("risk_level", "").lower()
                if risk_level in ["medium", "high", "critical"]:
                    success = whatsapp_service.send_weather_warning_instant(
                        phone_number=phone_number,
                        recommendation=recommendation,
                        language=current_user.language.value if current_user.language else "id"
                    )
                    recommendation["notification_sent"] = success
                else:
                    recommendation["notification_sent"] = False
                    recommendation["notification_skipped"] = "Risk level too low"
            else:
                recommendation["notification_sent"] = False
                recommendation["notification_error"] = "Phone number not provided"
        
        return recommendation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        error_detail = str(e)
        # Log full traceback untuk debugging
        print(f"Error in get_recommendation_from_google_sheets: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching from Google Sheets: {error_detail}"
        )


@router.post("/recommendation/from-spreadsheet", status_code=status.HTTP_200_OK)
def get_recommendation_from_spreadsheet(
    file: UploadFile = File(...),
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendation dari spreadsheet upload
    
    Support format: .xlsx, .xls, .csv
    """
    import tempfile
    import os
    
    # Validate file type
    allowed_extensions = ['.xlsx', '.xls', '.csv']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        service = WeatherRecommendationService(db)
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            spreadsheet_path=tmp_path
        )
        return recommendation
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File error: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing spreadsheet: {str(e)}"
        )
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Health check endpoint untuk weather service"""
    return {
        "status": "healthy",
        "service": "weather-recommendation"
    }

