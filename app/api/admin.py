"""Admin routes - hanya bisa diakses oleh admin."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os
from datetime import datetime, timedelta
from functools import lru_cache
import time

from app.core.dependencies import get_current_admin
from app.core.config import get_settings
from app.db.postgres import get_db
from app.db.models.user import User, RoleEnum
from app.services.auth.schemas import UserResponse
from app.services.weather.spreadsheet_service import SpreadsheetService

router = APIRouter(prefix="/admin", tags=["admin"])

# Simple in-memory cache untuk Google Sheets data
# Format: {cache_key: (data, timestamp)}
_sheets_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 30  # Cache selama 30 detik untuk mengurangi API calls


@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Dashboard admin - endpoint utama untuk admin."""
    return {
        "message": "Welcome to Admin Dashboard",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "full_name": current_admin.full_name,
        },
        "stats": {
            "total_users": db.query(User).count(),
            "total_admins": db.query(User).filter(User.role == RoleEnum.ADMIN).count(),
        },
    }


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List semua users - hanya admin yang bisa akses."""
    users = db.query(User).all()
    return users


@router.get("/me", response_model=UserResponse)
def get_admin_info(current_admin: User = Depends(get_current_admin)):
    """Get current admin information."""
    return current_admin


def _get_cached_sheets_data(spreadsheet_id: str, worksheet_name: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Get Google Sheets data dengan caching untuk mengurangi API calls
    """
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
                # Return cached data dengan warning
                return cached_data
        raise


@router.get("/spreadsheet/data")
def get_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    limit: Optional[int] = Query(default=None, description="Limit jumlah data (untuk pagination)"),
    offset: int = Query(default=0, description="Offset untuk pagination"),
    include_processed: bool = Query(default=False, description="Include processed data format"),
    force_refresh: bool = Query(default=False, description="Force refresh dari Google Sheets (bypass cache)")
) -> Dict[str, Any]:
    """
    Get data dari Google Sheets yang sudah dikonfigurasi.
    Admin tidak perlu input spreadsheet ID lagi, langsung tampilkan data.
    
    Data di-cache selama 30 detik untuk mengurangi API calls dan menghindari rate limit.
    
    Returns:
        Data spreadsheet dalam format yang siap ditampilkan di datatable
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name, force_refresh=force_refresh)
        service = SpreadsheetService()
        
        # Apply pagination jika ada limit
        total_records = len(raw_data)
        if limit:
            paginated_data = raw_data[offset:offset + limit]
        else:
            paginated_data = raw_data[offset:]
        
        # Process data jika diminta
        processed_data = None
        if include_processed and paginated_data:
            try:
                # Process latest data
                processed_data = service.process_bmkg_data(paginated_data[-1])
            except Exception as e:
                # Jika processing gagal, tetap return raw data
                processed_data = {"error": str(e)}
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "total_records": total_records,
            "limit": limit,
            "offset": offset,
            "data": paginated_data,
            "processed_data": processed_data,
            "columns": list(paginated_data[0].keys()) if paginated_data else []
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
            detail=f"Error fetching spreadsheet data: {error_msg}"
        )


@router.get("/spreadsheet/latest")
def get_latest_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    include_processed: bool = Query(default=True, description="Include processed data format")
) -> Dict[str, Any]:
    """
    Get data terbaru dari Google Sheets (baris terakhir).
    Berguna untuk menampilkan data real-time di dashboard.
    
    Returns:
        Data terbaru dalam format yang siap ditampilkan
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Yk6F3ZFLSBDna4CL7PCWKeFJNC7qLqZRhb5NNB1dCio")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name)
        
        if not raw_data:
            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "worksheet_name": worksheet_name,
                "data": None,
                "processed_data": None,
                "message": "No data found in spreadsheet"
            }
        
        # Get latest record (baris terakhir)
        latest_raw = raw_data[-1]
        service = SpreadsheetService()
        
        # Process data jika diminta
        processed_data = None
        if include_processed:
            try:
                processed_data = service.process_bmkg_data(latest_raw)
            except Exception as e:
                processed_data = {"error": str(e), "raw": latest_raw}
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "data": latest_raw,
            "processed_data": processed_data,
            "timestamp": latest_raw.get("Timestamp") or latest_raw.get("timestamp") or latest_raw.get("Date") or latest_raw.get("date")
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
            detail=f"Error fetching latest spreadsheet data: {error_msg}"
        )


@router.get("/spreadsheet/stats")
def get_spreadsheet_stats(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet")
) -> Dict[str, Any]:
    """
    Get statistics dari spreadsheet data.
    Berguna untuk menampilkan summary di dashboard.
    
    Returns:
        Statistics summary dari data spreadsheet
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name)
        
        if not raw_data:
            return {
                "success": True,
                "total_records": 0,
                "columns": [],
                "stats": {}
            }
        
        # Process semua data untuk stats
        service = SpreadsheetService()
        processed_records = []
        for record in raw_data:
            try:
                processed = service.process_bmkg_data(record)
                if processed:
                    processed_records.append(processed)
            except:
                continue
        
        # Calculate statistics
        stats = {}
        if processed_records:
            numeric_fields = ['pm25', 'pm10', 'temperature', 'humidity', 'o3', 'no2', 'so2', 'co']
            for field in numeric_fields:
                values = [r.get(field) for r in processed_records if r.get(field) is not None]
                if values:
                    stats[field] = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "latest": values[-1] if values else None
                    }
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "total_records": len(raw_data),
            "processed_records": len(processed_records),
            "columns": list(raw_data[0].keys()) if raw_data else [],
            "stats": stats
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
            detail=f"Error fetching spreadsheet stats: {error_msg}"
        )


@router.get("/heatmap")
def get_heatmap_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    force_refresh: bool = Query(default=False, description="Force refresh dari Google Sheets (bypass cache)")
) -> Dict[str, Any]:
    """
    Get heatmap data dari Google Sheets untuk visualisasi peta.
    Data diambil dari spreadsheet heatmap dengan format:
    - Location, Latitude, Longitude, PM2.5, PM10, Air Quality, Risk Score, Color, Device ID
    
    Returns:
        Array of heatmap points dengan format siap untuk frontend map visualization
    """
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
                def get_field_value(field_variants: List[str], default: Any = None) -> Any:
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


from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os
from datetime import datetime, timedelta
from functools import lru_cache
import time

from app.core.dependencies import get_current_admin
from app.core.config import get_settings
from app.db.postgres import get_db
from app.db.models.user import User, RoleEnum
from app.services.auth.schemas import UserResponse
from app.services.weather.spreadsheet_service import SpreadsheetService

router = APIRouter(prefix="/admin", tags=["admin"])

# Simple in-memory cache untuk Google Sheets data
# Format: {cache_key: (data, timestamp)}
_sheets_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 30  # Cache selama 30 detik untuk mengurangi API calls


@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Dashboard admin - endpoint utama untuk admin."""
    return {
        "message": "Welcome to Admin Dashboard",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "full_name": current_admin.full_name,
        },
        "stats": {
            "total_users": db.query(User).count(),
            "total_admins": db.query(User).filter(User.role == RoleEnum.ADMIN).count(),
        },
    }


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List semua users - hanya admin yang bisa akses."""
    users = db.query(User).all()
    return users


@router.get("/me", response_model=UserResponse)
def get_admin_info(current_admin: User = Depends(get_current_admin)):
    """Get current admin information."""
    return current_admin


def _get_cached_sheets_data(spreadsheet_id: str, worksheet_name: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Get Google Sheets data dengan caching untuk mengurangi API calls
    """
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
                # Return cached data dengan warning
                return cached_data
        raise


@router.get("/spreadsheet/data")
def get_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    limit: Optional[int] = Query(default=None, description="Limit jumlah data (untuk pagination)"),
    offset: int = Query(default=0, description="Offset untuk pagination"),
    include_processed: bool = Query(default=False, description="Include processed data format"),
    force_refresh: bool = Query(default=False, description="Force refresh dari Google Sheets (bypass cache)")
) -> Dict[str, Any]:
    """
    Get data dari Google Sheets yang sudah dikonfigurasi.
    Admin tidak perlu input spreadsheet ID lagi, langsung tampilkan data.
    
    Data di-cache selama 30 detik untuk mengurangi API calls dan menghindari rate limit.
    
    Returns:
        Data spreadsheet dalam format yang siap ditampilkan di datatable
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name, force_refresh=force_refresh)
        service = SpreadsheetService()
        
        # Apply pagination jika ada limit
        total_records = len(raw_data)
        if limit:
            paginated_data = raw_data[offset:offset + limit]
        else:
            paginated_data = raw_data[offset:]
        
        # Process data jika diminta
        processed_data = None
        if include_processed and paginated_data:
            try:
                # Process latest data
                processed_data = service.process_bmkg_data(paginated_data[-1])
            except Exception as e:
                # Jika processing gagal, tetap return raw data
                processed_data = {"error": str(e)}
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "total_records": total_records,
            "limit": limit,
            "offset": offset,
            "data": paginated_data,
            "processed_data": processed_data,
            "columns": list(paginated_data[0].keys()) if paginated_data else []
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
            detail=f"Error fetching spreadsheet data: {error_msg}"
        )


@router.get("/spreadsheet/latest")
def get_latest_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    include_processed: bool = Query(default=True, description="Include processed data format")
) -> Dict[str, Any]:
    """
    Get data terbaru dari Google Sheets (baris terakhir).
    Berguna untuk menampilkan data real-time di dashboard.
    
    Returns:
        Data terbaru dalam format yang siap ditampilkan
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Yk6F3ZFLSBDna4CL7PCWKeFJNC7qLqZRhb5NNB1dCio")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name)
        
        if not raw_data:
            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "worksheet_name": worksheet_name,
                "data": None,
                "processed_data": None,
                "message": "No data found in spreadsheet"
            }
        
        # Get latest record (baris terakhir)
        latest_raw = raw_data[-1]
        service = SpreadsheetService()
        
        # Process data jika diminta
        processed_data = None
        if include_processed:
            try:
                processed_data = service.process_bmkg_data(latest_raw)
            except Exception as e:
                processed_data = {"error": str(e), "raw": latest_raw}
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "data": latest_raw,
            "processed_data": processed_data,
            "timestamp": latest_raw.get("Timestamp") or latest_raw.get("timestamp") or latest_raw.get("Date") or latest_raw.get("date")
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
            detail=f"Error fetching latest spreadsheet data: {error_msg}"
        )


@router.get("/spreadsheet/stats")
def get_spreadsheet_stats(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet")
) -> Dict[str, Any]:
    """
    Get statistics dari spreadsheet data.
    Berguna untuk menampilkan summary di dashboard.
    
    Returns:
        Statistics summary dari data spreadsheet
    """
    try:
        # Get spreadsheet ID dari config atau environment variable
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
        
        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )
        
        # Read data dari Google Sheets (dengan cache)
        raw_data = _get_cached_sheets_data(spreadsheet_id, worksheet_name)
        
        if not raw_data:
            return {
                "success": True,
                "total_records": 0,
                "columns": [],
                "stats": {}
            }
        
        # Process semua data untuk stats
        service = SpreadsheetService()
        processed_records = []
        for record in raw_data:
            try:
                processed = service.process_bmkg_data(record)
                if processed:
                    processed_records.append(processed)
            except:
                continue
        
        # Calculate statistics
        stats = {}
        if processed_records:
            numeric_fields = ['pm25', 'pm10', 'temperature', 'humidity', 'o3', 'no2', 'so2', 'co']
            for field in numeric_fields:
                values = [r.get(field) for r in processed_records if r.get(field) is not None]
                if values:
                    stats[field] = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "latest": values[-1] if values else None
                    }
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "total_records": len(raw_data),
            "processed_records": len(processed_records),
            "columns": list(raw_data[0].keys()) if raw_data else [],
            "stats": stats
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
            detail=f"Error fetching spreadsheet stats: {error_msg}"
        )

