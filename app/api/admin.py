"""Admin routes - hanya bisa diakses oleh admin."""
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.core.config import get_settings
from app.core.exceptions import handle_google_sheets_error
from app.db.postgres import get_db
from app.db.models.user import User, RoleEnum
from app.services.auth.schemas import UserResponse
from app.services.weather.heatmap_processor import HeatmapProcessor
from app.services.weather.sheets_cache_service import get_cached_sheets_data
from app.services.weather.spreadsheet_service import SpreadsheetService

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.get("/spreadsheet/data")
def get_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    limit: Optional[int] = Query(
        default=None,
        description="Limit jumlah data (untuk pagination)"
    ),
    offset: int = Query(default=0, description="Offset untuk pagination"),
    include_processed: bool = Query(
        default=False,
        description="Include processed data format"
    ),
    force_refresh: bool = Query(
        default=False,
        description="Force refresh dari Google Sheets (bypass cache)"
    )
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
        default_sheet_id = "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA"
        spreadsheet_id = (
            settings.google_sheets_id or
            os.getenv("GOOGLE_SHEETS_ID", default_sheet_id)
        )

        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )

        raw_data = get_cached_sheets_data(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            force_refresh=force_refresh
        )
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
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.get("/spreadsheet/latest")
def get_latest_spreadsheet_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    include_processed: bool = Query(
        default=True,
        description="Include processed data format"
    )
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
        default_sheet_id = "1Yk6F3ZFLSBDna4CL7PCWKeFJNC7qLqZRhb5NNB1dCio"
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", default_sheet_id)

        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )

        raw_data = get_cached_sheets_data(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name
        )

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
            "timestamp": (
                latest_raw.get("Timestamp") or
                latest_raw.get("timestamp") or
                latest_raw.get("Date") or
                latest_raw.get("date")
            )
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.get("/spreadsheet/stats")
def get_spreadsheet_stats(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(
        default="Sheet1",
        description="Nama worksheet"
    )
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
        default_sheet_id = "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA"
        spreadsheet_id = (
            settings.google_sheets_id or
            os.getenv("GOOGLE_SHEETS_ID", default_sheet_id)
        )

        if not spreadsheet_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_SHEETS_ID not configured in environment variables"
            )

        raw_data = get_cached_sheets_data(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name
        )

        if not raw_data:
            return {
                "success": True,
                "total_records": 0,
                "columns": [],
                "stats": {}
            }

        service = SpreadsheetService()
        processed_records = []
        for record in raw_data:
            try:
                processed = service.process_bmkg_data(record)
                if processed:
                    processed_records.append(processed)
            except Exception:
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
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.get("/heatmap")
def get_heatmap_data(
    current_admin: User = Depends(get_current_admin),
    worksheet_name: str = Query(default="Sheet1", description="Nama worksheet"),
    force_refresh: bool = Query(
        default=False,
        description="Force refresh dari Google Sheets (bypass cache)"
    )
) -> Dict[str, Any]:
    """
    Get heatmap data dari Google Sheets untuk visualisasi peta.
    Data diambil dari spreadsheet heatmap dengan format:
    - Location, Latitude, Longitude, PM2.5, PM10, Air Quality, Risk Score, Color, Device ID

    Returns:
        Array of heatmap points dengan format siap untuk frontend map visualization
    """
    heatmap_spreadsheet_id = "1p69Ae67JGlScrMlSDnebuZMghXYMY7IykiT1gQwello"

    try:
        raw_data = get_cached_sheets_data(
            spreadsheet_id=heatmap_spreadsheet_id,
            worksheet_name=worksheet_name,
            force_refresh=force_refresh
        )

        return HeatmapProcessor.process_heatmap_points(
            raw_data=raw_data,
            spreadsheet_id=heatmap_spreadsheet_id,
            worksheet_name=worksheet_name
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)

