"""
Shared service untuk Google Sheets caching
Mengurangi duplikasi cache logic di admin.py dan weather.py
"""
import time
from typing import Dict, List, Any, Tuple

from app.services.weather.spreadsheet_service import SpreadsheetService


class SheetsCacheService:
    """Service untuk cache Google Sheets data dengan TTL"""
    
    def __init__(self, ttl_seconds: int = 30):
        self._cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
        self.ttl_seconds = ttl_seconds
        self._service = SpreadsheetService()
    
    def get_cached_data(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get Google Sheets data dengan caching untuk mengurangi API calls
        
        Args:
            spreadsheet_id: Google Sheets ID
            worksheet_name: Nama worksheet
            force_refresh: Force refresh dari Google Sheets (bypass cache)
        
        Returns:
            List of dictionaries dengan data dari spreadsheet
        """
        cache_key = f"{spreadsheet_id}:{worksheet_name}"
        current_time = time.time()
        
        if not force_refresh and cache_key in self._cache:
            cached_data, cache_timestamp = self._cache[cache_key]
            if current_time - cache_timestamp < self.ttl_seconds:
                return cached_data
        
        try:
            raw_data = self._service.read_from_google_sheets(
                spreadsheet_id=spreadsheet_id,
                worksheet_name=worksheet_name
            )
            self._cache[cache_key] = (raw_data, current_time)
            return raw_data
        except Exception as e:
            if cache_key in self._cache:
                error_msg = str(e)
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    cached_data, _ = self._cache[cache_key]
                    return cached_data
            raise
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()


# Global instance untuk shared cache
_sheets_cache_service = SheetsCacheService(ttl_seconds=30)


def get_cached_sheets_data(
    spreadsheet_id: str,
    worksheet_name: str,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function untuk get cached sheets data
    Menggunakan global cache service instance
    """
    return _sheets_cache_service.get_cached_data(
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        force_refresh=force_refresh
    )
