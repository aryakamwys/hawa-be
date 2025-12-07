"""
Weather API Endpoints
Endpoints untuk weather recommendations dan knowledge management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.services.weather.recommendation_service import WeatherRecommendationService
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.weather.groq_heatmap_tips_service import GroqHeatmapTipsService
from app.services.notification.whatsapp_service import WhatsAppService
from fastapi import Query
import time

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


@router.get("/heatmap", status_code=status.HTTP_200_OK)
def get_heatmap_data(
    current_user: "User" = Depends(get_current_user),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    force_refresh: bool = Query(default=False, description="Force refresh dari Google Sheets (bypass cache)")
):
    """
    Get heatmap data dari Google Sheets untuk visualisasi peta.
    Endpoint ini bisa diakses oleh semua user yang sudah login.
    
    Data diambil dari spreadsheet heatmap dengan format:
    - Location, Latitude, Longitude, PM2.5, PM10, Air Quality, Risk Score, Color, Device ID
    
    Returns:
        Array of heatmap points dengan format siap untuk frontend map visualization
    """
    # Simple in-memory cache untuk Google Sheets data (shared dengan admin jika perlu)
    # Format: {cache_key: (data, timestamp)}
    _sheets_cache: dict = {}
    CACHE_TTL_SECONDS = 30  # Cache selama 30 detik
    
    def _get_cached_sheets_data(spreadsheet_id: str, worksheet_name: str, force_refresh: bool = False):
        """Get Google Sheets data dengan caching untuk mengurangi API calls"""
        cache_key = f"{spreadsheet_id}:{worksheet_name}"
        current_time = time.time()
        
        # Check cache
        if not force_refresh and cache_key in _sheets_cache:
            cached_data, cache_timestamp = _sheets_cache[cache_key]
            if current_time - cache_timestamp < CACHE_TTL_SECONDS:
                return cached_data
        
        # Fetch fresh data
        try:
            service = SpreadsheetService()
            raw_data = service.read_from_google_sheets(
                spreadsheet_id=spreadsheet_id,
                worksheet_name=worksheet_name
            )
            # Update cache
            _sheets_cache[cache_key] = (raw_data, current_time)
            return raw_data
        except Exception as e:
            # Jika error dan ada cache, return cache sebagai fallback
            if cache_key in _sheets_cache:
                error_msg = str(e)
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    cached_data, cache_timestamp = _sheets_cache[cache_key]
                    return cached_data
            raise
    
    try:
        # Spreadsheet ID untuk heatmap data dummy
        heatmap_spreadsheet_id = "1p69Ae67JGlScrMlSDnebuZMghXYMY7IykiT1gQwello"
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(heatmap_spreadsheet_id, worksheet_name, force_refresh=force_refresh)
        
        if not raw_data:
            return {
                "success": True,
                "spreadsheet_id": heatmap_spreadsheet_id,
                "worksheet_name": worksheet_name,
                "points": [],
                "total_points": 0,
                "message": "No data found in spreadsheet"
            }
        
        # Process data untuk format heatmap
        heatmap_points = []
        for idx, record in enumerate(raw_data, start=1):
            try:
                # Extract data dengan case-insensitive key matching
                def get_field_value(field_variants: list[str], default: Any = None) -> Any:
                    """Helper untuk extract field dengan berbagai variasi nama kolom"""
                    for variant in field_variants:
                        for key in record.keys():
                            if str(key).lower() == variant.lower():
                                value = record[key]
                                # Convert string numbers to float
                                if isinstance(value, str):
                                    try:
                                        return float(value) if value.strip() else default
                                    except ValueError:
                                        return value if value else default
                                return value if value is not None else default
                    return default
                
                # Extract latitude dan longitude
                latitude = get_field_value(['Latitude', 'latitude', 'lat'])
                longitude = get_field_value(['Longitude', 'longitude', 'lng', 'lon'])
                
                # Skip jika tidak ada koordinat
                if latitude is None or longitude is None:
                    continue
                
                # Convert ke float jika string
                try:
                    lat = float(latitude) if not isinstance(latitude, float) else latitude
                    lng = float(longitude) if not isinstance(longitude, float) else longitude
                except (ValueError, TypeError):
                    continue
                
                # Extract PM values
                pm25 = get_field_value(['PM2.5', 'pm2.5', 'PM25', 'pm25', 'PM 2.5'])
                pm10 = get_field_value(['PM10', 'pm10', 'PM 10'])
                
                # Extract other fields
                location = get_field_value(
                    ['Location', 'location', 'Lokasi', 'lokasi'], 
                    f"Location {idx}"
                )
                air_quality = get_field_value(
                    ['Air Quality', 'air_quality', 'Air Quality Level', 'air_quality_level'],
                    "UNKNOWN"
                )
                risk_score = get_field_value(['Risk Score', 'risk_score', 'Risk', 'risk'], 0.0)
                color = get_field_value(['Color', 'color', 'Colour', 'colour'], "GRAY")
                device_id = get_field_value(['Device ID', 'device_id', 'Device', 'device'], None)
                
                # Determine risk level dari air quality atau risk score
                risk_level = "low"
                if isinstance(air_quality, str):
                    air_quality_upper = air_quality.upper()
                    if "POOR" in air_quality_upper or "UNHEALTHY" in air_quality_upper:
                        risk_level = "high"
                    elif "MODERATE" in air_quality_upper:
                        risk_level = "moderate"
                    elif "GOOD" in air_quality_upper:
                        risk_level = "low"
                
                # Jika risk score ada, gunakan untuk menentukan risk level
                if isinstance(risk_score, (int, float)):
                    if risk_score >= 0.7:
                        risk_level = "high"
                    elif risk_score >= 0.4:
                        risk_level = "moderate"
                    else:
                        risk_level = "low"
                
                # Build point object
                point = {
                    "id": idx,
                    "location": str(location) if location else f"Location {idx}",
                    "lat": lat,
                    "lng": lng,
                    "pm2_5": float(pm25) if pm25 is not None else None,
                    "pm10": float(pm10) if pm10 is not None else None,
                    "air_quality": str(air_quality) if air_quality else "UNKNOWN",
                    "risk_score": float(risk_score) if risk_score is not None else None,
                    "risk_level": risk_level,
                    "color": str(color).upper() if color else "GRAY",
                    "device_id": str(device_id) if device_id else None
                }
                
                heatmap_points.append(point)
                
            except Exception as e:
                # Skip record yang error, continue ke berikutnya
                continue
        
        return {
            "success": True,
            "spreadsheet_id": heatmap_spreadsheet_id,
            "worksheet_name": worksheet_name,
            "points": heatmap_points,
            "total_points": len(heatmap_points),
            "center": {
                "lat": sum(p["lat"] for p in heatmap_points) / len(heatmap_points) if heatmap_points else -6.2,
                "lng": sum(p["lng"] for p in heatmap_points) / len(heatmap_points) if heatmap_points else 107.6
            } if heatmap_points else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        error_msg = str(e)
        # Handle Google Sheets API rate limit
        if "429" in error_msg or "Quota exceeded" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Google Sheets API rate limit exceeded. Please wait a moment and try again. Data is cached for 30 seconds."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching heatmap data: {error_msg}"
        )


@router.get("/heatmap/info", status_code=status.HTTP_200_OK)
def get_heatmap_info(
    current_user: "User" = Depends(get_current_user),
    language: Optional[str] = Query(default=None, description="Bahasa (id, en, su). Optional, default dari user profile")
):
    """
    Get informasi/legend untuk heatmap.
    Menjelaskan arti warna dan kategori di peta.
    
    Bahasa akan otomatis disesuaikan dengan profile user (current_user.language).
    Query parameter language hanya sebagai override jika diperlukan.
    
    Returns:
        Informasi tentang kategori risk level dan arti warna di heatmap
        dalam bahasa sesuai dengan user profile
    """
    user_lang = current_user.language.value if current_user.language else "id"
    
    if language:
        user_lang = language
    
    info_data = {
        "id": {
            "title": "Informasi Peta Sebaran",
            "description": "Peta ini menampilkan sebaran kualitas udara di berbagai lokasi. Setiap warna menunjukkan tingkat risiko polusi udara.",
            "categories": [
                {
                    "color": "red",
                    "label": "Tinggi",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Kualitas udara tidak sehat. Hindari aktivitas di luar ruangan."
                },
                {
                    "color": "orange",
                    "label": "Sedang",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Kualitas udara sedang. Kelompok sensitif perlu berhati-hati."
                },
                {
                    "color": "green",
                    "label": "Rendah",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Kualitas udara baik. Aman untuk aktivitas di luar ruangan."
                }
            ],
            "pm25_explanation": "PM2.5: Partikel halus di udara yang dapat masuk ke paru-paru dan menyebabkan masalah kesehatan.",
            "pm10_explanation": "PM10: Partikel debu yang lebih besar yang dapat mengiritasi saluran pernapasan."
        },
        "en": {
            "title": "Distribution Map Information",
            "description": "This map shows the distribution of air quality at various locations. Each color indicates the level of air pollution risk.",
            "categories": [
                {
                    "color": "red",
                    "label": "High",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Unhealthy air quality. Avoid outdoor activities."
                },
                {
                    "color": "orange",
                    "label": "Moderate",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Moderate air quality. Sensitive groups should be cautious."
                },
                {
                    "color": "green",
                    "label": "Low",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Good air quality. Safe for outdoor activities."
                }
            ],
            "pm25_explanation": "PM2.5: Fine particles in the air that can enter the lungs and cause health problems.",
            "pm10_explanation": "PM10: Larger dust particles that can irritate the respiratory tract."
        },
        "su": {
            "title": "Informasi Peta Sebaran",
            "description": "Peta ieu nampilkeun sebaran kualitas udara di sababaraha lokasi. Unggal warna nunjukkeun tingkat risiko polusi udara.",
            "categories": [
                {
                    "color": "red",
                    "label": "Tinggi",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Kualitas udara henteu séhat. Hindari aktivitas di luar ruangan."
                },
                {
                    "color": "orange",
                    "label": "Sedang",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Kualitas udara sedeng. Kelompok sensitif kedah ati-ati."
                },
                {
                    "color": "green",
                    "label": "Rendah",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Kualitas udara saé. Aman pikeun aktivitas di luar ruangan."
                }
            ],
            "pm25_explanation": "PM2.5: Partikel halus di udara anu tiasa asup kana paru-paru sareng nyababkeun masalah kaséhatan.",
            "pm10_explanation": "PM10: Partikel debu anu langkung ageung anu tiasa ngairitasi saluran pernapasan."
        }
    }
    
    return info_data.get(user_lang, info_data["id"])


@router.get("/heatmap/tips", status_code=status.HTTP_200_OK)
def get_heatmap_tips(
    request: Request,
    current_user: "User" = Depends(get_current_user),
    pm25: Optional[float] = Query(default=None, description="PM2.5 value untuk generate tips"),
    pm10: Optional[float] = Query(default=None, description="PM10 value untuk generate tips"),
    air_quality: Optional[str] = Query(default=None, description="Air quality status"),
    risk_level: Optional[str] = Query(default=None, description="Risk level (high, moderate, low)"),
    location: Optional[str] = Query(default=None, description="Location name"),
    language: Optional[str] = Query(default=None, description="Bahasa (id, en, su). Optional override, default otomatis dari user profile")
):
    """
    Get AI-generated tips dan rekomendasi berdasarkan tingkat polusi.
    Menggunakan Groq LLM untuk generate explainable AI tips.
    
    Query Parameters:
        - pm25, pm10: Nilai polusi (optional, bisa dari heatmap point)
        - air_quality: Status kualitas udara (optional)
        - risk_level: Level risiko (optional)
        - location: Nama lokasi (optional)
        - language: Bahasa (optional, default dari user profile)
    
    Returns:
        Tips dan penjelasan AI-generated berdasarkan data polusi
    """
    try:
        user_lang = current_user.language.value if current_user.language else "id"
        
        if language:
            user_lang = language
        
        tips_service = GroqHeatmapTipsService()
        
        tips = tips_service.generate_tips(
            pm25=pm25,
            pm10=pm10,
            air_quality=air_quality,
            risk_level=risk_level,
            location=location,
            language=user_lang
        )
        
        return {
            "success": True,
            "language": user_lang,
            "data": tips,
            "source": "groq_llm"
        }
        
    except Exception as e:
        error_msg = str(e)
        try:
            tips_service = GroqHeatmapTipsService()
            user_lang = current_user.language.value if current_user.language else "id"
            if language:
                user_lang = language
            fallback_tips = tips_service._get_fallback_tips(pm25, pm10, risk_level, user_lang)
            
            return {
                "success": True,
                "language": user_lang,
                "data": fallback_tips,
                "source": "fallback",
                "error": error_msg
            }
        except Exception as fallback_error:
            return {
                "success": False,
                "language": language or "id",
                "data": {
                    "title": "Tips Kesehatan & Pencegahan",
                    "explanation": "Tidak dapat memuat tips saat ini. Silakan coba lagi nanti.",
                    "tips": [],
                    "health_impact": "",
                    "prevention": ""
                },
                "source": "error",
                "error": str(fallback_error)
            }


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Health check endpoint untuk weather service"""
    return {
        "status": "healthy",
        "service": "weather-recommendation"
    }

