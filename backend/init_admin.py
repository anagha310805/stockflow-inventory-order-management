import getpass
import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from backend import create_app
from backend.models import db, User


def init_admin(email=None, password=None, name=None, phone=None, app=None):
    """
    Explicitly runnable, idempotent script to initialize the primary Administrator account.
    Reads from arguments, environment variables, or prompts interactively.
    Does NOT overwrite or reset existing accounts.
    """
    target_app = app or create_app()
    with target_app.app_context():
        # Display safe, masked database connection info
        safe_url = db.engine.url.render_as_string(hide_password=True)
        is_cloud = "127.0.0.1" not in safe_url and "localhost" not in safe_url
        print(f"Connected to database: {safe_url}")
        if is_cloud:
            print(">> Target: Remote Cloud Production Database (TiDB Cloud)")
        else:
            print(">> Target: Local Database")

        # Test connection
        try:
            with db.engine.connect() as conn:
                pass
        except Exception as e:
            print(f"ERROR: Could not establish connection to the database: {e}")
            sys.exit(1)

        # Ensure schema tables exist safely
        db.create_all()

        target_email = email or os.getenv("ADMIN_EMAIL") or os.getenv("INITIAL_ADMIN_EMAIL") or os.getenv("DEMO_ADMIN_EMAIL")
        target_password = password or os.getenv("ADMIN_PASSWORD") or os.getenv("INITIAL_ADMIN_PASSWORD")
        target_name = name or os.getenv("ADMIN_NAME", "StockFlow Administrator")
        target_phone = phone or os.getenv("ADMIN_PHONE", "+91 98765 00001")

        # Fallback to interactive input if running in terminal and missing
        if not target_email and sys.stdin and sys.stdin.isatty():
            prompt_email = input("Enter Administrator email [admin@stockflow.com]: ").strip()
            target_email = prompt_email if prompt_email else "admin@stockflow.com"

        if not target_password and sys.stdin and sys.stdin.isatty():
            target_password = getpass.getpass("Enter Administrator password (min 8 characters): ").strip()

        if not target_email:
            print("ERROR: Administrator email is missing. Set ADMIN_EMAIL or pass as first argument.", file=sys.stderr)
            sys.exit(1)

        if not target_password:
            print("ERROR: Administrator password is missing. Set ADMIN_PASSWORD or pass as second argument.", file=sys.stderr)
            sys.exit(1)

        target_email = target_email.strip().lower()
        target_password = str(target_password).strip()

        if len(target_password) < 8:
            print("ERROR: Administrator password must be at least 8 characters long.", file=sys.stderr)
            sys.exit(1)

        existing = User.query.filter_by(email=target_email).first()
        if existing:
            print(f"Administrator account '{target_email}' already exists (ID: {existing.id}, Role: {existing.role}, Active: {existing.active}). Account was unchanged.")
            return existing

        admin_user = User(
            name=target_name.strip(),
            email=target_email,
            phone=target_phone.strip(),
            role="admin",
            active=True,
            password_hash=generate_password_hash(target_password)
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"SUCCESS: Administrator account '{target_email}' created successfully (ID: {admin_user.id}, Role: admin).")
        return admin_user


if __name__ == "__main__":
    arg_email = sys.argv[1] if len(sys.argv) > 1 else None
    arg_password = sys.argv[2] if len(sys.argv) > 2 else None
    init_admin(email=arg_email, password=arg_password)
