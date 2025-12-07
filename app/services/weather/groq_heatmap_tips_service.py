"""
Groq Heatmap Tips Service
Service untuk generate AI tips untuk heatmap menggunakan Groq LLM
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


class GroqHeatmapTipsService:
    """Service untuk generate AI tips untuk heatmap menggunakan Groq LLM."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"

    def generate_tips(
        self,
        pm25: Optional[float] = None,
        pm10: Optional[float] = None,
        air_quality: Optional[str] = None,
        risk_level: Optional[str] = None,
        location: Optional[str] = None,
        language: str = "id"
    ) -> Dict[str, Any]:
        # Build prompt untuk tips
        system_prompt = self._build_system_prompt(language)
        user_prompt = self._build_user_prompt(
            pm25, pm10, air_quality, risk_level, location, language
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                top_p=0.9,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            parsed = self._parse_response(content, language)
            return parsed

        except (ValueError, KeyError, AttributeError) as e:
            return self._get_fallback_tips(pm25, pm10, risk_level, language)
        except Exception as e:
            return self._get_fallback_tips(pm25, pm10, risk_level, language)

    def _build_system_prompt(self, language: str) -> str:
        prompts = {
            "id": """Anda adalah ahli kesehatan lingkungan dan kualitas udara yang berpengalaman.
Tugas Anda adalah memberikan penjelasan yang mudah dipahami dan tips praktis tentang polusi udara berdasarkan data PM2.5 dan PM10 untuk ditampilkan di heatmap dashboard.

Output JSON dengan format:
{
  "title": "Judul penjelasan",
  "explanation": "Penjelasan singkat tentang kondisi polusi udara saat ini",
  "tips": [
    {
      "category": "Kesehatan|Aktivitas|Perlindungan",
      "tip": "Tips praktis yang bisa dilakukan",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Dampak kesehatan yang mungkin terjadi",
  "prevention": "Cara pencegahan yang disarankan"
}

Gunakan bahasa Indonesia yang mudah dipahami, informatif, dan actionable. Fokus pada tips yang relevan dengan tingkat polusi yang ditampilkan.""",
            "en": """You are an experienced environmental health and air quality expert.
Your task is to provide easy-to-understand explanations and practical tips about air pollution based on PM2.5 and PM10 data for display on a heatmap dashboard.

Output JSON with format:
{
  "title": "Explanation title",
  "explanation": "Brief explanation about current air pollution condition",
  "tips": [
    {
      "category": "Health|Activity|Protection",
      "tip": "Practical tip that can be done",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Possible health impacts",
  "prevention": "Recommended prevention methods"
}

Use easy-to-understand English, informative, and actionable. Focus on tips relevant to the pollution level displayed.""",
            "su": """Anjeun ahli kaséhatan lingkungan sareng kualitas udara anu berpengalaman.
Tugas anjeun nyaéta masihan penjelasan anu gampang dipahami sareng tips praktis ngeunaan polusi udara dumasar kana data PM2.5 sareng PM10 pikeun ditampilkeun dina heatmap dashboard.

Output JSON kalayan format:
{
  "title": "Judul penjelasan",
  "explanation": "Penjelasan singkat ngeunaan kaayaan polusi udara ayeuna",
  "tips": [
    {
      "category": "Kaséhatan|Aktivitas|Perlindungan",
      "tip": "Tips praktis anu tiasa dilakukeun",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Dampak kaséhatan anu mungkin lumangsung",
  "prevention": "Cara pencegahan anu disarankeun"
}

Gunakeun basa Sunda anu gampang dipahami, informatif, sareng actionable. Fokus kana tips anu relevan sareng tingkat polusi anu ditampilkeun."""
        }
        return prompts.get(language, prompts["id"])

    def _build_user_prompt(
        self,
        pm25: Optional[float],
        pm10: Optional[float],
        air_quality: Optional[str],
        risk_level: Optional[str],
        location: Optional[str],
        language: str
    ) -> str:
        """Build user prompt dengan data polusi"""
        data_info = f"""
DATA KUALITAS UDARA:
- PM2.5: {pm25 if pm25 is not None else 'Tidak tersedia'} μg/m³
- PM10: {pm10 if pm10 is not None else 'Tidak tersedia'} μg/m³
- Status Kualitas Udara: {air_quality if air_quality else 'Tidak tersedia'}
- Level Risiko: {risk_level.upper() if risk_level else 'Tidak tersedia'}
- Lokasi: {location if location else 'Tidak tersedia'}
"""

        task_prompts = {
            "id": """Berdasarkan data di atas, berikan:
1. Penjelasan singkat tentang kondisi polusi udara saat ini di lokasi tersebut
2. Tips praktis yang bisa dilakukan untuk melindungi kesehatan (3-5 tips)
3. Dampak kesehatan yang mungkin terjadi jika terpapar polusi ini
4. Cara pencegahan yang disarankan

Fokus pada tips yang actionable dan mudah dipahami oleh masyarakat umum. Tips harus relevan dengan tingkat polusi yang ditampilkan.""",
            "en": """Based on the above data, provide:
1. Brief explanation about current air pollution condition at this location
2. Practical tips that can be done to protect health (3-5 tips)
3. Possible health impacts if exposed to this pollution
4. Recommended prevention methods

Focus on actionable tips that are easy to understand for the general public. Tips must be relevant to the pollution level displayed.""",
            "su": """Dumasar kana data di luhur, masihan:
1. Penjelasan singkat ngeunaan kaayaan polusi udara ayeuna di lokasi éta
2. Tips praktis anu tiasa dilakukeun pikeun ngajaga kaséhatan (3-5 tips)
3. Dampak kaséhatan anu mungkin lumangsung upami kakeunaan polusi ieu
4. Cara pencegahan anu disarankeun

Fokus kana tips anu actionable sareng gampang dipahami ku masarakat umum. Tips kedah relevan sareng tingkat polusi anu ditampilkeun."""
        }

        task = task_prompts.get(language, task_prompts["id"])
        return f"{data_info}\n\n{task}"

    def _parse_response(self, content: str, language: str) -> Dict[str, Any]:
        try:
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            data = json.loads(content)

            data.setdefault("title", self._get_default_title(language))
            data.setdefault("explanation", "")
            data.setdefault("tips", [])
            data.setdefault("health_impact", "")
            data.setdefault("prevention", "")

            if isinstance(data.get("tips"), list):
                for tip in data["tips"]:
                    if not isinstance(tip, dict):
                        continue
                    tip.setdefault("category", "Kesehatan" if language == "id" else "Health")
                    tip.setdefault("tip", "")
                    tip.setdefault("priority", "medium")

            return data
        except json.JSONDecodeError:
            return self._get_fallback_tips(None, None, None, language)

    def _get_default_title(self, language: str) -> str:
        titles = {
            "id": "Tips Kesehatan & Pencegahan",
            "en": "Health & Prevention Tips",
            "su": "Tips Kaséhatan & Pencegahan"
        }
        return titles.get(language, titles["id"])

    def _get_fallback_tips(
        self,
        pm25: Optional[float],
        pm10: Optional[float],
        risk_level: Optional[str],
        language: str
    ) -> Dict[str, Any]:
        """Get fallback tips jika LLM error"""
        if language == "id":
            if risk_level == "high":
                tips = [
                    {
                        "category": "Kesehatan",
                        "tip": "Gunakan masker N95 saat berada di luar ruangan",
                        "priority": "high"
                    },
                    {
                        "category": "Aktivitas",
                        "tip": "Hindari aktivitas fisik berat di luar ruangan",
                        "priority": "high"
                    },
                    {
                        "category": "Perlindungan",
                        "tip": "Tutup jendela dan gunakan air purifier di dalam ruangan",
                        "priority": "medium"
                    },
                    {
                        "category": "Kesehatan",
                        "tip": "Minum air putih lebih banyak untuk membantu detoksifikasi",
                        "priority": "medium"
                    }
                ]
                health_impact = "Paparan polusi udara tinggi dapat menyebabkan iritasi mata, batuk, sesak napas, memperburuk kondisi pernapasan seperti asma, dan meningkatkan risiko penyakit jantung."
                prevention = "Hindari aktivitas di luar ruangan saat polusi tinggi, gunakan masker N95, pastikan sirkulasi udara di dalam ruangan baik dengan air purifier, dan konsultasi dokter jika mengalami gejala pernapasan."
            elif risk_level == "moderate":
                tips = [
                    {
                        "category": "Kesehatan",
                        "tip": "Gunakan masker saat berada di luar ruangan untuk waktu lama",
                        "priority": "medium"
                    },
                    {
                        "category": "Aktivitas",
                        "tip": "Batasi aktivitas fisik di luar ruangan, terutama untuk kelompok sensitif",
                        "priority": "medium"
                    },
                    {
                        "category": "Perlindungan",
                        "tip": "Pastikan ventilasi ruangan baik",
                        "priority": "low"
                    }
                ]
                health_impact = "Paparan polusi udara sedang dapat menyebabkan iritasi ringan pada mata dan saluran pernapasan, terutama pada kelompok sensitif seperti anak-anak, lansia, dan penderita asma."
                prevention = "Kelompok sensitif perlu berhati-hati. Gunakan masker saat beraktivitas di luar, batasi waktu di luar ruangan, dan pastikan ventilasi dalam ruangan baik."
            else:  # low
                tips = [
                    {
                        "category": "Kesehatan",
                        "tip": "Kualitas udara baik, tetap jaga kesehatan dengan pola hidup sehat",
                        "priority": "low"
                    },
                    {
                        "category": "Aktivitas",
                        "tip": "Aman untuk melakukan aktivitas di luar ruangan",
                        "priority": "low"
                    }
                ]
                health_impact = "Kualitas udara baik, risiko kesehatan minimal."
                prevention = "Pertahankan kualitas udara dengan mengurangi penggunaan kendaraan pribadi dan menjaga lingkungan tetap bersih."

            return {
                "title": "Tips Kesehatan & Pencegahan",
                "explanation": (
                    "PM2.5 adalah partikel halus di udara yang dapat masuk ke "
                    "paru-paru dan menyebabkan masalah kesehatan. "
                    f"{'Kondisi saat ini menunjukkan tingkat polusi yang ' + ('tinggi' if risk_level == 'high' else 'sedang' if risk_level == 'moderate' else 'rendah') + '.' if risk_level else 'Kondisi saat ini perlu dipantau.'}"
                ),
                "tips": tips,
                "health_impact": health_impact,
                "prevention": prevention
            }
        elif language == "en":
            if risk_level == "high":
                tips = [
                    {
                        "category": "Health",
                        "tip": "Use N95 mask when outdoors",
                        "priority": "high"
                    },
                    {
                        "category": "Activity",
                        "tip": "Avoid heavy physical activity outdoors",
                        "priority": "high"
                    },
                    {
                        "category": "Protection",
                        "tip": "Close windows and use air purifier indoors",
                        "priority": "medium"
                    }
                ]
                health_impact = "High air pollution exposure can cause eye irritation, cough, shortness of breath, worsen respiratory conditions like asthma, and increase heart disease risk."
                prevention = "Avoid outdoor activities when pollution is high, use N95 masks, ensure good indoor air circulation with air purifiers, and consult a doctor if experiencing respiratory symptoms."
            elif risk_level == "moderate":
                tips = [
                    {
                        "category": "Health",
                        "tip": "Use mask when outdoors for extended periods",
                        "priority": "medium"
                    },
                    {
                        "category": "Activity",
                        "tip": "Limit outdoor physical activity, especially for sensitive groups",
                        "priority": "medium"
                    }
                ]
                health_impact = "Moderate air pollution exposure can cause mild irritation to eyes and respiratory tract, especially in sensitive groups like children, elderly, and asthma patients."
                prevention = "Sensitive groups should be cautious. Use masks when outdoors, limit outdoor time, and ensure good indoor ventilation."
            else:
                tips = [
                    {
                        "category": "Health",
                        "tip": "Air quality is good, maintain health with healthy lifestyle",
                        "priority": "low"
                    }
                ]
                health_impact = "Air quality is good, minimal health risk."
                prevention = "Maintain air quality by reducing private vehicle use and keeping the environment clean."

            return {
                "title": "Health & Prevention Tips",
                "explanation": (
                    "PM2.5 are fine particles in the air that can enter the "
                    "lungs and cause health problems. "
                    f"{'Current conditions show ' + ('high' if risk_level == 'high' else 'moderate' if risk_level == 'moderate' else 'low') + ' pollution levels.' if risk_level else 'Current conditions need monitoring.'}"
                ),
                "tips": tips,
                "health_impact": health_impact,
                "prevention": prevention
            }
        else:  # su
            return {
                "title": "Tips Kaséhatan & Pencegahan",
                "explanation": "PM2.5 nyaéta partikel halus di udara anu tiasa asup kana paru-paru sareng nyababkeun masalah kaséhatan. Beuki luhur nilaina, beuki bahaya pikeun kaséhatan.",
                "tips": [
                    {
                        "category": "Kaséhatan",
                        "tip": "Gunakeun masker N95 nalika di luar ruangan",
                        "priority": "high"
                    },
                    {
                        "category": "Aktivitas",
                        "tip": "Hindari aktivitas fisik beurat di luar ruangan",
                        "priority": "medium"
                    },
                    {
                        "category": "Perlindungan",
                        "tip": "Tutup jandela sareng gunakeun air purifier di jero ruangan",
                        "priority": "medium"
                    }
                ],
                "health_impact": "Paparan polusi udara tiasa nyababkeun iritasi panon, batuk, sesak napas, sareng ngorakeun kaayaan pernapasan.",
                "prevention": "Hindari aktivitas di luar ruangan nalika polusi luhur, gunakeun masker, sareng pastikeun sirkulasi udara di jero ruangan saé."
            }
