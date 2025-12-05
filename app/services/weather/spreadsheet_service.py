"""
Spreadsheet Service untuk membaca data cuaca dari file atau Google Sheets
Support Excel (.xlsx, .xls), CSV, dan Google Sheets
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


class SpreadsheetService:
    """Service untuk membaca dan memproses data cuaca dari spreadsheet atau Google Sheets"""
    
    def read_from_google_sheets(
        self,
        spreadsheet_id: str,
        worksheet_name: str = "Sheet1",
        credentials_path: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Read data dari Google Sheets
        
        Args:
            spreadsheet_id: Google Sheets ID (dari URL)
            worksheet_name: Nama worksheet (default: Sheet1)
            credentials_path: Path ke Google credentials JSON (optional, bisa dari env)
        
        Returns:
            List of dictionaries dengan data cuaca
        """
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError(
                "gspread and google-auth required for Google Sheets. "
                "Install with: pip install gspread google-auth google-auth-oauthlib google-auth-httplib2"
            )
        
        # Get credentials
        if credentials_path:
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
        else:
            # Try to get from environment variable (JSON string)
            creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
            else:
                # Try service account file from env
                service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
                if service_account_file and os.path.exists(service_account_file):
                    creds = Credentials.from_service_account_file(
                        service_account_file,
                        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                    )
                else:
                    raise ValueError(
                        "Google Sheets credentials not found. "
                        "Set GOOGLE_SHEETS_CREDENTIALS_JSON or GOOGLE_SERVICE_ACCOUNT_FILE in .env"
                    )
        
        # Connect to Google Sheets
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)
        
        # Get all records
        records = worksheet.get_all_records()
        return records
    
    def read_weather_data(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Read weather data dari spreadsheet
        
        Args:
            file_path: Path ke file spreadsheet
        
        Returns:
            List of dictionaries dengan data cuaca
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Support multiple formats
        if path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        elif path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Supported: .xlsx, .xls, .csv")
        
        # Convert to list of dicts
        return df.to_dict('records')
    
    def process_bmkg_data(self, data: List[Dict[str, Any]] | Dict[str, Any]) -> Dict[str, Any]:
        """
        Process BMKG/IoT data format ke format yang diharapkan
        Support format dari Google Sheets yang diberikan user
        
        Args:
            data: Raw data dari spreadsheet (list atau single dict)
        
        Returns:
            Processed data dalam format standar
        """
        # Jika list, ambil yang terakhir (data terbaru)
        if isinstance(data, list):
            if not data:
                raise ValueError("Empty data list")
            raw_data = data[-1]  # Latest data
        else:
            raw_data = data
        
        # Map columns sesuai dengan format BMKG/IoT (case-insensitive)
        # Support berbagai variasi nama kolom termasuk format dari Google Sheets
        def get_value(key_variants: List[str], default: Any = None) -> Any:
            for variant in key_variants:
                # Case-insensitive search
                for col in raw_data.keys():
                    if str(col).lower() == variant.lower():
                        value = raw_data[col]
                        # Handle comma as decimal separator (format Indonesia)
                        if isinstance(value, str) and ',' in value:
                            value = value.replace(',', '.')
                        try:
                            # Try to convert to float
                            return float(value) if value else default
                        except (ValueError, TypeError):
                            return value
            return default
        
        # Process numeric values (handle comma as decimal separator)
        def parse_numeric(value: Any, expected_max: float = 1000.0) -> float | None:
            """
            Parse numeric value, handling comma as decimal separator.
            Google Sheets dengan format Indonesia (koma sebagai desimal) 
            sering dibaca sebagai integer oleh gspread.
            
            Args:
                value: Value to parse
                expected_max: Maximum expected value (untuk detect jika perlu dibagi)
            """
            if value is None:
                return None
            if isinstance(value, (int, float)):
                num_value = float(value)
                # Jika nilai terlalu besar, kemungkinan koma dihilangkan
                # Contoh: "56,82" dibaca sebagai 5682, harus jadi 56.82
                if num_value > expected_max:
                    # Coba bagi dengan 100 (untuk 2 decimal places)
                    corrected_100 = num_value / 100.0
                    if corrected_100 <= expected_max:
                        return corrected_100
                    # Jika masih terlalu besar, coba bagi dengan 10 (untuk 1 decimal place)
                    corrected_10 = num_value / 10.0
                    if corrected_10 <= expected_max:
                        return corrected_10
                return num_value
            if isinstance(value, str):
                # Remove any whitespace
                value = value.strip()
                # Handle comma as decimal separator (format Indonesia)
                if ',' in value and '.' not in value:
                    # Comma is decimal separator
                    value = value.replace(',', '.')
                elif ',' in value and '.' in value:
                    # Both comma and dot - assume comma is thousands separator
                    # Remove comma, keep dot as decimal
                    value = value.replace(',', '')
                try:
                    return float(value)
                except ValueError:
                    return None
            return None
        
        processed = {
            # PM2.5 - support berbagai format (expected max ~500 μg/m³)
            'pm25': parse_numeric(get_value([
                'PM2.5 density', 'PM2.5 raw', 'PM2.5', 'pm25', 'PM25', 
                'pm2.5', 'PM 2.5', 'PM2.5 density'
            ]), expected_max=500.0),
            # PM10 (expected max ~1000 μg/m³)
            'pm10': parse_numeric(get_value([
                'PM10 density', 'PM10 raw', 'PM10', 'pm10', 'PM 10'
            ]), expected_max=1000.0),
            # Other pollutants (optional)
            'o3': parse_numeric(get_value(['O3', 'o3', 'Ozone', 'ozone']), expected_max=500.0),
            'no2': parse_numeric(get_value(['NO2', 'no2', 'NO 2', 'Nitrogen Dioxide']), expected_max=500.0),
            'so2': parse_numeric(get_value(['SO2', 'so2', 'SO 2', 'Sulfur Dioxide']), expected_max=500.0),
            'co': parse_numeric(get_value(['CO', 'co', 'Carbon Monoxide']), expected_max=50.0),
            # Weather data
            'temperature': parse_numeric(get_value([
                'Temperature', 'temperature', 'Temp', 'temp', 'Suhu', 'suhu'
            ]), expected_max=50.0),  # Max temperature ~50°C
            'humidity': parse_numeric(get_value([
                'Humidity', 'humidity', 'Hum', 'hum', 'Kelembaban', 'kelembaban'
            ]), expected_max=100.0),  # Max humidity 100%
            'pressure': parse_numeric(get_value([
                'Pressure', 'pressure', 'Tekanan', 'tekanan'
            ])),
            # Metadata
            'location': get_value([
                'Location', 'location', 'Lokasi', 'lokasi', 'Kota', 'kota', 
                'Device ID', 'device_id'
            ], 'Bandung'),
            'timestamp': get_value([
                'Timestamp', 'timestamp', 'Date', 'date', 'Tanggal', 'tanggal', 
                'Waktu', 'waktu', 'Time', 'time'
            ]),
            'air_quality_level': get_value([
                'Air quality level', 'air_quality_level', 'Air Quality Level',
                'Status', 'status', 'Kualitas Udara', 'kualitas_udara'
            ]),
            'device_id': get_value(['Device ID', 'device_id', 'Device', 'device']),
        }
        
        return processed
    
    def validate_weather_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate weather data memiliki minimal required fields
        
        Args:
            data: Weather data dictionary
        
        Returns:
            True jika valid
        """
        required_fields = ['pm25', 'pm10']
        return all(data.get(field) is not None for field in required_fields)

