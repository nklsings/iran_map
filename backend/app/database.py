from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Handle Vercel Postgres URL which starts with postgres:// instead of postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    # Fallback for local dev if not set
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/iran_map"

# Create engine with connection pooling settings for Cloud Run
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,    # Recycle connections after 5 minutes
    pool_size=5,         # Number of connections to keep
    max_overflow=10,     # Allow up to 10 overflow connections
    connect_args={
        "connect_timeout": 10,  # 10 second timeout
    } if "cloudsql" not in DATABASE_URL else {}  # Cloud SQL uses Unix sockets
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
