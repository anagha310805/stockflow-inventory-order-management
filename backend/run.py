import os

from dotenv import load_dotenv

load_dotenv()

from backend import create_app
from backend.models import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=app.config.get("DEBUG", False))