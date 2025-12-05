#!/usr/bin/env python3

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import argparse
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.db.models.user import User
from app.services.weather.recommendation_service import WeatherRecommendationService
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.notification.whatsapp_service import WhatsAppService
from app.core.config import get_settings


def check_and_send_warnings(
    db: Session,
    user_id: Optional[int] = None,
    min_risk_level: str = "medium",
    spreadsheet_id: Optional[str] = None,
    worksheet_name: str = "Sheet1",
    verbose: bool = False,
) -> dict:
    """
    Check data cuaca dan kirim warning ke WhatsApp jika perlu
    
    Args:
        db: Database session
        user_id: User ID tertentu (None untuk semua users)
        min_risk_level: Minimum risk level untuk kirim warning (low, medium, high, critical)
        spreadsheet_id: Google Sheets ID (None untuk ambil dari config)
        worksheet_name: Nama worksheet
    
    Returns:
        Dictionary dengan hasil pengiriman
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "checked_users": 0,
        "warnings_sent": 0,
        "warnings_skipped": 0,
        "errors": [],
        "details": []
    }
    
    risk_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_risk_value = risk_levels.get(min_risk_level.lower(), 1)
    
    if not spreadsheet_id:
        settings = get_settings()
        spreadsheet_id = settings.google_sheets_id or os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
    
    if user_id:
        users = db.query(User).filter(
            User.id == user_id,
            User.phone_e164.isnot(None),
            User.phone_e164 != ''
        ).all()
    else:
        users = db.query(User).filter(
            User.phone_e164.isnot(None),
            User.phone_e164 != '',
            User.privacy_consent == True
        ).all()
    
    if not users:
        results["errors"].append("No users found to check")
        return results
    
    try:
        spreadsheet_service = SpreadsheetService()
        raw_data = spreadsheet_service.read_from_google_sheets(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name
        )
        
        if not raw_data:
            results["errors"].append("No data found in spreadsheet")
            return results
        
        weather_data = spreadsheet_service.process_bmkg_data(raw_data)
        
        if not spreadsheet_service.validate_weather_data(weather_data):
            results["errors"].append("Invalid weather data from spreadsheet")
            return results
        
    except Exception as e:
        results["errors"].append(f"Error fetching weather data: {str(e)}")
        return results
    
    recommendation_service = WeatherRecommendationService(db)
    whatsapp_service = WhatsAppService()
    
    for user in users:
        try:
            results["checked_users"] += 1
            
            if not user.phone_e164:
                results["warnings_skipped"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "status": "skipped",
                    "reason": "No phone number"
                })
                continue
            
            if not user.privacy_consent:
                results["warnings_skipped"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "status": "skipped",
                    "reason": "No privacy consent"
                })
                continue
            
            recommendation = recommendation_service.get_personalized_recommendation(
                user=user,
                weather_data=weather_data
            )
            if verbose:
                print("\\n--- Recommendation Debug (full) ---")
                print(json.dumps(recommendation, ensure_ascii=False, indent=2))
                print("--- End Recommendation Debug ---\\n")
            
            risk_level = recommendation.get("risk_level", "low").lower()
            risk_value = risk_levels.get(risk_level, 0)
            
            if risk_value < min_risk_value:
                results["warnings_skipped"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "status": "skipped",
                    "reason": f"Risk level too low ({risk_level} < {min_risk_level})",
                    "risk_level": risk_level
                })
                continue
            
            language = user.language.value if user.language else "id"
            
            phone_number = user.phone_e164.strip() if user.phone_e164 else None
            if not phone_number or not phone_number.startswith('+'):
                results["warnings_skipped"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "status": "skipped",
                    "reason": f"Invalid phone number format: {phone_number}",
                    "risk_level": risk_level
                })
                continue
            
            success = whatsapp_service.send_weather_warning_instant(
                phone_number=phone_number,
                recommendation=recommendation,
                language=language
            )
            
            if success:
                results["warnings_sent"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "phone": user.phone_e164,
                    "status": "sent",
                    "risk_level": risk_level,
                    "language": language
                })
            else:
                results["warnings_skipped"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "email": user.email,
                    "status": "failed",
                    "reason": "WhatsApp send failed",
                    "risk_level": risk_level
                })
                
        except Exception as e:
            results["errors"].append(f"Error processing user {user.id} ({user.email}): {str(e)}")
            results["details"].append({
                "user_id": user.id,
                "email": user.email,
                "status": "error",
                "error": str(e)
            })
    
    return results


def main():
    """Main function untuk run script"""
    parser = argparse.ArgumentParser(
        description="Send WhatsApp warnings untuk users berdasarkan data cuaca terbaru"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="User ID tertentu (default: semua users)"
    )
    parser.add_argument(
        "--min-risk",
        type=str,
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Minimum risk level untuk kirim warning (default: medium)"
    )
    parser.add_argument(
        "--spreadsheet-id",
        type=str,
        help="Google Sheets ID (default: dari config)"
    )
    parser.add_argument(
        "--worksheet",
        type=str,
        default="Sheet1",
        help="Nama worksheet (default: Sheet1)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Tampilkan detail output"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("HAWA WhatsApp Warning Script")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Min Risk Level: {args.min_risk}")
    if args.user_id:
        print(f"User ID: {args.user_id}")
    else:
        print("Users: All users with phone number and privacy consent")
    print("-" * 60)
    
    db = next(get_db())
    
    try:
        results = check_and_send_warnings(
            db=db,
            user_id=args.user_id,
            min_risk_level=args.min_risk,
            spreadsheet_id=args.spreadsheet_id,
            worksheet_name=args.worksheet
        )
        
        print(f"\n✅ Checked Users: {results['checked_users']}")
        print(f"📤 Warnings Sent: {results['warnings_sent']}")
        print(f"⏭️  Warnings Skipped: {results['warnings_skipped']}")
        
        if results['errors']:
            print(f"\n❌ Errors: {len(results['errors'])}")
            for error in results['errors']:
                print(f"   - {error}")
        
        if args.verbose and results['details']:
            print("\n📋 Details:")
            for detail in results['details']:
                status_emoji = {
                    "sent": "✅",
                    "skipped": "⏭️",
                    "failed": "❌",
                    "error": "⚠️"
                }.get(detail.get('status', ''), '❓')
                
                print(f"   {status_emoji} User {detail.get('user_id')} ({detail.get('email')}): {detail.get('status')}")
                if detail.get('reason'):
                    print(f"      Reason: {detail.get('reason')}")
                if detail.get('risk_level'):
                    print(f"      Risk Level: {detail.get('risk_level')}")
        
        print("\n" + "=" * 60)
        
        if results['errors']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

