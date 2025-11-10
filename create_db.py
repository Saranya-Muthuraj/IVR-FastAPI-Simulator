# create_db.py
from database import Base, engine, SessionLocal, Booking, FrequentFlyer

# <--- UPDATED MOCK DATA with passenger details and 'seats_available'
MOCK_PNR_DB = {
    "241234": {"pnr_display": "AI1234", "flight": "AI101", "status": "Confirmed", "route": "Mumbai to Delhi", "time": "Today 6:00 PM", "seats_available": 30, "passenger_name": "R. Kumar", "passenger_age": 45, "passenger_gender": "Male"},
    "855678": {"pnr_display": "UK5678", "flight": "UK822", "status": "Delayed", "route": "Chennai to Bangalore", "time": "Today 4:30 PM (New 5:15 PM)", "seats_available": 5, "passenger_name": "S. Priya", "passenger_age": 28, "passenger_gender": "Female"},
    "749876": {"pnr_display": "SG9876", "flight": "SG445", "status": "Cancelled", "route": "Delhi to Goa", "time": "Tomorrow 9:00 AM", "seats_available": 0, "passenger_name": "A. Gupta", "passenger_age": 33, "passenger_gender": "Male"},
    "631111": {"pnr_display": "6E1111", "flight": "6E204", "status": "Confirmed", "route": "Kolkata to Hyderabad", "time": "Today 7:20 PM", "seats_available": 50, "passenger_name": "M. Banerjee", "passenger_age": 52, "passenger_gender": "Female"},
    "222222": {"pnr_display": "BA2222", "flight": "BA142", "status": "Confirmed", "route": "London to Mumbai", "time": "Tomorrow 11:00 AM", "seats_available": 12, "passenger_name": "John Smith", "passenger_age": 41, "passenger_gender": "Male"},
    "353333": {"pnr_display": "EK3333", "flight": "EK501", "status": "Boarding", "route": "Dubai to Chennai", "time": "Today 4:30 PM", "seats_available": 0, "passenger_name": "F. Al-Jaber", "passenger_age": 29, "passenger_gender": "Female"},
    "734444": {"pnr_display": "QF4444", "flight": "QF068", "status": "On Time", "route": "Singapore to Sydney", "time": "Today 8:00 PM", "seats_available": 45, "passenger_name": "L. Chen", "passenger_age": 60, "passenger_gender": "Male"}
}

MOCK_FF_DB = {
    "111222333": {"pin": "1234", "points": 12500, "name": "Saranya"},
    "987654321": {"pin": "1995", "points": 55000, "name": "Kumar"},
    "555666777": {"pin": "0000", "points": 800, "name": "Priya"}
}

def setup_database():
    # Create all tables (defined in database.py)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        if db.query(Booking).count() == 0:
            print("Populating Bookings (PNR) table...")
            for key, data in MOCK_PNR_DB.items():
                # The **data unpacks all key-value pairs, including the new passenger details
                db_booking = Booking(pnr_key=key, **data) 
                db.add(db_booking)
            db.commit()
            print("Bookings populated.")
        else:
            print("Bookings table already has data.")

        # Check if data already exists
        if db.query(FrequentFlyer).count() == 0:
            print("Populating FrequentFlyer table...")
            for key, data in MOCK_FF_DB.items():
                db_ff = FrequentFlyer(ff_number=key, **data)
                db.add(db_ff)
            db.commit()
            print("FrequentFlyer populated.")
        else:
            print("FrequentFlyer table already has data.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Setting up database...")
    setup_database()
    print("Database setup complete. You can now run your FastAPI app.")

