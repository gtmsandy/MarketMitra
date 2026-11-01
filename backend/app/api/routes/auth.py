"""Public registration and login routes for opaque cookie sessions."""

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import IdentitySession
from app.core.config import get_application_environment, get_cors_origins
from app.identity.service import (
    RegistrationUnavailable,
    SessionGrant,
    authenticate_identity,
    csrf_matches,
    logout_all_sessions,
    logout_session,
    register_identity,
    resolve_session,
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


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_COOKIE_NAME,
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


@router.get(
    "/session",
    response_model=AuthSessionResponse,
    responses={401: {"model": ErrorResponse}},
)
def current_session(
    request: Request, response: Response, session: IdentitySession
) -> AuthSessionResponse | JSONResponse:
    grant = resolve_session(
        session,
        request.cookies.get(_COOKIE_NAME),
        rotate_csrf=True,
    )
    session.commit()
    if grant is None:
        error = _error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Authentication is required",
        )
        _clear_session_cookie(error)
        return error
    response.headers["Cache-Control"] = "no-store"
    return _response(grant)


def _authenticated_mutation(
    request: Request, session: IdentitySession
) -> SessionGrant | JSONResponse:
    grant = resolve_session(
        session,
        request.cookies.get(_COOKIE_NAME),
        rotate_csrf=False,
    )
    if grant is None:
        session.commit()
        return _error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Authentication is required",
        )

    origin = request.headers.get("origin")
    csrf_token = request.headers.get("x-csrf-token")
    if origin not in get_cors_origins() or not csrf_matches(grant.session, csrf_token):
        session.rollback()
        return _error(
            status.HTTP_403_FORBIDDEN,
            "CSRF_VALIDATION_FAILED",
            "Request could not be verified",
        )
    return grant


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def logout(request: Request, session: IdentitySession) -> Response:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        if grant.status_code == status.HTTP_401_UNAUTHORIZED:
            _clear_session_cookie(grant)
        return grant
    logout_session(session, grant)
    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(response)
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def logout_all(request: Request, session: IdentitySession) -> Response:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        if grant.status_code == status.HTTP_401_UNAUTHORIZED:
            _clear_session_cookie(grant)
        return grant
    logout_all_sessions(session, grant)
    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(response)
    return response
