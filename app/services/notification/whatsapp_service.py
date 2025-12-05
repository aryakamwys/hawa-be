"""WhatsApp notification service using pywhatkit."""
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pywhatkit as pwt


class WhatsAppService:
    """Service untuk mengirim notifikasi peringatan cuaca ke WhatsApp"""
    
    def __init__(self):
        pass
    
    def send_weather_warning(
        self,
        phone_number: str,
        recommendation: Dict[str, Any],
        language: str = "id"
    ) -> bool:
        """Kirim peringatan cuaca ke WhatsApp."""
        try:
            message = self._format_warning_message(recommendation, language)
            now = datetime.now()
            send_time = now + timedelta(minutes=1)
            pwt.sendwhatmsg(
                phone_no=phone_number,
                message=message,
                time_hour=send_time.hour,
                time_min=send_time.minute,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {e}")
            return False
    
    def send_weather_warning_instant(
        self,
        phone_number: str,
        recommendation: Dict[str, Any],
        language: str = "id"
    ) -> bool:
        """Kirim peringatan cuaca ke WhatsApp secara instan."""
        try:
            message = self._format_warning_message(recommendation, language)
            pwt.sendwhatmsg_instantly(
                phone_no=phone_number,
                message=message,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {e}")
            return False
    
    def _format_warning_message(
        self,
        recommendation: Dict[str, Any],
        language: str
    ) -> str:
        """Format pesan peringatan berdasarkan bahasa"""
        
        risk_level = recommendation.get("risk_level", "unknown")
        primary_concern = recommendation.get("primary_concern", "")
        personalized_advice = recommendation.get("personalized_advice", "")
        
        next_dt = datetime.now() + timedelta(hours=2)
        next_check = next_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        if language == "id":
            message = f"""⚠️ *PERINGATAN KUALITAS UDARA*

*Level Risiko:* {risk_level.upper()}

*Kekhawatiran Utama:*
{primary_concern}

*Rekomendasi Personalisasi:*
{personalized_advice}

*Rekomendasi Tindakan:*
"""
            for rec in recommendation.get("recommendations", [])[:3]:  # Top 3
                priority_emoji = "🔴" if rec.get("priority") == "high" else "🟡" if rec.get("priority") == "medium" else "🟢"
                message += f"\n{priority_emoji} {rec.get('action', '')}"
            
            message += f"\n\n⏰ *Cek ulang:* {next_check}"
            message += "\n\n_HAWA - Air Quality Monitoring System_"
            
        elif language == "en":
            message = f"""⚠️ *AIR QUALITY WARNING*

*Risk Level:* {risk_level.upper()}

*Primary Concern:*
{primary_concern}

*Personalized Recommendation:*
{personalized_advice}

*Action Items:*
"""
            for rec in recommendation.get("recommendations", [])[:3]:
                priority_emoji = "🔴" if rec.get("priority") == "high" else "🟡" if rec.get("priority") == "medium" else "🟢"
                message += f"\n{priority_emoji} {rec.get('action', '')}"
            
            message += f"\n\n⏰ *Next check:* {next_check}"
            message += "\n\n_HAWA - Air Quality Monitoring System_"
            
        else:  # su (Sunda)
            message = f"""⚠️ *PERINGATAN KUALITAS UDARA*

*Tingkat Résiko:* {risk_level.upper()}

*Kekhawatiran Utama:*
{primary_concern}

*Rekomendasi Personalisasi:*
{personalized_advice}

*Tindakan:*
"""
            for rec in recommendation.get("recommendations", [])[:3]:
                priority_emoji = "🔴" if rec.get("priority") == "high" else "🟡" if rec.get("priority") == "medium" else "🟢"
                message += f"\n{priority_emoji} {rec.get('action', '')}"
            
            message += f"\n\n⏰ *Mariksa deui:* {next_check}"
            message += "\n\n_HAWA - Air Quality Monitoring System_"
        
        return message
    
    def send_simple_warning(
        self,
        phone_number: str,
        risk_level: str,
        message: str,
        language: str = "id"
    ) -> bool:
        """
        Kirim peringatan sederhana ke WhatsApp
        
        Args:
            phone_number: Nomor WhatsApp
            risk_level: Level risiko (low, medium, high, critical)
            message: Pesan peringatan
            language: Bahasa
        
        Returns:
            True jika berhasil
        """
        try:
            risk_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴"
            }.get(risk_level.lower(), "⚠️")
            
            formatted_message = f"{risk_emoji} *PERINGATAN KUALITAS UDARA*\n\n{message}\n\n_HAWA - Air Quality Monitoring System_"
            
            now = datetime.now()
            send_time = now + timedelta(minutes=1)
            
            pwt.sendwhatmsg(
                phone_no=phone_number,
                message=formatted_message,
                time_hour=send_time.hour,
                time_min=send_time.minute,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {e}")
            return False

