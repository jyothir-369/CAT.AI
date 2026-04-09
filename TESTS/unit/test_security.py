"""
Unit tests for core security utilities.
No DB, no HTTP.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

import pytest
from datetime import timedelta


class TestPasswordHashing:

    def test_hash_and_verify_roundtrip(self):
        from core.security import hash_password, verify_password
        hashed = hash_password("supersecret123")
        assert verify_password("supersecret123", hashed) is True

    def test_wrong_password_fails(self):
        from core.security import hash_password, verify_password
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hashes_are_unique(self):
        from core.security import hash_password
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts differ

    def test_hash_is_not_plaintext(self):
        from core.security import hash_password
        hashed = hash_password("plaintext")
        assert "plaintext" not in hashed


class TestJWT:

    def test_access_token_roundtrip(self):
        from core.security import create_access_token, decode_token
        token = create_access_token({"sub": "user-123", "email": "a@b.com"})
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        from core.security import create_refresh_token, decode_token
        token = create_refresh_token({"sub": "user-456"})
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_invalid_token_raises_value_error(self):
        from core.security import decode_token
        with pytest.raises(ValueError):
            decode_token("not.a.valid.token")

    def test_tampered_token_raises_value_error(self):
        from core.security import create_access_token, decode_token
        token = create_access_token({"sub": "user-789"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            decode_token(tampered)

    def test_signed_url_token_has_correct_type(self):
        from core.security import create_signed_url_token, decode_token
        token = create_signed_url_token({"run_id": "abc", "action": "approve"})
        payload = decode_token(token)
        assert payload["type"] == "signed_url"
        assert payload["run_id"] == "abc"


class TestAPIKey:

    def test_generate_returns_raw_and_hash(self):
        from core.security import generate_api_key
        raw, hashed = generate_api_key()
        assert raw.startswith("cat_")
        assert len(raw) > 20
        assert len(hashed) == 64  # sha256 hex

    def test_hash_is_deterministic(self):
        from core.security import hash_api_key
        assert hash_api_key("test_key") == hash_api_key("test_key")

    def test_different_keys_different_hashes(self):
        from core.security import hash_api_key
        assert hash_api_key("key_a") != hash_api_key("key_b")

    def test_raw_key_matches_hash(self):
        from core.security import generate_api_key, hash_api_key
        raw, stored_hash = generate_api_key()
        assert hash_api_key(raw) == stored_hash


class TestCredentialEncryption:

    def test_encrypt_decrypt_roundtrip(self):
        from core.security import encrypt_credentials, decrypt_credentials
        original = '{"access_token": "abc123", "refresh_token": "xyz789"}'
        encrypted = encrypt_credentials(original)
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == original

    def test_encrypted_is_not_plaintext(self):
        from core.security import encrypt_credentials
        secret = "my_secret_token"
        encrypted = encrypt_credentials(secret)
        assert secret not in encrypted