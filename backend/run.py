import os

from dotenv import load_dotenv

load_dotenv()

from backend import create_app
from backend.models import db

app = create_app()

with app.app_context():
    try:
        db.create_all()
    except Exception as exc:
        app.logger.warning(f"Database initialization deferred: {exc}")

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=app.config.get("DEBUG", False))
