"""
Integrations routes — OAuth initiation · callback · list · delete
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_user, get_current_org, get_db
from core.security import encrypt_credentials, decrypt_credentials
from db.models.user import User, Organization
from db.models.integrations import Integration

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Supported providers and their OAuth config stubs
SUPPORTED_PROVIDERS = {
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "scopes": ["chat:write", "channels:read"],
    },
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scopes": ["https://www.googleapis.com/auth/gmail.send"],
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "scopes": [],
    },
    "google_sheets": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
    },
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    provider: str
    redirect_uri: Optional[str] = None


class ConnectResponse(BaseModel):
    auth_url: str
    provider: str
    state: str


class OAuthCallbackRequest(BaseModel):
    provider: str
    code: str
    state: str
    redirect_uri: Optional[str] = None


class IntegrationOut(BaseModel):
    id: str
    provider: str
    scopes: list
    expires_at: Optional[datetime]
    created_at: datetime


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration)
        .where(Integration.org_id == current_org.id)
        .order_by(Integration.created_at.desc())
    )
    integrations = result.scalars().all()
    return [_integration_out(i) for i in integrations]


@router.post("/connect", response_model=ConnectResponse)
async def initiate_oauth(
    body: ConnectRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the OAuth authorization URL for the user to redirect to.
    State encodes org_id + user_id + provider for the callback.
    """
    provider = body.provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider}. Supported: {list(SUPPORTED_PROVIDERS.keys())}",
        )

    import base64, json as _json
    state_data = _json.dumps({
        "org_id": current_org.id,
        "user_id": current_user.id,
        "provider": provider,
    })
    state = base64.urlsafe_b64encode(state_data.encode()).decode()

    config = SUPPORTED_PROVIDERS[provider]
    scopes = " ".join(config["scopes"])
    redirect_uri = body.redirect_uri or f"{settings.frontend_url}/integrations/callback"

    # Build auth URL (simplified — real implementation adds client_id, etc.)
    auth_url = (
        f"{config['auth_url']}?"
        f"scope={scopes}&"
        f"state={state}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code"
    )

    return ConnectResponse(auth_url=auth_url, provider=provider, state=state)


@router.post("/callback", response_model=IntegrationOut, status_code=201)
async def oauth_callback(
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Receives the OAuth code from the frontend after redirect.
    Exchanges code for tokens and stores encrypted credentials.
    """
    import base64, json as _json

    try:
        state_data = _json.loads(base64.urlsafe_b64decode(body.state).decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    org_id = state_data.get("org_id")
    user_id = state_data.get("user_id")
    provider = state_data.get("provider", body.provider.lower())

    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # In production: exchange `body.code` for access/refresh tokens via provider's token endpoint
    # For MVP, store the code itself as a placeholder
    mock_credentials = _json.dumps({
        "access_token": f"mock_token_for_{provider}",
        "code": body.code,
        "provider": provider,
    })

    # Upsert integration record
    result = await db.execute(
        select(Integration).where(
            Integration.org_id == org_id,
            Integration.provider == provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_credentials = encrypt_credentials(mock_credentials)
        existing.scopes = SUPPORTED_PROVIDERS[provider]["scopes"]
        integration = existing
    else:
        integration = Integration(
            org_id=org_id,
            user_id=user_id,
            provider=provider,
            encrypted_credentials=encrypt_credentials(mock_credentials),
            scopes=SUPPORTED_PROVIDERS[provider]["scopes"],
        )
        db.add(integration)
        await db.flush()

    return _integration_out(integration)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.org_id == current_org.id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    await db.delete(integration)
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _integration_out(i: Integration) -> IntegrationOut:
    return IntegrationOut(
        id=i.id,
        provider=i.provider,
        scopes=i.scopes or [],
        expires_at=i.expires_at,
        created_at=i.created_at,
    )