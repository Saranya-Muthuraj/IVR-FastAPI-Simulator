# database.py
# (v3) - The Corrected Production Version

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import Column
from sqlalchemy.types import String, Integer, DateTime, JSON

# 1. GET THE DATABASE URL
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- THIS IS THE FIX ---
# Check if the URL is for PostgreSQL (it might start with "postgres://" or "postgresql://")
if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    # It's a Postgres URL.
    # Make sure it uses the "postgresql://" protocol that SQLAlchemy requires.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # If it's already "postgresql://", this code does nothing, which is correct.
else:
    # It's either empty or not a Postgres URL, so use SQLite for local dev
    print(">>> DATABASE_URL not found or invalid. Defaulting to local SQLite file.")
    DATABASE_URL = "sqlite:///./ivr.db"
# --- END OF FIX ---


# 2. CREATE THE ENGINE
if DATABASE_URL.startswith("sqlite"):
    print(">>> Using local SQLite database.")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # This will now correctly print that it's using Postgres
    print(f">>> Using live PostgreSQL database.")
    engine = create_engine(DATABASE_URL)

# 3. STANDARD SESSION SETUP
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. DATABASE MODELS (Your tables)
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
# (This is no longer needed here, your main app does it on startup)
# Base.metadata.create_all(bind=engine) 

# 6. DEPENDENCY (Unchanged)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
