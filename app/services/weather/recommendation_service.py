"""
Main Weather Recommendation Service
Menggabungkan semua service untuk generate personalized recommendations
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.db.models.user import User
from app.services.weather.groq_service import GroqWeatherService
from app.services.weather.vector_service import VectorService
from app.services.weather.spreadsheet_service import SpreadsheetService


class WeatherRecommendationService:
    """Main service untuk generate personalized weather recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.groq_service = GroqWeatherService()
        self.vector_service = VectorService()
        self.spreadsheet_service = SpreadsheetService()
    
    def get_personalized_recommendation(
        self,
        user: User,
        weather_data: Dict[str, Any] | None = None,
        spreadsheet_path: str | None = None,
        google_sheets_id: str | None = None,
        google_sheets_worksheet: str = "Sheet1"
    ) -> Dict[str, Any]:
        """
        Generate personalized recommendation untuk user
        
        Args:
            user: User object dengan profile lengkap
            weather_data: Data cuaca langsung (optional)
            spreadsheet_path: Path ke spreadsheet file (optional)
        
        Returns:
            Dictionary dengan rekomendasi terstruktur
        """
        # 1. Get atau load weather data
        if weather_data is None:
            if google_sheets_id:
                # Read from Google Sheets
                raw_data = self.spreadsheet_service.read_from_google_sheets(
                    spreadsheet_id=google_sheets_id,
                    worksheet_name=google_sheets_worksheet
                )
                weather_data = self.spreadsheet_service.process_bmkg_data(raw_data)
            elif spreadsheet_path:
                # Read from local file
                raw_data = self.spreadsheet_service.read_weather_data(spreadsheet_path)
                weather_data = self.spreadsheet_service.process_bmkg_data(raw_data)
            else:
                raise ValueError(
                    "Either weather_data, spreadsheet_path, or google_sheets_id must be provided"
                )
        
        # Validate weather data
        if not self.spreadsheet_service.validate_weather_data(weather_data):
            raise ValueError("Invalid weather data: missing required fields")
        
        # 2. Build user profile
        user_profile = self._build_user_profile(user)
        
        # 3. Get relevant context dari vector DB
        query_context = self._build_query_context(weather_data, user_profile)
        context_knowledge = self.vector_service.search_similar(
            self.db,
            query_context,
            language=user.language.value if user.language else "id",
            limit=3
        )
        
        # 4. Generate recommendation dengan Groq LLM
        recommendation = self.groq_service.generate_recommendation(
            weather_data=weather_data,
            user_profile=user_profile,
            context_knowledge=context_knowledge,
            language=user.language.value if user.language else "id",
            use_streaming=False
        )
        
        # 5. Add metadata
        recommendation["metadata"] = {
            "user_id": user.id,
            "location": weather_data.get("location", "Unknown"),
            "timestamp": weather_data.get("timestamp"),
            "language": user.language.value if user.language else "id"
        }
        
        return recommendation
    
    def _build_user_profile(self, user: User) -> Dict[str, Any]:
        """Build user profile dictionary dari User model"""
        profile = {
            'age': user.age,
            'occupation': user.occupation,
            'location': user.location,
            'activity_level': user.activity_level,
            'sensitivity_level': user.sensitivity_level or "medium",
            'health_conditions': 'Tidak ada'
        }
        
        # Decrypt health conditions jika ada
        if user.health_conditions_encrypted:
            try:
                from app.core.security import decrypt_user_health_data
                profile['health_conditions'] = decrypt_user_health_data(
                    user.health_conditions_encrypted
                )
            except Exception:
                profile['health_conditions'] = 'Data tidak tersedia'
        
        return profile
    
    def _build_query_context(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> str:
        """Build query context untuk vector search"""
        location = weather_data.get('location', 'Bandung')
        occupation = user_profile.get('occupation', '')
        sensitivity = user_profile.get('sensitivity_level', 'medium')
        
        # Build query yang relevan untuk similarity search
        query = f"polusi udara {location}"
        if occupation:
            query += f" {occupation}"
        if sensitivity:
            query += f" sensitivitas {sensitivity}"
        
        return query

