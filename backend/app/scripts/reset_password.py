"""Reset one local identity password through an explicit offline connection."""

import argparse
from collections.abc import Callable, Sequence
import getpass
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from app.core.config import get_database_url
from app.db.base import make_session_factory
from app.identity.security import validate_password
from app.identity.service import (
    IdentityMaintenanceUnavailable,
    reset_identity_password,
)
from app.models.identity import normalize_email

EXPECTED_ALEMBIC_HEAD = "0010"
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--confirm-email", required=True)
    parser.add_argument(
        "--confirm-database",
        required=True,
        help="Exact database name from DATABASE_URL",
    )
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    password_reader: Callable[[str], str] = getpass.getpass,
) -> int:
    args = _parser().parse_args(argv)
    try:
        database_url = get_database_url()
        parsed_url = make_url(database_url)
        database_name = parsed_url.database
    except (ValueError, ArgumentError):
        print("ERROR: DATABASE_URL is missing or invalid", file=sys.stderr)
        return 2

    if parsed_url.host not in LOCAL_DATABASE_HOSTS:
        print("ERROR: password maintenance requires a local database", file=sys.stderr)
        return 2
    if not database_name or args.confirm_database != database_name:
        print("ERROR: database confirmation does not match DATABASE_URL", file=sys.stderr)
        return 2
    if args.confirm_email != args.email:
        print("ERROR: email confirmation does not match", file=sys.stderr)
        return 2

    try:
        email = normalize_email(args.email)
        password = password_reader("New password: ")
        confirmation = password_reader("Confirm new password: ")
        if password != confirmation:
            print("ERROR: passwords do not match", file=sys.stderr)
            return 2
        validate_password(password)
    except ValueError:
        print("ERROR: password maintenance input is invalid", file=sys.stderr)
        return 2

    try:
        factory = make_session_factory(database_url)
        with factory() as session:
            database, role, revision = session.execute(
                text(
                    "select current_database(), current_user, "
                    "(select version_num from alembic_version)"
                )
            ).one()
            if database != database_name or role != parsed_url.username:
                print("ERROR: connected database identity does not match", file=sys.stderr)
                return 2
            if revision != EXPECTED_ALEMBIC_HEAD:
                print(
                    f"ERROR: database must be at Alembic head {EXPECTED_ALEMBIC_HEAD}",
                    file=sys.stderr,
                )
                return 2
            _, revoked_count = reset_identity_password(
                session,
                email=email,
                password=password,
            )
            session.commit()
    except IdentityMaintenanceUnavailable:
        print("ERROR: identity could not be maintained", file=sys.stderr)
        return 2
    except (SQLAlchemyError, ValueError):
        print("ERROR: database operation failed", file=sys.stderr)
        return 2

    print(
        f"Reset password for {email}; revoked {revoked_count} session(s); "
        f"database: {database}; role: {role}"
    )
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
