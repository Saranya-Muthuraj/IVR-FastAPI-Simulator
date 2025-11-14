# test_ivr_simulator.py
# (v5 - THE CORRECTED SQLITE-IN-MEMORY LOGIC)

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool # <--- NEW IMPORT

# --- CRITICAL: Set TESTING env var BEFORE importing the app ---
os.environ["TESTING"] = "true" 

# --- Import from your project files ---
from ivr_simulator_backend import app, MOCK_PNR_DB, MOCK_FF_DB
from database import Base, get_db, Booking, FrequentFlyer, CallHistory

# =================================================================
# ##### !!!!! THIS IS THE CORRECT, ISOLATED TEST DB SETUP !!!!! #####
# =================================================================

# 1. Use a Static Connection Pool for the in-memory database
# This ensures all tests use the SAME connection, so the tables are not lost.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Create tables ONCE on this engine
Base.metadata.create_all(bind=engine)

# 3. Define a function to OVERRIDE the app's 'get_db' dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# 4. TELL THE APP to use our test database instead of its own
app.dependency_overrides[get_db] = override_get_db

# =================================================================
# --- Pytest Fixture ---
# This fixture populates the database that was just created
@pytest.fixture(scope="session", autouse=True)
def populate_db():
    db = TestingSessionLocal()
    
    print("\n--- Populating in-memory test database... ---")
    try:
        # Manually populate Bookings
        if db.query(Booking).count() == 0:
            print("Populating test Bookings (PNR) table...")
            for key, data in MOCK_PNR_DB.items():
                db_booking = Booking(pnr_key=key, **data)
                db.add(db_booking)
            db.commit()
        
        # Manually populate FrequentFlyer
        if db.query(FrequentFlyer).count() == 0:
            print("Populating test FrequentFlyer table...")
            for key, data in MOCK_FF_DB.items():
                db_ff = FrequentFlyer(ff_number=key, **data)
                db.add(db_ff)
            db.commit()
        print("--- Test database population complete. ---")
    except Exception as e:
        print(f"Error populating test DB: {e}")
        db.rollback()
    finally:
        db.close()
    
    # This fixture doesn't need to yield anything
    # It just runs once and sets up the data.


# --- Fixture to create the client for each test ---
@pytest.fixture(scope="function")
def client():
    # We create a new TestClient for each test
    # It will use the override_get_db and the populated DB
    with TestClient(app) as c:
        yield c
        
    # After each test, we clear the CallHistory table
    # so tests don't affect each other
    db = TestingSessionLocal()
    db.query(CallHistory).delete()
    db.commit()
    db.close()


### 🌎 BASIC TESTS ###

def test_health_check(client):
    """Test the root endpoint (/)"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "IVR Simulator Running"
    assert data["database_status"] == "Connected" # <--- This will pass
    assert data["total_bookings_in_db"] > 0
    assert data["total_ff_accounts_in_db"] > 0
    assert data["total_completed_calls_in_db"] == 0

def test_start_call(client):
    """Test the /ivr/start endpoint"""
    response = client.post(
        "/ivr/start",
        json={"caller_number": "+15551234567"}
    )
    assert response.status_code == 200 # <--- This will pass
    data = response.json()
    assert data["status"] == "connected"
    assert "call_id" in data
    
    # Check that the call is now in the DB
    health_resp = client.get("/")
    assert health_resp.json()["live_active_calls_in_db"] == 1

### 📞 DTMF (KEYPAD) FLOW TESTS ###

def test_dtmf_flow_get_pnr_status(client):
    """Test a full flow: Start -> Press 1 -> Enter PNR -> Get Status"""
    
    # 1. Start the call
    start_resp = client.post("/ivr/start", json={"caller_number": "+1Test"})
    call_id = start_resp.json()["call_id"] # <--- This will pass
    
    # 2. Press '1' for Flight Status
    dtmf_resp_1 = client.post(
        "/ivr/dtmf",
        json={"call_id": call_id, "digit": "1", "current_menu": "main"}
    )
    assert dtmf_resp_1.status_code == 200
    data_1 = dtmf_resp_1.json()
    assert data_1["current_menu"] == "flight_status_pnr"
    assert data_1["message"] == "You selected Flight Status."
    
    # 3. Enter PNR 241234 (R. Kumar) - one by one
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "2", "current_menu": "flight_status_pnr"})
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "4", "current_menu": "flight_status_pnr"})
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "1", "current_menu": "flight_status_pnr"})
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "2", "current_menu": "flight_status_pnr"})
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "3", "current_menu": "flight_status_pnr"})
    client.post("/ivr/dtmf", json={"call_id": call_id, "digit": "4", "current_menu": "flight_status_pnr"})
    
    # 4. Press '#' to submit
    dtmf_resp_hash = client.post(
        "/ivr/dtmf",
        json={"call_id": call_id, "digit": "#", "current_menu": "flight_status_pnr"}
    )
    assert dtmf_resp_hash.status_code == 200
    data_hash = dtmf_resp_hash.json()
    
    # 5. Check the final result
    assert data_hash["status"] == "pnr_found"
    assert data_hash["call_action"] == "hangup"
    assert "Passenger: R. Kumar" in data_hash["message"]

### 🗣️ NLU (VOICE) FLOW TESTS ###

def test_nlu_flow_get_pnr_status(client):
    """Test a full flow: Start -> Say "Flight Status" -> Say PNR -> Get Status"""
    
    # 1. Start the call
    start_resp = client.post("/ivr/start", json={"caller_number": "+1VoiceTest"})
    call_id = start_resp.json()["call_id"] # <--- This will pass
    
    # 2. Say "Flight Status"
    voice_resp_1 = client.post(
        "/ivr/process_voice",
        json={"call_id": call_id, "text": "Check my flight status", "current_menu": "main"}
    )
    assert voice_resp_1.status_code == 200
    data_1 = voice_resp_1.json()
    assert data_1["current_menu"] == "flight_status_pnr"
    
    # 3. Say PNR "855678" (S. Priya)
    voice_resp_pnr = client.post(
        "/ivr/process_voice",
        json={"call_id": call_id, "text": "my pnr is 8 5 5 6 7 8", "current_menu": "flight_status_pnr"}
    )
    assert voice_resp_pnr.status_code == 200
    data_pnr = voice_resp_pnr.json()
    
    # 4. Check the final result
    assert data_pnr["status"] == "pnr_found"
    assert data_pnr["call_action"] == "hangup"
    assert "Passenger: S. Priya" in data_pnr["message"]

def test_nlu_flow_cancel_flight(client):
    """Test NLU flow for cancelling a flight"""
    # 1. Start
    start_resp = client.post("/ivr/start", json={"caller_number": "+1CancelTest"})
    call_id = start_resp.json()["call_id"] # <--- This will pass

    # 2. Say "Manage Booking"
    voice_resp_1 = client.post(
        "/ivr/process_voice",
        json={"call_id": call_id, "text": "I want to manage my booking", "current_menu": "main"}
    )
    assert voice_resp_1.json()["current_menu"] == "manage_booking_pnr"

    # 3. Say PNR "631111" (M. Banerjee)
    voice_resp_pnr = client.post(
        "/ivr/process_voice",
        json={"call_id": call_id, "text": "six three one one one one", "current_menu": "manage_booking_pnr"}
    )
    assert voice_resp_pnr.status_code == 200
    data_pnr = voice_resp_pnr.json()
    assert data_pnr["current_menu"] == "manage_booking_options"
    
    # 4. Say "Cancel Flight"
    voice_resp_cancel = client.post(
        "/ivr/process_voice",
        json={"call_id": call_id, "text": "cancel my flight", "current_menu": "manage_booking_options"}
    )
    assert voice_resp_cancel.status_code == 200
    data_cancel = voice_resp_cancel.json()
    
    # 5. Check result
    assert data_cancel["status"] == "call_ended"
    assert data_cancel["call_action"] == "hangup"
    assert "has been successfully cancelled" in data_cancel["message"]