"""Provision one administrator through an explicit offline database connection."""

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
from app.identity.service import RegistrationUnavailable, provision_admin
from app.models.identity import normalize_display_name, normalize_email

EXPECTED_ALEMBIC_HEAD = "0008"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
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
        database_name = make_url(database_url).database
    except (ValueError, ArgumentError):
        print("ERROR: DATABASE_URL is missing or invalid", file=sys.stderr)
        return 2

    if not database_name or args.confirm_database != database_name:
        print("ERROR: database confirmation does not match DATABASE_URL", file=sys.stderr)
        return 2

    try:
        email = normalize_email(args.email)
        display_name = normalize_display_name(args.display_name)
        password = password_reader("Administrator password: ")
        confirmation = password_reader("Confirm administrator password: ")
        if password != confirmation:
            print("ERROR: passwords do not match", file=sys.stderr)
            return 2
        validate_password(password)
    except ValueError:
        print("ERROR: administrator input is invalid", file=sys.stderr)
        return 2

    try:
        factory = make_session_factory(database_url)
        with factory() as session:
            revision = session.scalar(text("select version_num from alembic_version"))
            if revision != EXPECTED_ALEMBIC_HEAD:
                print(
                    f"ERROR: database must be at Alembic head {EXPECTED_ALEMBIC_HEAD}",
                    file=sys.stderr,
                )
                return 2
            provision_admin(
                session,
                email=email,
                display_name=display_name,
                password=password,
            )
            session.commit()
    except RegistrationUnavailable:
        print("ERROR: administrator account could not be provisioned", file=sys.stderr)
        return 2
    except (SQLAlchemyError, ValueError):
        print("ERROR: database operation failed", file=sys.stderr)
        return 2

    print(f"Provisioned administrator: {email}")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
