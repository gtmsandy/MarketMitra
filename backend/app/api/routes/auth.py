"""Public registration and login routes for opaque cookie sessions."""

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import IdentitySession
from app.core.config import get_application_environment
from app.identity.service import (
    RegistrationUnavailable,
    SessionGrant,
    authenticate_identity,
    register_identity,
)
from app.models.identity import (
    AuthSessionResponse,
    ErrorResponse,
    IdentityUserResponse,
    LoginRequest,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_COOKIE_NAME = "marketmitra_session"
_COOKIE_MAX_AGE_SECONDS = 12 * 60 * 60


def _response(grant: SessionGrant) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=IdentityUserResponse(
            id=grant.user.id,
            email=grant.user.email,
            display_name=grant.user.display_name,
            role=grant.user.role,
            created_at=grant.user.created_at,
        ),
        csrf_token=grant.csrf_token,
        expires_at=grant.session.absolute_expires_at,
    )


def _set_session_cookie(response: Response, grant: SessionGrant) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=grant.session_token,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=get_application_environment() == "production",
        samesite="lax",
        path="/api/v1",
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error={"code": code, "message": message})
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@router.post(
    "/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
def register(
    request: RegisterRequest, response: Response, session: IdentitySession
) -> AuthSessionResponse | JSONResponse:
    try:
        grant = register_identity(
            session,
            email=request.email,
            display_name=request.display_name,
            password=request.password,
        )
        session.commit()
    except RegistrationUnavailable:
        session.rollback()
        return _error(
            status.HTTP_409_CONFLICT,
            "REGISTRATION_UNAVAILABLE",
            "Registration could not be completed",
        )

    _set_session_cookie(response, grant)
    return _response(grant)


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    responses={401: {"model": ErrorResponse}},
)
def login(
    request: LoginRequest, response: Response, session: IdentitySession
) -> AuthSessionResponse | JSONResponse:
    grant = authenticate_identity(
        session, email=request.email, password=request.password
    )
    session.commit()
    if grant is None:
        return _error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_FAILED",
            "Email or password is incorrect",
        )

    _set_session_cookie(response, grant)
    return _response(grant)
