# database.py
# (v2) - Production-Ready Version

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import Column
from sqlalchemy.types import String, Integer, DateTime, JSON

# 1. GET THE DATABASE URL
#    - It looks for a "DATABASE_URL" environment variable (for production on Render)
#    - If it doesn't find one, it uses a local "ivr.db" file (for development)
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Fix for SQLAlchemy: "postgres://" needs to be "postgresql://"
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # Use SQLite locally
    DATABASE_URL = "sqlite:///./ivr.db"

# 2. CREATE THE ENGINE
#    - For SQLite, we need "check_same_thread"
#    - For PostgreSQL (production), we don't.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# 3. STANDARD SESSION SETUP
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. DATABASE MODELS (Your tables)
#    (These are the same as before)
class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    pnr_key = Column(String(6), unique=True, index=True, nullable=False)
    pnr_display = Column(String(8))
    flight = Column(String(10))
    status = Column(String(20))
    route = Column(String(100))
    time = Column(String(50))
    seats_available = Column(Integer)
    passenger_name = Column(String(100))
    passenger_age = Column(Integer)
    passenger_gender = Column(String(10))

class FrequentFlyer(Base):
    __tablename__ = "frequent_flyers"
    id = Column(Integer, primary_key=True, index=True)
    ff_number = Column(String(9), unique=True, index=True, nullable=False)
    pin = Column(String(4), nullable=False)
    name = Column(String(100))
    points = Column(Integer)

class CallHistory(Base):
    __tablename__ = "call_history"
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(50), unique=True, index=True)
    caller_number = Column(String(20))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    menu_path = Column(JSON)
    inputs = Column(JSON)

# 5. CREATE TABLES
#    This line will create the tables when the app first runs
Base.metadata.create_all(bind=engine)

# 6. DEPENDENCY (Unchanged)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()