from dotenv import load_dotenv
import os
from pathlib import Path


env_path = Path('.') / 'app' / '.env'
load_dotenv()

PG_USER = os.environ.get("PG_USER", "myuser")
DB_HOST = os.environ.get("DB_HOST", "localhost")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "1111")
PG_DB = os.environ.get("PG_DB", "mydb")
DB_PORT = os.environ.get("DB_PORT", 5432)
DOCKER_PORT = os.environ.get("DOCKER_PORT", 5432)

SECRET_AUTH = os.environ.get("SECRET_AUTH")
PHOTO_DIR = os.path.join(os.getcwd(), "uploads", "photos")

if not SECRET_AUTH:
    raise ValueError("SECRET_AUTH is not defined in the environment variables.")
