# database.py
# (v4) - Production-Ready Version with State in CallHistory

import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. GET THE DATABASE URL
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- THIS IS THE FIX for postgres:// vs postgresql:// ---
if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    print(">>> DATABASE_URL not found or invalid. Defaulting to local SQLite file.")
    DATABASE_URL = "sqlite:///./ivr.db"
# --- END OF FIX ---


# 2. CREATE THE ENGINE
if DATABASE_URL.startswith("sqlite"):
    print(">>> Using local SQLite database.")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
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

# --- UPDATED CallHistory Table ---
# We add all the fields that were previously in the in-memory `active_calls` dict
class CallHistory(Base):
    __tablename__ = "call_history"
    
    # Core Info
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(50), unique=True, index=True)
    caller_number = Column(String(20))
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True) # A call that is not ended will have NULL here
    
    # State Info
    current_menu = Column(String(50), default='main')
    input_buffer = Column(String(100), default='')
    menu_path = Column(JSON, default=[])
    inputs = Column(JSON, default=[])
    
    # PNR/FF State
    active_pnr = Column(String(10), nullable=True)
    active_ff_number = Column(String(10), nullable=True)
    
    # Booking Wizard State
    booking_flight = Column(String(20), nullable=True)
    booking_name = Column(String(100), nullable=True)
    booking_age = Column(Integer, nullable=True)
    booking_gender = Column(String(20), nullable=True)

# 5. DEPENDENCY (Unchanged)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
