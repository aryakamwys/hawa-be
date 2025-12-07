import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


class GroqWeatherService:
    """Generate personalized weather recommendations using Groq LLM."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"

    def generate_recommendation(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        context_knowledge: List[str],
        language: str = "id",
        use_streaming: bool = False
    ) -> Dict[str, Any]:
        """Generate structured personalized weather recommendation."""

        system_prompt = self._build_system_prompt(language)
        user_prompt = self._build_user_prompt(weather_data, user_profile, context_knowledge, language)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                top_p=0.9,
                stream=use_streaming,
                # JSON Mode untuk structured output
                response_format={"type": "json_object"},
            )

            if use_streaming:
                return self._handle_streaming(response)

            content = response.choices[0].message.content
            return self._parse_response(content)

        except (ValueError, KeyError, AttributeError) as e:
            return {
                "error": f"Error generating recommendation: {str(e)}",
                "risk_level": "unknown",
                "recommendations": [],
                "primary_concern": "",
                "personalized_advice": "",
                "warnings": [],
                "raw_error": str(e)
            }
        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}",
                "risk_level": "unknown",
                "recommendations": [],
                "primary_concern": "",
                "personalized_advice": "",
                "warnings": [],
                "raw_error": str(e)
            }

    def _build_system_prompt(self, language: str) -> str:
        return """You are an environmental health and meteorology expert focused on West Java air pollution (BMKG Bandung context).
Use current weather/air-quality data and user profile (age, occupation, health conditions, location, sensitivity) to produce a personalized warning.
Reasoning steps:
- Analyze data: PM2.5, PM10, O3, NO2, SO2, CO, temperature, humidity, vulnerability.
- Assess risk_level: low|medium|high|critical (WHO/IDN aligned).
- Personalize to the profile (child, elderly, respiratory/cardiac conditions).
- Provide 3-5 concrete, prioritized actions and clear warnings (what to avoid, impacted activities).
Output JSON strictly:
{
  "risk_level": "low|medium|high|critical",
  "air_quality_index": number,
  "primary_concern": "string",
  "recommendations": [
    {
      "priority": "high|medium|low",
      "category": "health|activity|equipment|medication",
      "action": "string",
      "reasoning": "string"
    }
  ],
  "warnings": [
    {
      "severity": "info|warning|danger",
      "message": "string",
      "affected_activities": ["string"]
    }
  ],
  "personalized_advice": "string",
  "next_check_time": "string"
}
Style: direct, concise, actionable, non-chatty, include brief reasoning for each action. If data insufficient, pick the safest conservative risk_level and still return the full JSON."""

    def _build_user_prompt(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        context_knowledge: List[str],
        language: str
    ) -> str:
        """Build contextual user prompt dengan semua informasi relevan"""

        weather_context = f"""
DATA CUACA & KUALITAS UDARA TERKINI:
- PM2.5: {weather_data.get('pm25', 'N/A')} μg/m³
- PM10: {weather_data.get('pm10', 'N/A')} μg/m³
- O3: {weather_data.get('o3', 'N/A')} ppb
- NO2: {weather_data.get('no2', 'N/A')} ppb
- SO2: {weather_data.get('so2', 'N/A')} ppb
- CO: {weather_data.get('co', 'N/A')} ppm
- Suhu: {weather_data.get('temperature', 'N/A')}°C
- Kelembaban: {weather_data.get('humidity', 'N/A')}%
- Lokasi: {weather_data.get('location', 'N/A')}
- Timestamp: {weather_data.get('timestamp', 'N/A')}
"""

        profile_context = f"""
PROFIL PENGGUNA:
- Umur: {user_profile.get('age', 'N/A')} tahun
- Pekerjaan: {user_profile.get('occupation', 'N/A')}
- Lokasi: {user_profile.get('location', 'N/A')}
- Level Aktivitas: {user_profile.get('activity_level', 'N/A')}
- Level Sensitivitas: {user_profile.get('sensitivity_level', 'N/A')}
- Kondisi Kesehatan: {user_profile.get('health_conditions', 'Tidak ada')}
"""

        knowledge_context = ""
        if context_knowledge:
            knowledge_context = "\n".join([
                f"KONTEKS PENGETAHUAN {i+1}: {knowledge}"
                for i, knowledge in enumerate(context_knowledge[:3])
            ])

        task_prompts = {
            "id": "TUGAS:\nBerdasarkan data di atas, berikan rekomendasi peringatan kesehatan yang PERSONALISASI untuk pengguna ini.\nFokus pada:\n1. Aktivitas yang HARUS DIHINDARI atau DIBATASI\n2. Perlindungan yang DIPERLUKAN\n3. Tindakan pencegahan SPESIFIK untuk profil pengguna ini\n4. Timeline kapan harus mengecek ulang\n\nBerikan output dalam format JSON sesuai dengan spesifikasi sistem.",
            "en": "TASK:\nBased on the above data, provide PERSONALIZED health warning recommendations for this user.\nFocus on:\n1. Activities that MUST BE AVOIDED or LIMITED\n2. Protection REQUIRED\n3. SPECIFIC preventive measures for this user profile\n4. Timeline when to check again\n\nProvide output in JSON format according to system specifications.",
            "su": "TUGAS:\nDumasar kana data di luhur, masihan rekomendasi peringatan kaséhatan anu PERSONALISASI pikeun pangguna ieu.\nFokus kana:\n1. Aktivitas anu KUDU DIHINDARI atanapi DIBATASI\n2. Perlindungan anu DIPERLUKAN\n3. Tindakan pencegahan SPESIFIK pikeun profil pangguna ieu\n4. Timeline iraha kudu mariksa deui\n\nMasihan output dina format JSON luyu sareng spésifikasi sistem."
        }

        task = task_prompts.get(language, task_prompts["id"])

        return f"""
{weather_context}

{profile_context}

{knowledge_context}

{task}
"""

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response dari LLM"""
        def ensure_list(obj: Dict[str, Any], key: str) -> List[Any]:
            val = obj.get(key, [])
            return val if isinstance(val, list) else []

        try:
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            data = json.loads(content)

            if "risk_level" not in data or data["risk_level"] not in ["low", "medium", "high", "critical"]:
                data["risk_level"] = "unknown"
            data["primary_concern"] = data.get("primary_concern", "")
            data["personalized_advice"] = data.get("personalized_advice", "")
            data["warnings"] = ensure_list(data, "warnings")
            data["recommendations"] = ensure_list(data, "recommendations")
            data["next_check_time"] = data.get("next_check_time", "2 jam lagi")
            return data

        except json.JSONDecodeError as e:
            return {
                "error": "Failed to parse response",
                "raw_content": content,
                "parse_error": str(e),
                "risk_level": "unknown",
                "primary_concern": "",
                "personalized_advice": "",
                "recommendations": [],
                "warnings": [],
                "next_check_time": "2 jam lagi"
            }

    def _handle_streaming(self, stream):
        """Handle streaming response"""
        full_content = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
        return self._parse_response(full_content)
