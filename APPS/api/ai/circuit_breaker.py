import time
from enum import Enum

# In production: replace with aioredis. Using a simple in-process dict as placeholder.
_store: dict[str, dict] = {}


class CircuitState(str, Enum):
    CLOSED = "closed"       # healthy — requests pass through
    OPEN = "open"           # unhealthy — requests are blocked
    HALF_OPEN = "half_open" # testing recovery


class CircuitBreaker:
    """
    Per-provider circuit breaker.
    Opens after ERROR_THRESHOLD failures within WINDOW_SECONDS.
    Retries after RECOVERY_SECONDS (half-open probe).
    """
    ERROR_THRESHOLD = 5
    WINDOW_SECONDS = 60
    RECOVERY_SECONDS = 30

    def __init__(self, provider: str):
        self.provider = provider
        if provider not in _store:
            _store[provider] = {
                "state": CircuitState.CLOSED,
                "errors": [],
                "opened_at": None,
            }

    @property
    def _data(self) -> dict:
        return _store[self.provider]

    def get_state(self) -> CircuitState:
        data = self._data
        if data["state"] == CircuitState.OPEN:
            # Check if recovery window has elapsed → move to half-open
            if data["opened_at"] and time.time() - data["opened_at"] >= self.RECOVERY_SECONDS:
                data["state"] = CircuitState.HALF_OPEN
        return data["state"]

    def is_available(self) -> bool:
        return self.get_state() != CircuitState.OPEN

    def record_success(self) -> None:
        data = self._data
        data["state"] = CircuitState.CLOSED
        data["errors"] = []
        data["opened_at"] = None

    def record_failure(self) -> None:
        data = self._data
        now = time.time()
        # Purge errors outside the window
        data["errors"] = [t for t in data["errors"] if now - t < self.WINDOW_SECONDS]
        data["errors"].append(now)

        if len(data["errors"]) >= self.ERROR_THRESHOLD:
            data["state"] = CircuitState.OPEN
            data["opened_at"] = now

    def __repr__(self) -> str:
        return f"CircuitBreaker(provider={self.provider}, state={self.get_state()})"


# Registry — one breaker per provider, reused across requests
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(provider: str) -> CircuitBreaker:
    if provider not in _breakers:
        _breakers[provider] = CircuitBreaker(provider)
    return _breakers[provider]