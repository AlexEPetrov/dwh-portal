from typing import Annotated, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.dependencies.security import Principal, create_session_cookie_value, get_principal
from settings.auth import AuthSettings

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthUser(BaseModel):
    id: str
    name: str
    email: str
    roles: List[str] = Field(default_factory=list)


class AuthSessionResponse(BaseModel):
    is_authenticated: bool
    auth_type: str | None = None
    user: AuthUser | None = None


def _cookie_name() -> str:
    return AuthSettings().session_cookie_name


def _cookie_secure() -> bool:
    return AuthSettings().session_secure_cookie


def _cookie_samesite() -> Literal["lax", "strict", "none"]:
    value = AuthSettings().session_samesite.lower()
    if value in {"lax", "strict", "none"}:
        return value  # type: ignore[return-value]
    return "lax"


def _roles_for_username(username: str, settings: AuthSettings) -> list[str]:
    roles: list[str] = []
    if username == settings.local_username:
        roles.append("admin")
    if username == settings.viewer_username:
        roles.append("viewer")
    return roles


@auth_router.post("/login", response_model=AuthSessionResponse)
def login(request: LoginRequest, response: Response) -> AuthSessionResponse:
    settings = AuthSettings()
    valid_credentials = (
        request.username == settings.local_username and request.password == settings.local_password
    ) or (
        request.username == settings.viewer_username
        and request.password == settings.viewer_password
    )
    if not valid_credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    cookie_value = create_session_cookie_value(subject=request.username)
    response.set_cookie(
        key=_cookie_name(),
        value=cookie_value,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return AuthSessionResponse(
        is_authenticated=True,
        auth_type="session",
        user=AuthUser(
            id=request.username,
            name=request.username,
            email=f"{request.username}@local",
            roles=_roles_for_username(request.username, settings),
        ),
    )


@auth_router.post("/logout", response_model=AuthSessionResponse)
def logout(response: Response) -> AuthSessionResponse:
    response.delete_cookie(key=_cookie_name(), path="/")
    return AuthSessionResponse(is_authenticated=False)


@auth_router.get("/session", response_model=AuthSessionResponse)
def get_session(principal: Annotated[Principal, Depends(get_principal)]) -> AuthSessionResponse:
    if principal.auth_type == "api_key":
        return AuthSessionResponse(
            is_authenticated=True,
            auth_type="api_key",
            user=AuthUser(id="service", name="service", email="service@local", roles=["service"]),
        )

    return AuthSessionResponse(
        is_authenticated=True,
        auth_type="session",
        user=AuthUser(
            id=principal.subject,
            name=principal.subject,
            email=f"{principal.subject}@local",
            roles=_roles_for_username(principal.subject, AuthSettings()),
        ),
    )
