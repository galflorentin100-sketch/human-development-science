"""Apply the idempotent SQLite development schema from the repository root or scripts/ folder."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.database import database_from_settings
database_from_settings(Settings.load()).migrate()
print("Database migrated")
