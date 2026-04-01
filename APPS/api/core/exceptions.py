from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


# ── Auth ──────────────────────────────────────────────────────────────────────

class AuthError(AppError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR")


class InvalidTokenError(AuthError):
    def __init__(self):
        super().__init__("Invalid or expired token")


class InsufficientPermissionsError(AuthError):
    def __init__(self):
        super().__init__("Insufficient permissions")


# ── Domain ────────────────────────────────────────────────────────────────────

class NotFoundError(AppError):
    def __init__(self, resource: str, id: str | None = None):
        msg = f"{resource} not found" if not id else f"{resource} '{id}' not found"
        super().__init__(msg, "NOT_FOUND")


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class WorkspaceIsolationError(AppError):
    def __init__(self):
        super().__init__("Cross-workspace access denied", "ISOLATION_ERROR")


# ── Billing ───────────────────────────────────────────────────────────────────

class PlanLimitExceededError(AppError):
    def __init__(self, limit_type: str):
        super().__init__(f"Plan limit exceeded: {limit_type}", "PLAN_LIMIT_EXCEEDED")


class BillingError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "BILLING_ERROR")


# ── AI ────────────────────────────────────────────────────────────────────────

class ProviderError(AppError):
    def __init__(self, provider: str, message: str):
        super().__init__(f"Provider '{provider}' error: {message}", "PROVIDER_ERROR")


class AllProvidersFailedError(AppError):
    def __init__(self):
        super().__init__("All AI providers are unavailable", "ALL_PROVIDERS_FAILED")


# ── HTTP exception mapper ─────────────────────────────────────────────────────

def to_http_exception(err: AppError) -> HTTPException:
    mapping = {
        "AUTH_ERROR":          status.HTTP_401_UNAUTHORIZED,
        "NOT_FOUND":           status.HTTP_404_NOT_FOUND,
        "CONFLICT":            status.HTTP_409_CONFLICT,
        "VALIDATION_ERROR":    status.HTTP_422_UNPROCESSABLE_ENTITY,
        "ISOLATION_ERROR":     status.HTTP_403_FORBIDDEN,
        "PLAN_LIMIT_EXCEEDED": status.HTTP_402_PAYMENT_REQUIRED,
        "BILLING_ERROR":       status.HTTP_400_BAD_REQUEST,
        "PROVIDER_ERROR":      status.HTTP_502_BAD_GATEWAY,
        "ALL_PROVIDERS_FAILED":status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    status_code = mapping.get(err.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    return HTTPException(status_code=status_code, detail={"error": err.code, "message": err.message})