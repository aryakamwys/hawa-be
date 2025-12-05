"""
Protokol Keamanan Data Privasi
Mengikuti best practices untuk perlindungan data pengguna
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
import os
from enum import Enum


class DataClassification(str, Enum):
    """Klasifikasi data berdasarkan sensitivitas"""
    PUBLIC = "public"  # Data yang bisa diakses publik
    INTERNAL = "internal"  # Data internal, tidak sensitif
    CONFIDENTIAL = "confidential"  # Data sensitif (email, phone)
    RESTRICTED = "restricted"  # Data sangat sensitif (health conditions)


class PrivacyProtocol:
    """
    Protokol keamanan data privasi untuk aplikasi HAWA
    """
    
    def __init__(self):
        # Generate encryption key dari environment
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in environment variables. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        self.cipher = Fernet(encryption_key.encode())
    
    def encrypt_sensitive_data(self, data: str, classification: DataClassification) -> str:
        """
        Encrypt data sensitif berdasarkan klasifikasi
        
        Args:
            data: Data yang akan di-encrypt
            classification: Klasifikasi data (confidential atau restricted)
        
        Returns:
            Encrypted data dalam format base64
        """
        if classification not in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]:
            raise ValueError(f"Encryption only allowed for {DataClassification.CONFIDENTIAL} or {DataClassification.RESTRICTED}")
        
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """
        Decrypt data sensitif
        
        Args:
            encrypted_data: Data yang ter-encrypt
        
        Returns:
            Decrypted data
        """
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    def mask_pii(self, data: str, mask_char: str = "*") -> str:
        """
        Mask PII (Personally Identifiable Information) untuk logging/display
        
        Args:
            data: Data yang akan di-mask
            mask_char: Karakter untuk masking
        
        Returns:
            Masked data
        """
        if not data or len(data) < 3:
            return mask_char * len(data) if data else ""
        
        # Mask semua kecuali 2 karakter pertama dan 2 karakter terakhir
        if len(data) <= 4:
            return data[0] + mask_char * (len(data) - 1)
        
        return data[:2] + mask_char * (len(data) - 4) + data[-2:]
    
    def validate_privacy_consent(self, user_consent: bool, consent_date: Optional[datetime]) -> bool:
        """
        Validasi privacy consent dari user
        
        Args:
            user_consent: Boolean consent dari user
            consent_date: Tanggal consent diberikan
        
        Returns:
            True jika consent valid
        """
        if not user_consent:
            return False
        
        if consent_date is None:
            return False
        
        # Consent harus dalam 1 tahun terakhir (bisa di-update)
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        return consent_date >= one_year_ago
    
    def get_data_retention_policy(self, data_classification: DataClassification) -> int:
        """
        Get data retention policy dalam hari berdasarkan klasifikasi
        
        Returns:
            Jumlah hari data boleh disimpan
        """
        policies = {
            DataClassification.PUBLIC: 365 * 5,  # 5 tahun
            DataClassification.INTERNAL: 365 * 3,  # 3 tahun
            DataClassification.CONFIDENTIAL: 365 * 2,  # 2 tahun
            DataClassification.RESTRICTED: 365,  # 1 tahun
        }
        return policies.get(data_classification, 365)
    
    def should_anonymize(self, data_classification: DataClassification, purpose: str) -> bool:
        """
        Tentukan apakah data perlu di-anonymize untuk purpose tertentu
        
        Args:
            data_classification: Klasifikasi data
            purpose: Tujuan penggunaan data (analytics, research, etc.)
        
        Returns:
            True jika perlu anonymize
        """
        # Restricted data selalu perlu anonymize untuk analytics/research
        if data_classification == DataClassification.RESTRICTED:
            return purpose in ["analytics", "research", "aggregation"]
        
        # Confidential data perlu anonymize untuk research
        if data_classification == DataClassification.CONFIDENTIAL:
            return purpose == "research"
        
        return False


# Singleton instance
_privacy_protocol: Optional[PrivacyProtocol] = None

def get_privacy_protocol() -> PrivacyProtocol:
    """Get singleton instance of PrivacyProtocol"""
    global _privacy_protocol
    if _privacy_protocol is None:
        _privacy_protocol = PrivacyProtocol()
    return _privacy_protocol

