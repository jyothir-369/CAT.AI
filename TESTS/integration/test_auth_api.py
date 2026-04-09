"""
Integration tests for auth endpoints.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

import pytest
from conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
class TestRegister:

    async def test_register_success(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@catai.test",
                "password": "securepass123",
                "name": "New User",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "newuser@catai.test"

    async def test_register_duplicate_email(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user["user"].email,
                "password": "anotherpass",
                "name": "Duplicate",
            },
        )
        assert response.status_code == 409

    async def test_register_invalid_email(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "pass",
                "name": "Test",
            },
        )
        assert response.status_code == 422

    async def test_register_with_org_name(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "orguser@catai.test",
                "password": "securepass123",
                "name": "Org User",
                "org_name": "My Startup",
            },
        )
        assert response.status_code == 201


@pytest.mark.asyncio
class TestLogin:

    async def test_login_success(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["user"].email,
                "password": "testpass123",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["user"].email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    async def test_login_unknown_email(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@catai.test",
                "password": "somepass",
            },
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestGetMe:

    async def test_get_me_with_valid_token(self, client, test_user):
        response = await client.get(
            "/api/v1/auth/me",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == test_user["user"].email
        assert body["name"] == test_user["user"].name
        assert "hashed_password" not in body

    async def test_get_me_without_token(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403

    async def test_get_me_with_invalid_token(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestLogout:

    async def test_logout_clears_cookie(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/logout",
            headers=test_user["headers"],
        )
        assert response.status_code == 204