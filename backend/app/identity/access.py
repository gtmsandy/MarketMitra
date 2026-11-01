"""Reusable FastAPI authentication and role dependencies."""

from typing import Annotated

from fastapi import Depends, Request, status

from app.api.dependencies import IdentitySession
from app.identity.service import SessionGrant, resolve_session

SESSION_COOKIE_NAME = "marketmitra_session"


class IdentityAccessError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def get_current_identity(
    request: Request, session: IdentitySession
) -> SessionGrant:
    grant = resolve_session(
        session,
        request.cookies.get(SESSION_COOKIE_NAME),
        rotate_csrf=False,
    )
    session.commit()
    if grant is None:
        raise IdentityAccessError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            "Authentication is required",
        )
    return grant


CurrentIdentity = Annotated[SessionGrant, Depends(get_current_identity)]


def require_admin(identity: CurrentIdentity) -> SessionGrant:
    if identity.user.role != "ADMIN":
        raise IdentityAccessError(
            status.HTTP_403_FORBIDDEN,
            "ADMIN_REQUIRED",
            "Administrator access is required",
        )
    return identity


AdminIdentity = Annotated[SessionGrant, Depends(require_admin)]
