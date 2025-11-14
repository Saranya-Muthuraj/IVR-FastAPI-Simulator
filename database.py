# database.py
# (v5) - FINAL Test-Aware Version

import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base  # <-- Use this
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. GET THE DATABASE URL
DATABASE_URL = os.environ.get("DATABASE_URL")
TESTING = os.environ.get("TESTING") == "true" # <--- NEW: Check for test mode

# --- THIS IS THE NEW LOGIC ---
if TESTING:
    # If we are testing, ALWAYS use an in-memory database
    print(">>> RUNNING IN TEST MODE: Using in-memory SQLite database.")
    DATABASE_URL = "sqlite:///:memory:"
elif DATABASE_URL and DATABASE_URL.startswith("postgres"):
    # This is for production (Render)
    print(">>> RUNNING IN PRODUCTION MODE: Using PostgreSQL database.")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # This is for running locally (e.g., uvicorn main:app)
    print(">>> DATABASE_URL not found. Defaulting to local SQLite file 'ivr.db'.")
    DATABASE_URL = "sqlite:///./ivr.db"
# --- END OF NEW LOGIC ---


# 2. CREATE THE ENGINE
# This engine will now be correct for all 3 modes (Test, Prod, Local)
if DATABASE_URL.startswith("sqlite"):
    print(">>> Using SQLite database.")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    print(f">>> Using live PostgreSQL database.")
    engine = create_engine(DATABASE_URL)

# 3. STANDARD SESSION SETUP (This is now correct)
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

# --- UPDATED CallHistory Table ---
# This is the state-tracking table
class CallHistory(Base):
    __tablename__ = "call_history"
    
    # Core Info
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(50), unique=True, index=True)
    caller_number = Column(String(20))
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True) # A call that is not ended will have NULL here
    
    # State Info
    current_menu = Column(String(50), default='main')
    input_buffer = Column(String(100), default='')
    
    # --- THIS IS THE BUG FIX ---
    # Use default=lambda: [] to create a new list for every row
    menu_path = Column(JSON, default=lambda: ["main"])
    inputs = Column(JSON, default=list)
    # --- END BUG FIX ---
    
    # PNR/FF State
    active_pnr = Column(String(10), nullable=True)
    active_ff_number = Column(String(10), nullable=True)
    
    # Booking Wizard State
    booking_flight = Column(String(20), nullable=True)
    booking_name = Column(String(100), nullable=True)
    booking_age = Column(Integer, nullable=True)
    booking_gender = Column(String(20), nullable=True)

# 5. DEPENDENCY
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
