import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL from env for PostgreSQL on Render, fallback to SQLite locally
_raw_url = os.getenv("DATABASE_URL", "").strip()
DATABASE_URL = _raw_url if _raw_url else "sqlite:///./safeflow.db"

# SQLite needs check_same_thread=False; Postgres does not need it
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
