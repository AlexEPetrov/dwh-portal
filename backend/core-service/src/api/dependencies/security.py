import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Request

from settings.auth import AuthSettings


@dataclass(frozen=True)
class Principal:
    auth_type: str
    subject: str


def _sign(payload_b64: str, secret: str) -> str:
    signature = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return signature


def create_session_cookie_value(subject: str) -> str:
    settings = AuthSettings()
    payload = {
        "sub": subject,
        "exp": int(time.time()) + settings.session_ttl_seconds,
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{_sign(payload_b64, settings.session_secret_key)}"


def _decode_session_cookie(value: str) -> Optional[dict]:
    settings = AuthSettings()
    try:
        payload_b64, signature = value.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(payload_b64, settings.session_secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(payload_json.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    return payload


def _is_valid_service_key(x_api_key: str) -> bool:
    settings = AuthSettings()
    valid_keys = {key.strip() for key in settings.service_api_keys.split(",") if key.strip()}
    return x_api_key in valid_keys


def verify_x_api_key(
    x_api_key_header: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Проверка machine API key через header x-api-key."""
    x_api_key = x_api_key_header
    if not x_api_key or not _is_valid_service_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid x-api-key")
    return True


def get_principal(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
) -> Principal:
    if x_api_key and _is_valid_service_key(x_api_key):
        return Principal(auth_type="api_key", subject="service")

    settings = AuthSettings()
    app_session = request.cookies.get(settings.session_cookie_name)
    if app_session:
        payload = _decode_session_cookie(app_session)
        if payload:
            return Principal(auth_type="session", subject=payload["sub"])

    raise HTTPException(status_code=401, detail="Unauthorized")
