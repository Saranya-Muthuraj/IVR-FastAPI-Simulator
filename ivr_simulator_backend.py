# ivr_simulator_backend.py
# FINAL VERSION (v23): NLU Fix + Star Key Go-Back

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import random
import re

# <--- UPDATED IMPORTS
from sqlalchemy.orm import Session
from sqlalchemy import func # <--- IMPORT 'func'
# Import our new database models and session helper
from database import get_db, Booking, FrequentFlyer, CallHistory

app = FastAPI(title="IVR Simulator Backend", version="3.3.0 (NLU/Star-Key Fix)")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATA MODELS (Unchanged) ====================
class CallStart(BaseModel):
    caller_number: str
    call_id: Optional[str] = None

class DTMFInput(BaseModel):
    call_id: str
    digit: str
    current_menu: str

class VoiceInput(BaseModel):
    call_id: str
    text: str
    current_menu: str

class CallEndRequest(BaseModel):
    call_id: str

# ==================== IN-MEMORY STORAGE ====================
active_calls = {}

# ==================== MENU_STRUCTURE (UPDATED: Star-Key) ====================
MENU_STRUCTURE = {
    "main": {
        "prompt": "Welcome to Air India. You can say your option. "
                  "Press 1 for Flight Status. "
                  "Press 2 to Manage an Existing Booking. "
                  "Press 3 for Baggage Services. "
                  "Press 4 for Check-in and Boarding Pass. "
                  "Press 5 to Book a New Flight. "
                  "Press 6 for Frequent Flyer Program. "
                  "Press 7 for Special Assistance. "
                  "Press 8 for Refunds and Receipts. "
                  "Press 9 for All Other Inquiries. "
                  "Press 0 to speak with an agent.",
        "options": {
            "1": {"action": "goto_menu", "target": "flight_status_pnr", "message": "You selected Flight Status."},
            "2": {"action": "goto_menu", "target": "manage_booking_pnr", "message": "You selected Manage Booking."},
            "3": {"action": "goto_menu", "target": "baggage", "message": "You selected Baggage Services."},
            "4": {"action": "goto_menu", "target": "check_in_options", "message": "You selected Check-in and Boarding Pass."},
            "5": {"action": "goto_menu", "target": "booking_ask_flight", "message": "You selected Book New Flight."},
            "6": {"action": "goto_menu", "target": "frequent_flyer_number", "message": "You selected Frequent Flyer Program."},
            "7": {"action": "goto_menu", "target": "special_assistance", "message": "You selected Special Assistance."},
            "8": {"action": "goto_menu", "target": "refunds", "message": "You selected Refunds and Receipts."},
            "9": {"action": "goto_menu", "target": "other_inquiries", "message": "You selected Other Inquiries."},
            "0": {"action": "transfer_agent", "message": "You will be directing to our airline agent please wait"} # <-- 0 is STILL agent
        }
    },
    "flight_status_pnr": { # Option 1 PNR
        "prompt": "Please say your 6-digit PNR number, or enter it on the keypad followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_status", "message": "Looking up your PNR..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "manage_booking_pnr": { # Option 2 PNR
       "prompt": "To manage your booking, please say your 6-digit PNR number, or enter it on the keypad followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_manage", "message": "Finding your booking..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "manage_booking_options": { # Option 2 Submenu
        "prompt": "PNR found. Say 'Change Flight' or 'Cancel Flight'. Or, Press 1 to Change your flight. Press 2 to Cancel your flight. Press star to go back.",
        "options": {
            "1": {"action": "end_call", "message": "To change your flight, a link has been sent via SMS. This call will now end."},
            "2": {"action": "cancel_flight", "message": "Attempting to cancel your flight..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "baggage": { # Option 3
        "prompt": "For Baggage Services: Say 'Lost Baggage' or 'Baggage Allowance'. Or, Press 1 for Lost or Delayed Baggage. Press 2 for Baggage Allowance. Press star to go back.",
        "options": {
            "1": {"action": "transfer_agent", "message": "Transferring to a baggage specialist."},
            "2": {"action": "end_call", "message": "For domestic flights, your cabin allowance is 7kg and check-in allowance is 15kg. For international, check-in is 25kg. This call will now end."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "check_in_options": { # Option 4 Submenu
        "prompt": "For Check-in: Say 'Check in' or 'Get Boarding Pass'. Or, Press 1 to check in for your flight. Press 2 to get your boarding pass. Press star to go back.",
        "options": {
            "1": {"action": "goto_menu", "target": "check_in_pnr_for_checkin", "message": "Okay, let's check you in."},
            "2": {"action": "goto_menu", "target": "check_in_pnr_for_boardingpass", "message": "Okay, let's get your boarding pass."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "check_in_pnr_for_checkin": { # Option 4 -> 1 PNR
        "prompt": "To check in, please say your 6-digit PNR number, or enter it followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_checkin", "message": "Finding your booking for check-in..."},
            "*": {"action": "goto_menu", "target": "check_in_options", "message": "Going back."} # <-- CHANGED
        }
    },
     "check_in_pnr_for_boardingpass": { # Option 4 -> 2 PNR
        "prompt": "To get your boarding pass, please say your 6-digit PNR number, or enter it followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_boardingpass", "message": "Finding your booking for boarding pass..."},
            "*": {"action": "goto_menu", "target": "check_in_options", "message": "Going back."} # <-- CHANGED
        }
    },
    # <--- UPDATED/NEW MENUS FOR BOOKING (OPTION 5)
    "booking_ask_flight": { 
        "prompt": "Please say the flight number you wish to book, like 'one zero one' for AI101, or enter the digits followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_flight_for_booking", "message": "Checking seat availability for this flight..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "booking_ask_name": {
        "prompt": "Please say the passenger's full name now. Say 'go back' or press star to cancel.", # <-- PROMPT UPDATED
        "options": {
             # This menu MUST use voice input.
             "*": {"action": "goto_menu", "target": "main", "message": "Booking cancelled. Going back to main menu."} # <-- CHANGED
        }
    },
    "booking_ask_age": {
        "prompt": "Please say the passenger's age, or enter it on the keypad followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "set_age_and_ask_gender", "message": "Age recorded."},
             "*": {"action": "goto_menu", "target": "main", "message": "Booking cancelled. Going back to main menu."} # <-- CHANGED
        }
    },
    "booking_ask_gender": {
        "prompt": "Please say 'Male', 'Female', or 'Other'. Or, press 1 for Male, 2 for Female, 3 for Other. Press star to go back.",
        "options": {
             "1": {"action": "set_gender_and_confirm", "gender": "Male", "message": "Gender set as Male."},
             "2": {"action": "set_gender_and_confirm", "gender": "Female", "message": "Gender set as Female."},
             "3": {"action": "set_gender_and_confirm", "gender": "Other", "message": "Gender set as Other."},
             "*": {"action": "goto_menu", "target": "booking_ask_age", "message": "Going back to age."} # <-- CHANGED
        }
    },
    "booking_confirm_details": {
        "prompt": "You are about to book. Press 1 to confirm, star to cancel.", # This prompt is set dynamically
         "options": {
            "1": {"action": "confirm_booking", "message": "Booking your seat..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Booking cancelled. Going back to main menu."} # <-- CHANGED
        }
    },
    # <--- END NEW MENUS
    "frequent_flyer_number": { # Option 6 -> FF Number Input
        "prompt": "Please say or enter your 9-digit Flying Returns number followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_ff_number", "message": "Looking up your account..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "frequent_flyer_pin": { # Option 6 -> PIN Input
        "prompt": "For security, please say or enter your 4-digit PIN followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "verify_ff_pin", "message": "Verifying your PIN..."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "frequent_flyer_options": { # Option 6 Submenu (After PIN)
        "prompt": "Account verified. Say 'Check Points' or 'Redeem Points'. Or, Press 1 to check your points balance. Press 2 to redeem points. Press star to go back.",
        "options": {
            "1": {"action": "check_ff_points", "message": "Checking your points balance..."},
            "2": {"action": "end_call", "message": "To redeem points for flights or upgrades, please log in to your account on our website. This call will now end."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "special_assistance": { # Option 7
        "prompt": "For Special Assistance: Say 'Wheelchair' or 'Other Needs'. Or, Press 1 for Wheelchair Assistance. Press 2 for other needs. Press star to go back.",
        "options": {
            "1": {"action": "transfer_agent", "message": "Transferring to our special assistance team for wheelchair booking."},
            "2": {"action": "transfer_agent", "message": "Transferring to our special assistance team."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "refunds": { # Option 8 Submenu
        "prompt": "For Refunds and Receipts: Say 'Refund Status' or 'Get Receipt'. Or, Press 1 for Refund Status. Press 2 to get a copy of your receipt. Press star to go back.",
        "options": {
            "1": {"action": "goto_menu", "target": "refunds_pnr_for_status", "message": "Okay, let's check your refund status."},
            "2": {"action": "goto_menu", "target": "refunds_pnr_for_receipt", "message": "Okay, let's get your receipt."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    },
    "refunds_pnr_for_status": { # Option 8 -> 1 PNR
        "prompt": "To check your refund status, please say or enter your 6-digit PNR followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_refundstatus", "message": "Finding your refund details..."},
            "*": {"action": "goto_menu", "target": "refunds", "message": "Going back."} # <-- CHANGED
        }
    },
     "refunds_pnr_for_receipt": { # Option 8 -> 2 PNR
        "prompt": "To get your receipt, please say or enter your 6-digit PNR followed by hash. Press star to go back.",
        "options": {
            "#": {"action": "lookup_pnr_receipt", "message": "Finding your booking details..."},
            "*": {"action": "goto_menu", "target": "refunds", "message": "Going back."} # <-- CHANGED
        }
    },
    "other_inquiries": { # Option 9
        "prompt": "For Other Inquiries: Say 'Pet Policy' or 'Group Booking'. Or, Press 1 for Pet Travel Policy. Press 2 for Group Bookings. Press star to go back.",
        "options": {
            "1": {"action": "end_call", "message": "For Pet Travel, small pets in carriers are allowed in the cabin for a fee. Please see our website for size restrictions. This call will now end."},
            "2": {"action": "transfer_agent", "message": "For group bookings of 9 or more, transferring to a specialist."},
            "*": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # <-- CHANGED
        }
    }
}

# ==================== HELPER FUNCTIONS (DATABASE) ====================

def end_call_logic(db: Session, call_id_to_end, status_msg=""):
    if call_id_to_end in active_calls:
        call_to_end = active_calls.pop(call_id_to_end) # Use pop to get and remove
        
        call_to_end["end_time"] = datetime.now() 
        if status_msg:
            call_to_end["inputs"].append(status_msg)
        
        start_time_dt = datetime.fromisoformat(call_to_end["start_time"])

        db_call_log = CallHistory(
            call_id=call_to_end["call_id"],
            caller_number=call_to_end["caller_number"],
            start_time=start_time_dt,
            end_time=call_to_end["end_time"],
            menu_path=call_to_end.get("menu_path", []),
            inputs=call_to_end.get("inputs", [])
        )
        
        db.add(db_call_log)
        db.commit()
        
        print(f"✅ Call {call_id_to_end} saved to history DB.")

# <--- NEW HELPER for navigating menus
def _go_to_menu(call: dict, target_menu: str, message: Optional[str] = None):
    """Helper to transition the call state to a new menu."""
    call["current_menu"] = target_menu
    call["menu_path"].append(target_menu)
    response = {
        "status": "processed",
        "message": message,
        "current_menu": target_menu,
        "prompt": MENU_STRUCTURE[target_menu]["prompt"]
    }
    return response

# ==================== ENDPOINTS ====================

@app.get("/")
def root(db: Session = Depends(get_db)): 
    """Health check"""
    try:
        booking_count = db.query(Booking).count()
        ff_count = db.query(FrequentFlyer).count()
        history_count = db.query(CallHistory).count()
        
        return {
            "status": "IVR Simulator Running",
            "database_status": "Connected",
            "live_active_calls": len(active_calls),
            "total_completed_calls_in_db": history_count,
            "total_bookings_in_db": booking_count,
            "total_ff_accounts_in_db": ff_count
        }
    except Exception as e:
        print(f"DB Error: {e}")
        return {"status": "IVR Simulator Running", "database_status": "Error - Not Connected"}


@app.post("/ivr/start")
def start_call(call_data: CallStart):

    call_id = f"CALL_{random.randint(100000, 999999)}"

    active_calls[call_id] = {
        "call_id": call_id,
        "caller_number": call_data.caller_number,
        "start_time": datetime.now().isoformat(), 
        "current_menu": "main",
        "menu_path": ["main"],
        "inputs": [],
        "input_buffer": "",
        "active_pnr": None,
        "active_ff_number": None,
        # <--- NEW FIELDS FOR BOOKING WIZARD
        "booking_flight": None,
        "booking_name": None,
        "booking_age": None,
        "booking_gender": None
    }

    print(f"\n📞 NEW CALL: {call_id} from {call_data.caller_number}")

    return {
        "call_id": call_id,
        "status": "connected",
        "prompt": MENU_STRUCTURE["main"]["prompt"]
    }

# ==========================================================
# ##### !!!!! UPDATED handle_voice_input (NLU FIX) !!!!! #####
# ==========================================================
@app.post("/ivr/process_voice")
async def handle_voice_input(input_data: VoiceInput, db: Session = Depends(get_db)): 
    """
    MODERNIZATION LAYER:
    Accepts natural language text, maps it to legacy IVR logic.
    """
    call_id = input_data.call_id
    text = input_data.text.lower()
    original_menu = input_data.current_menu

    print(f"\n🗣️ VOICE INPUT: Call {call_id}, Menu: {original_menu}, Text: {text}")

    if call_id not in active_calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call = active_calls[call_id]

    # --- NLU (Natural Language Understanding) Simulation ---
    pnr_input_menus = ["flight_status_pnr", "manage_booking_pnr", "check_in_pnr_for_checkin", "check_in_pnr_for_boardingpass", "refunds_pnr_for_status", "refunds_pnr_for_receipt"]
    ff_number_menu = "frequent_flyer_number"
    ff_pin_menu = "frequent_flyer_pin"
    # <--- NEW NLU CONTEXTS
    booking_flight_menu = "booking_ask_flight"
    booking_name_menu = "booking_ask_name"
    booking_age_menu = "booking_ask_age"
    booking_gender_menu = "booking_ask_gender"
    booking_confirm_menu = "booking_confirm_details"

    # <--- NEW: List of words to ignore (FIXED: removed 'a' and 'i')
    FILLER_WORDS = [
        'my', 'is', 'uh', 'um', 'please', 'can', 'get', 'space', 'dot', 'dash', 'want', 'to', 'like'
    ]

    def map_spoken_pnr(spoken_text):
        letter_map = {
            'a': '2', 'b': '2', 'c': '2', 'd': '3', 'e': '3', 'f': '3',
            'g': '4', 'h': '4', 'i': '4', 'j': '5', 'k': '5', 'l': '5',
            'm': '6', 'n': '6', 'o': '6', 'p': '7', 'q': '7', 'r': '7', 's': '7',
            't': '8', 'u': '8', 'v': '8', 'w': '9', 'x': '9', 'y': '9', 'z': '9'
        }
        num_word_map = {
            "one": "1", "two": "2", "three": "3", "four": "4", 
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "zero": "0"
        }

        # <--- UPDATED NLU: Remove filler words first
        for word in FILLER_WORDS + ['pnr', 'number']:
            spoken_text = spoken_text.replace(word, ' ')

        for word, digit in num_word_map.items():
            spoken_text = spoken_text.replace(word, digit)
        
        cleaned_text = re.sub(r'[.\s,-]+', '', spoken_text)
        
        chars = re.findall(r'([a-zA-Z0-9])', cleaned_text)
        alphanumeric_pnr = "".join(chars)
        
        if len(alphanumeric_pnr) == 6:
            numeric_pnr = ""
            for char in alphanumeric_pnr:
                if char.isalpha(): 
                    numeric_pnr += letter_map.get(char, '') 
                elif char.isdigit():
                    numeric_pnr += char
            
            if len(numeric_pnr) == 6:
                print(f"       NLU: Converted spoken PNR '{alphanumeric_pnr}' to '{numeric_pnr}'")
                return numeric_pnr
        
        digit_match = re.search(r'(\d{6})', alphanumeric_pnr)
        if digit_match:
             print(f"       NLU: Found numeric PNR: {digit_match.group(1)}")
             return digit_match.group(1)
             
        return None

    def map_spoken_flight_number(spoken_text):
        num_word_map = {
            "one": "1", "two": "2", "three": "3", "four": "4", 
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "zero": "0"
        }

        # <--- UPDATED NLU: Remove filler words first
        for word in FILLER_WORDS + ['flight', 'book', 'number']:
            spoken_text = spoken_text.replace(word, ' ')

        for word, digit in num_word_map.items():
            spoken_text = spoken_text.replace(word, digit)
        
        # <--- FIX: Allow numbers or letters at start, and remove all spaces
        cleaned_text = re.sub(r'[\s.-]+', '', spoken_text) 
        
        # <--- FIX: Updated REGEX to be more flexible (e.g., "6E204" or "KE204")
        flight_match = re.search(r'([a-zA-Z0-9]{2}\d{2,4})', cleaned_text, re.IGNORECASE)
        if flight_match:
            flight_num_str = flight_match.group(1).upper()
            print(f"       NLU: Found flight code '{flight_num_str}'")
            return flight_num_str

        # Fallback: just digits
        cleaned_digits = re.sub(r'[^0-9]+', '', cleaned_text)
        if cleaned_digits:
            flight_num_str = "AI" + cleaned_digits # Assume AI prefix
            print(f"       NLU: Converted spoken digits to '{flight_num_str}'")
            return flight_num_str
        return None

    def map_spoken_age(spoken_text):
        # <--- UPDATED NLU: Remove filler words first
        for word in FILLER_WORDS + ['age', 'years', 'old']:
            spoken_text = spoken_text.replace(word, ' ')

        num_word_map = {
            "one": "1", "two": "2", "three": "3", "four": "4", 
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "zero": "0",
            "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
            "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
            "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90"
        }
        for word, digit in num_word_map.items():
            spoken_text = spoken_text.replace(word, digit)

        age_match = re.search(r'(\d{1,3})', spoken_text)
        if age_match:
            age = int(age_match.group(1))
            if 0 < age < 120:
                print(f"       NLU: Extracted age '{age}'")
                return age
        return None

    # --- NLU PROCESSING ---
    if original_menu in pnr_input_menus:
        numeric_pnr = map_spoken_pnr(text) 
        if numeric_pnr:
            call["input_buffer"] = numeric_pnr
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db) 

    elif original_menu == booking_flight_menu:
        flight_num_str = map_spoken_flight_number(text)
        if flight_num_str:
            call["input_buffer"] = flight_num_str
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db)

    # <--- NEW: Handle spoken name (voice only)
    elif original_menu == booking_name_menu:
        # <--- UPDATED NLU: Clean name input
        cleaned_name = text
        for word in FILLER_WORDS + ['name']:
             cleaned_name = cleaned_name.replace(word, ' ')
        
        name = cleaned_name.strip().title() # Remove extra spaces and capitalize
        
        if name:
            call["booking_name"] = name
            return _go_to_menu(call, "booking_ask_age", f"Passenger name set as {name}.")
        
    # <--- NEW: Handle spoken age
    elif original_menu == booking_age_menu:
        age = map_spoken_age(text)
        if age:
            call["input_buffer"] = str(age) # Store as string for DTMF logic
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db)

    # <--- NEW: Handle spoken gender
    elif original_menu == booking_gender_menu:
        digit = None
        if "male" in text:
            digit = "1"
        elif "female" in text:
            digit = "2"
        elif "other" in text:
            digit = "3"
        
        if digit:
            dtmf_input = DTMFInput(call_id=call_id, digit=digit, current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db)

    elif original_menu == ff_number_menu:
        # <--- UPDATED NLU: Remove filler words
        cleaned_text = text
        for word in FILLER_WORDS + ['number']:
             cleaned_text = cleaned_text.replace(word, ' ')
        cleaned_text = re.sub(r'[^0-9]+', '', cleaned_text) # Get only digits
        
        data_match = re.search(r'(\d{9})', cleaned_text)
        if data_match:
            data = data_match.group(1)
            print(f"       NLU: Extracted FF Number: {data}")
            call["input_buffer"] = data
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db) 

    elif original_menu == ff_pin_menu:
        # <--- UPDATED NLU: Remove filler words
        cleaned_text = text
        for word in FILLER_WORDS + ['pin']:
             cleaned_text = cleaned_text.replace(word, ' ')
        
        spoken_digits = cleaned_text.split()
        pin_digits = ""
        num_map = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
        for word in spoken_digits:
            if word.isdigit():
                pin_digits += word
            elif word in num_map:
                pin_digits += num_map[word]

        data_match = re.search(r'(\d{4})', pin_digits)
        if data_match:
            data = data_match.group(1)
            print(f"       NLU: Extracted PIN: {data}")
            call["input_buffer"] = data
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input, db) 

    # --- (Voice to DTMF mapping logic) ---
    digit_to_press = None
    menu_to_use = original_menu
    if "agent" in text or "speak" in text:
        digit_to_press = "0"
        menu_to_use = "main"
    elif "main menu" in text:
        if original_menu != "main":
            digit_to_press = "*"  # <--- CHANGED
            menu_to_use = original_menu
    elif "back" in text:
       if original_menu in [ff_pin_menu, "booking_confirm_details", "booking_ask_name", "booking_ask_age", "booking_ask_gender"]:
            digit_to_press = "*"  # <--- CHANGED
            menu_to_use = original_menu
       elif original_menu != "main":
            digit_to_press = "*"  # <--- CHANGED
            menu_to_use = original_menu
    if digit_to_press is None:
        if original_menu == "main":
            if "status" in text: digit_to_press = "1"
            elif "manage" in text or "cancel" in text or "change" in text: digit_to_press = "2"
            elif "baggage" in text or "bag" in text: digit_to_press = "3"
            elif "check in" in text or "boarding pass" in text: digit_to_press = "4"
            elif "booking" in text or "book" in text: digit_to_press = "5"
            elif "frequent" in text or "points" in text: digit_to_press = "6"
            elif "special" in text or "wheelchair" in text: digit_to_press = "7"
            elif "refund" in text or "receipt" in text: digit_to_press = "8"
            elif "other" in text or "pet" in text: digit_to_press = "9"
        elif original_menu == "manage_booking_options":
            if "change" in text: digit_to_press = "1"
            elif "cancel" in text: digit_to_press = "2"
        elif original_menu == booking_confirm_menu:
            if "confirm" in text or "yes" in text: digit_to_press = "1"
        elif original_menu == "baggage":
            if "lost" in text: digit_to_press = "1"
            elif "allowance" in text: digit_to_press = "2"
        elif original_menu == "check_in_options":
            if "check in" in text: digit_to_press = "1"
            elif "boarding pass" in text: digit_to_press = "2"
        elif original_menu == "frequent_flyer_options":
            if "check" in text or "points" in text: digit_to_press = "1"
            elif "redeem" in text: digit_to_press = "2"
        elif original_menu == "special_assistance":
            if "wheelchair" in text: digit_to_press = "1"
            elif "other" in text: digit_to_press = "2"
        elif original_menu == "refunds":
            if "status" in text: digit_to_press = "1"
            elif "receipt" in text or "copy" in text: digit_to_press = "2"
        elif original_menu == "other_inquiries":
            if "pet" in text: digit_to_press = "1"
            elif "group" in text: digit_to_press = "2"

    if digit_to_press:
        print(f"       NLU: Mapped text '{text}' to DTMF digit: {digit_to_press} (using menu: {menu_to_use})")
        dtmf_input = DTMFInput(
            call_id=call_id,
            digit=digit_to_press,
            current_menu=menu_to_use
        )
        return await handle_dtmf(dtmf_input, db) 

    # --- (NLU Fail logic) ---
    print("       NLU: No intent or digit matched.")
    prompt_msg = "I'm sorry, I didn't understand that. Please try again."
    if original_menu in pnr_input_menus:
        prompt_msg = "Sorry, I didn't catch that PNR. Please clearly say your 6-digit PNR."
    elif original_menu == booking_flight_menu:
        prompt_msg = "Sorry, I didn't catch that. Please say the digits of the flight, like 'one zero one' for AI101."
    elif original_menu == booking_name_menu:
        prompt_msg = "Sorry, I didn't catch that name. Please try saying it again."
    elif original_menu == booking_age_menu:
        prompt_msg = "Sorry, I didn't catch that. Please say the passenger's age."
    elif original_menu == ff_number_menu:
        prompt_msg = "Sorry, I didn't catch that. Please say your 9-digit Flying Returns number."
    elif original_menu == ff_pin_menu:
        prompt_msg = "Sorry, I didn't catch that PIN. Please say your 4-digit PIN."

    return {
        "status": "invalid",
        "prompt": prompt_msg,
        "current_menu": original_menu,
        "prompt_original": MENU_STRUCTURE[original_menu]["prompt"]
    }

# ==========================================================
# ##### UPDATED handle_dtmf (Star-Key Fix) !!!!! #####
# ==========================================================
@app.post("/ivr/dtmf")
async def handle_dtmf(input_data: DTMFInput, db: Session = Depends(get_db)): 
    """
    Process DTMF key press (The Legacy System)
    """

    call_id = input_data.call_id
    digit = input_data.digit

    if call_id not in active_calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call = active_calls[call_id]
    current_menu = call["current_menu"] 
    menu_name_from_input = input_data.current_menu 

    print(f"\n🔢 DTMF INPUT: Call {call_id}, User's Menu: {current_menu}, Action Menu: {menu_name_from_input}, Digit: {digit}")

    menu = MENU_STRUCTURE.get(menu_name_from_input)
    if not menu:
        return {"error": "Invalid menu state"}

    # --- Input buffer logic (UPDATED for Star-Key) ---
    input_required_menus = {
        "flight_status_pnr": 6,
        "manage_booking_pnr": 6,
        "check_in_pnr_for_checkin": 6,
        "check_in_pnr_for_boardingpass": 6,
        "frequent_flyer_number": 9,
        "frequent_flyer_pin": 4,
        "refunds_pnr_for_status": 6,
        "refunds_pnr_for_receipt": 6,
        "booking_ask_flight": -1, # <--- Variable length
        "booking_ask_age": -1 # <--- Variable length
    }
    required_length = input_required_menus.get(menu_name_from_input)

    # --- PNR/FF/PIN Input (Fixed length) ---
    if required_length and required_length > 0 and digit != "#" and digit != "*": # <-- CHANGED
        call["input_buffer"] += digit 
        buffer_content = call["input_buffer"]
        prompt_msg = f"You entered {digit}. Continue entering."
        
        if len(buffer_content) >= required_length:
             prompt_msg = f"You entered {digit}. Press hash to submit."
             
        return { "status": "collecting", "prompt": prompt_msg, "collected": buffer_content, "current_menu": menu_name_from_input }
    
    # --- NEW: Flight Booking/Age Input (Variable length) ---
    elif required_length == -1 and digit != "#" and digit != "*": # <-- CHANGED
        call["input_buffer"] += digit
        buffer_content = call["input_buffer"]
        return { "status": "collecting", "prompt": f"You entered {digit}. Press hash to submit.", "collected": buffer_content, "current_menu": menu_name_from_input }

    
    # --- Check if hash is pressed AND length is incorrect (for fixed-length inputs) ---
    if digit == "#" and required_length and required_length > 0 and len(call["input_buffer"]) != required_length:
         error_message = f"Invalid input length. Must be {required_length} digits. Please try again."
         return _handle_invalid_input(error_message)


    if digit not in menu["options"]:
        invalid_menu_to_use = call["current_menu"]
        return { "status": "invalid", "prompt": "Invalid option. Please try again.", "current_menu": invalid_menu_to_use, "valid_options": list(MENU_STRUCTURE[invalid_menu_to_use]["options"].keys()) }

    call["inputs"].append(digit)

    option = menu["options"][digit]
    action = option["action"]
    message = option["message"]

    response = { "status": "processed", "message": message }

    # --- (DB Helper functions) ---
    def _find_pnr_info(pnr_key_to_find):
        return db.query(Booking).filter(Booking.pnr_key == pnr_key_to_find).first()
    
    def _find_flight_info(flight_num_to_find):
        # <--- FIX: Trim spaces from database column before comparing
        # This fixes the "KE204" vs "KE204 " bug
        return db.query(Booking).filter(func.trim(Booking.flight).ilike(func.trim(flight_num_to_find))).first()

    def _find_ff_info(ff_num_to_find):
        return db.query(FrequentFlyer).filter(FrequentFlyer.ff_number == ff_num_to_find).first()

    def _handle_invalid_input(error_message, repeat_menu=None):
        call["input_buffer"] = ""
        menu_to_repeat = repeat_menu if repeat_menu else menu_name_from_input
        
        return {
            "status": "processed", 
            "message": error_message,
            "prompt": MENU_STRUCTURE[menu_to_repeat]["prompt"], 
            "current_menu": menu_to_repeat
        }

    # --- (Action logic: goto_menu, end_call, transfer_agent are unchanged) ---
    if action == "goto_menu":
        target_menu = option["target"]
        
        # <--- NEW: Clear booking data if returning to main
        if target_menu == "main":
            call["active_pnr"] = None
            call["active_ff_number"] = None
            call["booking_flight"] = None
            call["booking_name"] = None
            call["booking_age"] = None
            call["booking_gender"] = None
            
        if menu_name_from_input in input_required_menus:
             call["input_buffer"] = ""

        response = _go_to_menu(call, target_menu, message)


    elif action == "end_call":
        response["status"] = "call_ended"
        response["call_action"] = "hangup"
        end_call_logic(db, call_id, f"Call ended with message: {message}") 

    elif action == "transfer_agent":
        response["status"] = "transferring"
        response["call_action"] = "hangup"
        response["message"] = message
        end_call_logic(db, call_id, f"Transferred to agent: {message}") 
        print(f"✅ ACTION: {action} - Sending 'transferring' signal to frontend.")
        return response

    elif action == "lookup_pnr_status":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 

        if pnr_info:
            pnr_display = pnr_info.pnr_display
            seats = pnr_info.seats_available 

            vacancy_message = ""
            if pnr_info.status == "Cancelled":
                vacancy_message = "There are no seats available as this flight is cancelled."
            elif seats > 0:
                vacancy_message = f"There are currently {seats} seats available on this flight."
            else:
                vacancy_message = "This flight is currently full."
            
            # <--- CRASH FIX (v22)
            pass_name = pnr_info.passenger_name if pnr_info.passenger_name else "N/A"

            response["status"] = "pnr_found"
            response["pnr_info"] = { "pnr_display": pnr_info.pnr_display, "flight": pnr_info.flight, "status": pnr_info.status, "route": pnr_info.route, "time": pnr_info.time, "seats_available": seats }
            
            response["message"] = (
                f"Your PNR {pnr_display}: Flight {pnr_info.flight} from {pnr_info.route} is {pnr_info.status}. "
                f"Passenger: {pass_name}. " # <--- Use safe 'pass_name'
                f"{vacancy_message} " 
                f"This call will now end."
            )
            response["call_action"] = "hangup"
            end_call_logic(db, call_id, f"Looked up PNR status: {pnr_display}") 
        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    elif action == "lookup_pnr_manage":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 

        if pnr_info:
            pnr_display = pnr_info.pnr_display
            if pnr_info.status == "Cancelled":
                 response["message"] = f"PNR {pnr_display} is already marked as Cancelled. Returning to main menu."
                 target_menu = "main"
                 call["active_pnr"] = None
            else:
                 call["active_pnr"] = pnr_key 
                 target_menu = "manage_booking_options"

            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu

            if target_menu == "manage_booking_options":
                # <--- CRASH FIX (v22)
                pass_name = pnr_info.passenger_name if pnr_info.passenger_name else "N/A"
                response["prompt"] = f"PNR {pnr_display} for {pass_name} found. Say 'Cancel Flight'. Or, Press 2 to Cancel. Press star to go back."
            else:
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]

        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    elif action == "lookup_pnr_checkin":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 
        
        if pnr_info:
            pnr_display = pnr_info.pnr_display
            if pnr_info.status == "Cancelled":
                 response["message"] = f"Cannot check in for cancelled PNR {pnr_display}. Returning to main menu."
                 target_menu = "main"
                 call["current_menu"] = target_menu
                 call["menu_path"].append(target_menu)
                 response["current_menu"] = target_menu
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            else:
                # <--- CRASH FIX (v22)
                pass_name = pnr_info.passenger_name if pnr_info.passenger_name else "N/A"
                response["status"] = "call_ended"
                response["message"] = f"Check-in successful for PNR {pnr_display}, passenger {pass_name}. A link has been sent. This call will now end."
                response["call_action"] = "hangup"
                end_call_logic(db, call_id, f"Checked in PNR: {pnr_display}") 
        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    elif action == "lookup_pnr_boardingpass":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 

        if pnr_info:
             pnr_display = pnr_info.pnr_display
             if pnr_info.status == "Cancelled":
                 response["message"] = f"Cannot get boarding pass for cancelled PNR {pnr_display}. Returning to main menu."
                 target_menu = "main"
                 call["current_menu"] = target_menu
                 call["menu_path"].append(target_menu)
                 response["current_menu"] = target_menu
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
             else:
                 response["status"] = "call_ended"
                 response["message"] = f"Your boarding pass for PNR {pnr_display} has been re-sent to your registered email. This call will now end."
                 response["call_action"] = "hangup"
                 end_call_logic(db, call_id, f"Sent boarding pass for PNR: {pnr_display}") 
        else:
             response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    # ==================================================
    # <--- ACTION 'cancel_flight' IS UPDATED ----->
    # ==================================================
    elif action == "cancel_flight":
        pnr_to_cancel_key = call.get("active_pnr")
        
        if pnr_to_cancel_key:
            booking_to_cancel = _find_pnr_info(pnr_to_cancel_key) 
            
            if booking_to_cancel:
                pnr_display = booking_to_cancel.pnr_display

                if booking_to_cancel.status == "Cancelled":
                    response["message"] = f"Your flight for PNR {pnr_display} is already cancelled. This call will now end."
                else:
                    # 1. UPDATE THE BOOKING STATUS
                    booking_to_cancel.status = "Cancelled"
                    
                    # 2. <--- NEW: INCREMENT SEAT COUNT
                    flight_num = booking_to_cancel.flight
                    # Find all bookings for this flight to update their seat counts
                    all_bookings_for_flight = db.query(Booking).filter(Booking.flight == flight_num).all()
                    
                    if all_bookings_for_flight:
                        current_seats = all_bookings_for_flight[0].seats_available
                        new_seat_count = current_seats + 1
                        for b in all_bookings_for_flight:
                            b.seats_available = new_seat_count
                        print(f"       *** SEATS UPDATED for {flight_num}: {current_seats} -> {new_seat_count} ***")

                    # 3. COMMIT (SAVE) ALL CHANGES
                    db.commit() 
                    print(f"       *** PNR {pnr_display} ({pnr_to_cancel_key}) STATUS UPDATED TO CANCELLED IN DB ***")
                    response["message"] = f"Your flight for PNR {pnr_display} has been successfully cancelled. A confirmation email has been sent. This call will now end."
                
                response["status"] = "call_ended"
                response["call_action"] = "hangup"
                end_call_logic(db, call_id, f"Cancelled PNR: {pnr_display}") 
            
            else:
                 response = _handle_invalid_input("An error occurred finding your PNR. Returning to main menu.", "main")
                 call["active_pnr"] = None
        else:
             response = _handle_invalid_input("An error occurred (no PNR active). Returning to main menu.", "main")

    # --- (FF logic is unchanged) ---
    elif action == "lookup_ff_number":
        ff_number = call["input_buffer"]
        call["input_buffer"] = ""
        ff_info = _find_ff_info(ff_number) 

        if ff_info:
            call["active_ff_number"] = ff_number
            response = _go_to_menu(call, "frequent_flyer_pin", f"Account {ff_number} found for {ff_info.name}.")
        else:
             response = _handle_invalid_input(f"Sorry, Flying Returns number {ff_number} was not found. Please try again.")

    elif action == "verify_ff_pin":
        pin_entered = call["input_buffer"]
        call["input_buffer"] = ""
        active_ff = call.get("active_ff_number")
        ff_info = _find_ff_info(active_ff) 

        if ff_info and ff_info.pin == pin_entered: 
            response = _go_to_menu(call, "frequent_flyer_options", "PIN verified.")
        else:
            response = _handle_invalid_input(f"Sorry, that PIN is incorrect. Please try again.")

    elif action == "check_ff_points":
        active_ff = call.get("active_ff_number")
        ff_info = _find_ff_info(active_ff) 
        if ff_info:
             points = ff_info.points 
             response["status"] = "call_ended"
             response["message"] = f"Your Flying Returns balance for account {active_ff} is {points:,} points. This call will now end."
             response["call_action"] = "hangup"
             end_call_logic(db, call_id, f"Checked points for FF: {active_ff}") 
        else:
            response = _handle_invalid_input("An error occurred finding your account details. Returning to main menu.", "main")
            call["active_ff_number"] = None

    # --- (Refund logic is unchanged) ---
    elif action == "lookup_pnr_refundstatus":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 

        if pnr_info:
            pnr_display = pnr_info.pnr_display
            refund_msg = ""
            if pnr_info.status == "Cancelled":
                 refund_msg = f"Your refund request for cancelled PNR {pnr_display} is currently in process. It should reflect in your account within 5-7 business days."
            else:
                 refund_msg = f"There is no active refund request found for PNR {pnr_display} as the booking is currently {pnr_info.status}."

            response["status"] = "call_ended"
            response["message"] = refund_msg + " This call will now end."
            response["call_action"] = "hangup"
            end_call_logic(db, call_id, f"Checked refund status for PNR: {pnr_display}") 
        else:
             response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    elif action == "lookup_pnr_receipt":
        pnr_key = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr_key) 

        if pnr_info:
            pnr_display = pnr_info.pnr_display
            response["status"] = "call_ended"
            response["message"] = f"A copy of the receipt for PNR {pnr_display} has been sent to your registered email address. This call will now end."
            response["call_action"] = "hangup"
            end_call_logic(db, call_id, f"Sent receipt for PNR: {pnr_display}") 
        else:
             response = _handle_invalid_input(f"Sorry, PNR {pnr_key} was not found. Please try again.")

    # ==================================================
    # <--- NEW BOOKING ACTIONS ----->
    # ==================================================
    elif action == "lookup_flight_for_booking":
        # Input buffer could be "101" (keypad) or "AI101" (voice)
        flight_input = call["input_buffer"]
        
        # <--- FIX: Allow number-letter combos like "6E204"
        # NLU provides the clean code, but keypad input might just be digits
        if flight_input.isdigit():
            flight_input = "AI" + flight_input # Assume AI prefix
        
        # Use .upper() to be safe
        flight_info = _find_flight_info(flight_input.upper())
        call["input_buffer"] = ""
        
        if flight_info:
            if flight_info.seats_available > 0:
                call["booking_flight"] = flight_info.flight # Store "AI101"
                response = _go_to_menu(call, "booking_ask_name", f"Flight {flight_info.flight} found. {flight_info.seats_available} seats available.")
            else:
                response = _handle_invalid_input(f"Sorry, flight {flight_info.flight} is full. Please try another flight.", "booking_ask_flight")
        else:
            response = _handle_invalid_input(f"Sorry, flight {flight_input.upper()} was not found. Please try again.", "booking_ask_flight")
            
    elif action == "set_age_and_ask_gender":
        try:
            age = int(call["input_buffer"])
            if 0 < age < 120:
                call["booking_age"] = age
                call["input_buffer"] = ""
                response = _go_to_menu(call, "booking_ask_gender", f"Passenger age set as {age}.")
            else:
                response = _handle_invalid_input("Invalid age. Please enter an age between 1 and 120.", "booking_ask_age")
        except ValueError:
            response = _handle_invalid_input("Invalid age entered. Please try again.", "booking_ask_age")

    elif action == "set_gender_and_confirm":
        call["booking_gender"] = option["gender"]
        
        # All details collected, move to final confirmation
        name = call["booking_name"]
        age = call["booking_age"]
        gender = call["booking_gender"]
        flight = call["booking_flight"]
        
        dynamic_prompt = (
            f"You are about to book one seat on flight {flight} for {name}, age {age}, gender {gender}. "
            "Press 1 to confirm and book. Press star to cancel and return to the main menu." # <-- CHANGED
        )
        
        call["current_menu"] = "booking_confirm_details"
        call["menu_path"].append("booking_confirm_details")
        response["current_menu"] = "booking_confirm_details"
        response["prompt"] = dynamic_prompt
        # Message was already set in the option

    elif action == "confirm_booking":
        # --- FINAL BOOKING LOGIC ---
        flight_num = call.get("booking_flight")
        name = call.get("booking_name")
        age = call.get("booking_age")
        gender = call.get("booking_gender")
        
        if not all([flight_num, name, age, gender]):
             response = _handle_invalid_input("A booking error occurred. Incomplete details. Returning to main menu.", "main")
             return response
        
        # Find all bookings for this flight to update seat count
        all_bookings_for_flight = db.query(Booking).filter(Booking.flight == flight_num).all()
        
        if not all_bookings_for_flight:
            response = _handle_invalid_input(f"Error: Flight {flight_num} not found. Returning to main menu.", "main")
            return response
            
        # Check seats again (in case someone else booked)
        current_seats = all_bookings_for_flight[0].seats_available
        if current_seats <= 0:
            response = _handle_invalid_input(f"Sorry, flight {flight_num} has just sold out. Returning to main menu.", "main")
            return response
        
        # --- Create new booking ---
        new_seat_count = current_seats - 1
        
        # Get flight details from first booking
        flight_template = all_bookings_for_flight[0]
        
        # Generate new PNR
        new_pnr_key = str(random.randint(100000, 999999))
        while _find_pnr_info(new_pnr_key): # Ensure PNR is unique
            new_pnr_key = str(random.randint(100000, 999999))
        
        new_pnr_display = flight_template.flight[:2] + new_pnr_key[2:]

        new_booking = Booking(
            pnr_key=new_pnr_key,
            pnr_display=new_pnr_display,
            flight=flight_num,
            status="Confirmed",
            route=flight_template.route,
            time=flight_template.time,
            seats_available=new_seat_count,
            passenger_name=name,
            passenger_age=age,
            passenger_gender=gender
        )
        
        # Update seat count for ALL bookings on this flight
        for b in all_bookings_for_flight:
            b.seats_available = new_seat_count
            
        db.add(new_booking)
        db.commit()
        
        print(f"       *** NEW BOOKING: {new_pnr_display} for {name} on {flight_num} ***")
        print(f"       *** SEATS UPDATED for {flight_num}: {current_seats} -> {new_seat_count} ***")

        response["status"] = "call_ended"
        response["message"] = f"Booking confirmed. Your new PNR is {new_pnr_display}. This call will now end."
        response["call_action"] = "hangup"
        end_call_logic(db, call_id, f"Booked PNR: {new_pnr_display}")


    if response.get("status") != "transferring" and response.get("status") != "call_ended":
        print(f"✅ ACTION: {action} - {message}")

    return response


# ==================== end_call ====================
@app.post("/ivr/end")
def end_call(request: CallEndRequest, db: Session = Depends(get_db)): 
    """End call (user hung up)"""
    call_id = request.call_id
    if call_id in active_calls:
        end_call_logic(db, call_id, "Call ended by user.")
        return {"status": "call_ended", "call_id": call_id}
        
    return {"status": "error", "message": "Call not found"}
