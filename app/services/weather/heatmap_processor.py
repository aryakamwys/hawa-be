"""
Shared service untuk process heatmap data dari Google Sheets
Mengurangi duplikasi processing logic di admin.py dan weather.py
"""
from typing import Dict, List, Any, Optional


class HeatmapProcessor:
    """Service untuk process raw spreadsheet data menjadi heatmap points"""
    
    @staticmethod
    def process_heatmap_points(
        raw_data: List[Dict[str, Any]],
        spreadsheet_id: str,
        worksheet_name: str
    ) -> Dict[str, Any]:
        """
        Process raw spreadsheet data menjadi format heatmap points
        
        Args:
            raw_data: Raw data dari Google Sheets
            spreadsheet_id: Spreadsheet ID
            worksheet_name: Worksheet name
        
        Returns:
            Dictionary dengan format heatmap data
        """
        if not raw_data:
            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "worksheet_name": worksheet_name,
                "points": [],
                "total_points": 0,
                "center": None
            }
        
        heatmap_points = []
        
        for idx, record in enumerate(raw_data, start=1):
            try:
                point = HeatmapProcessor._extract_point(record, idx)
                if point:
                    heatmap_points.append(point)
            except Exception:
                continue
        
        center = HeatmapProcessor._calculate_center(heatmap_points)
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet_name,
            "points": heatmap_points,
            "total_points": len(heatmap_points),
            "center": center
        }
    
    @staticmethod
    def _extract_point(record: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """Extract single point dari record"""
        def get_field_value(field_variants: List[str], default: Any = None) -> Any:
            for variant in field_variants:
                for key in record.keys():
                    if str(key).lower() == variant.lower():
                        value = record[key]
                        if isinstance(value, str):
                            try:
                                return float(value) if value.strip() else default
                            except ValueError:
                                return value if value else default
                        return value if value is not None else default
            return default
        
        latitude = get_field_value(['Latitude', 'latitude', 'lat'])
        longitude = get_field_value(['Longitude', 'longitude', 'lng', 'lon'])
        
        if latitude is None or longitude is None:
            return None
        
        try:
            lat = float(latitude) if not isinstance(latitude, float) else latitude
            lng = float(longitude) if not isinstance(longitude, float) else longitude
        except (ValueError, TypeError):
            return None
        
        pm25 = get_field_value(['PM2.5', 'pm2.5', 'PM25', 'pm25', 'PM 2.5'])
        pm10 = get_field_value(['PM10', 'pm10', 'PM 10'])
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
        
        risk_level = HeatmapProcessor._determine_risk_level(air_quality, risk_score)
        
        return {
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
    
    @staticmethod
    def _determine_risk_level(air_quality: Any, risk_score: Any) -> str:
        """Determine risk level dari air quality atau risk score"""
        risk_level = "low"
        
        if isinstance(air_quality, str):
            air_quality_upper = air_quality.upper()
            if "POOR" in air_quality_upper or "UNHEALTHY" in air_quality_upper:
                risk_level = "high"
            elif "MODERATE" in air_quality_upper:
                risk_level = "moderate"
            elif "GOOD" in air_quality_upper:
                risk_level = "low"
        
        if isinstance(risk_score, (int, float)):
            if risk_score >= 0.7:
                risk_level = "high"
            elif risk_score >= 0.4:
                risk_level = "moderate"
            else:
                risk_level = "low"
        
        return risk_level
    
    @staticmethod
    def _calculate_center(points: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        """Calculate center point dari list of points"""
        if not points:
            return None
        
        return {
            "lat": sum(p["lat"] for p in points) / len(points),
            "lng": sum(p["lng"] for p in points) / len(points)
        }
