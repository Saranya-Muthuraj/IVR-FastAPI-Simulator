# ivr_simulator_backend.py
# FINAL VERSION (v11): Added FF Number & PIN Verification for Option 6

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import random
import re

app = FastAPI(title="IVR Simulator Backend", version="1.0.0")

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

class CallLog(BaseModel):
    call_id: str
    caller_number: str
    start_time: str
    end_time: Optional[str] = None
    duration: Optional[int] = None
    menu_path: List[str] = []
    inputs: List[str] = []

class CallEndRequest(BaseModel):
    call_id: str

# ==================== IN-MEMORY STORAGE ====================
active_calls = {}
call_history = []

# ==================== MOCK PNR DATABASE (Unchanged) ====================
MOCK_PNR_DB = {
    "AI1234": {"flight": "AI101", "status": "Confirmed", "route": "Mumbai to Delhi", "time": "Today 6:00 PM"},
    "UK5678": {"flight": "UK822", "status": "Delayed", "route": "Chennai to Bangalore", "time": "Today 4:30 PM (New 5:15 PM)"},
    "SG9876": {"flight": "SG445", "status": "Cancelled", "route": "Delhi to Goa", "time": "Tomorrow 9:00 AM"},
    "6E1111": {"flight": "6E204", "status": "Confirmed", "route": "Kolkata to Hyderabad", "time": "Today 7:20 PM"},
    "BA2222": {"flight": "BA142", "status": "Confirmed", "route": "London to Mumbai", "time": "Tomorrow 11:00 AM"},
    "EK3333": {"flight": "EK501", "status": "Boarding", "route": "Dubai to Chennai", "time": "Today 4:30 PM"},
    "QF4444": {"flight": "QF068", "status": "On Time", "route": "Singapore to Sydney", "time": "Today 8:00 PM"}
}

# ==========================================================
# ##### !!!!! NEW MOCK FREQUENT FLYER DATABASE !!!!! #####
# ==========================================================
MOCK_FF_DB = {
    "111222333": {"pin": "1234", "points": 12500, "name": "Saranya"},
    "987654321": {"pin": "1995", "points": 55000, "name": "Kumar"},
    "555666777": {"pin": "0000", "points": 800, "name": "Priya"}
}

# ==========================================================
# ##### !!!!! UPDATED MENU_STRUCTURE !!!!! #####
# ==========================================================
MENU_STRUCTURE = {
    "main": {
        "prompt": "Welcome to Air India. You can say your option. "
                  "Press 1 for Flight Status. "
                  "Press 2 to Manage an Existing Booking. "
                  "Press 3 for Baggage Services. "
                  "Press 4 for Check-in and Boarding Pass. "
                  "Press 5 to Book a New Flight. "
                  "Press 6 for Frequent Flyer Program. " # Text unchanged
                  "Press 7 for Special Assistance. "
                  "Press 8 for Refunds and Receipts. "
                  "Press 9 for All Other Inquiries. "
                  "Press 0 to speak with an agent.",
        "options": {
            "1": {"action": "goto_menu", "target": "flight_status_pnr", "message": "You selected Flight Status."},
            "2": {"action": "goto_menu", "target": "manage_booking_pnr", "message": "You selected Manage Booking."},
            "3": {"action": "goto_menu", "target": "baggage", "message": "You selected Baggage Services."},
            "4": {"action": "goto_menu", "target": "check_in_options", "message": "You selected Check-in and Boarding Pass."},
            "5": {"action": "goto_menu", "target": "booking", "message": "You selected Book New Flight."},
            # --- FIX: Go to FF number menu first ---
            "6": {"action": "goto_menu", "target": "frequent_flyer_number", "message": "You selected Frequent Flyer Program."},
            # --- End Fix ---
            "7": {"action": "goto_menu", "target": "special_assistance", "message": "You selected Special Assistance."},
            "8": {"action": "goto_menu", "target": "refunds", "message": "You selected Refunds and Receipts."},
            "9": {"action": "goto_menu", "target": "other_inquiries", "message": "You selected Other Inquiries."},
            "0": {"action": "transfer_agent", "message": "You will be directing to our airline agent please wait"}
        }
    },
    "flight_status_pnr": { # Option 1 PNR
        "prompt": "Please say your 6-digit PNR number, or enter it on the keypad followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "lookup_pnr_status", "message": "Looking up your PNR..."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "manage_booking_pnr": { # Option 2 PNR
         "prompt": "To manage your booking, please say your 6-digit PNR number, or enter it on the keypad followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "lookup_pnr_manage", "message": "Finding your booking..."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "manage_booking_options": { # Option 2 Submenu
        "prompt": "PNR found. Say 'Change Flight' or 'Cancel Flight'. Or, Press 1 to Change your flight. Press 2 to Cancel your flight. Press 0 to go back.",
        "options": {
            "1": {"action": "end_call", "message": "To change your flight, a link has been sent via SMS. This call will now end."},
            "2": {"action": "cancel_flight", "message": "Attempting to cancel your flight..."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "baggage": { # Option 3
        "prompt": "For Baggage Services: Say 'Lost Baggage' or 'Baggage Allowance'. Or, Press 1 for Lost or Delayed Baggage. Press 2 for Baggage Allowance. Press 0 to go back.",
        "options": {
            "1": {"action": "transfer_agent", "message": "Transferring to a baggage specialist."},
            "2": {"action": "end_call", "message": "For domestic flights, your cabin allowance is 7kg and check-in allowance is 15kg. For international, check-in is 25kg. This call will now end."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "check_in_options": { # Option 4 Submenu
        "prompt": "For Check-in: Say 'Check in' or 'Get Boarding Pass'. Or, Press 1 to check in for your flight. Press 2 to get your boarding pass. Press 0 to go back.",
        "options": {
            "1": {"action": "goto_menu", "target": "check_in_pnr_for_checkin", "message": "Okay, let's check you in."},
            "2": {"action": "goto_menu", "target": "check_in_pnr_for_boardingpass", "message": "Okay, let's get your boarding pass."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "check_in_pnr_for_checkin": { # Option 4 -> 1 PNR
        "prompt": "To check in, please say your 6-digit PNR number, or enter it followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "lookup_pnr_checkin", "message": "Finding your booking for check-in..."},
            "0": {"action": "goto_menu", "target": "check_in_options", "message": "Going back."}
        }
    },
     "check_in_pnr_for_boardingpass": { # Option 4 -> 2 PNR
        "prompt": "To get your boarding pass, please say your 6-digit PNR number, or enter it followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "lookup_pnr_boardingpass", "message": "Finding your booking for boarding pass..."},
            "0": {"action": "goto_menu", "target": "check_in_options", "message": "Going back."}
        }
    },
    "booking": { # Option 5
        "prompt": "To book a new flight: Say 'Domestic' or 'International'. Or, press 1 for Domestic Flights. Press 2 for International Flights. Press 0 to go back.",
        "options": {
            "1": {"action": "transfer_agent", "message": "Transferring to a domestic booking agent."},
            "2": {"action": "transfer_agent", "message": "Transferring to an international booking agent."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    # --- FIX: Added new menus for FF Number and PIN ---
    "frequent_flyer_number": { # Option 6 -> FF Number Input
        "prompt": "Please say or enter your 9-digit Flying Returns number followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "lookup_ff_number", "message": "Looking up your account..."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "frequent_flyer_pin": { # Option 6 -> PIN Input
        "prompt": "For security, please say or enter your 4-digit PIN followed by hash. Press 0 to go back.",
        "options": {
            "#": {"action": "verify_ff_pin", "message": "Verifying your PIN..."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."} # Go back to main if they press 0 here
        }
    },
    "frequent_flyer_options": { # Option 6 Submenu (After PIN)
        "prompt": "Account verified. Say 'Check Points' or 'Redeem Points'. Or, Press 1 to check your points balance. Press 2 to redeem points. Press 0 to go back.",
        "options": {
            "1": {"action": "check_ff_points", "message": "Checking your points balance..."},
            "2": {"action": "end_call", "message": "To redeem points for flights or upgrades, please log in to your account on our website. This call will now end."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    # --- End Fix ---
    "special_assistance": { # Option 7
        "prompt": "For Special Assistance: Say 'Wheelchair' or 'Other Needs'. Or, Press 1 for Wheelchair Assistance. Press 2 for other needs. Press 0 to go back.",
        "options": {
            "1": {"action": "transfer_agent", "message": "Transferring to our special assistance team for wheelchair booking."},
            "2": {"action": "transfer_agent", "message": "Transferring to our special assistance team."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "refunds": { # Option 8
        "prompt": "For Refunds and Receipts: Say 'Refund Status' or 'Get Receipt'. Or, Press 1 for Refund Status. Press 2 to get a copy of your receipt. Press 0 to go back.",
        "options": {
            "1": {"action": "end_call", "message": "Your refund for PNR SG9876 is in process and will be credited in 5-7 business days. This call will now end."},
            "2": {"action": "end_call", "message": "A copy of your receipt for PNR AI1234 has been sent to your email. This call will now end."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    },
    "other_inquiries": { # Option 9
        "prompt": "For Other Inquiries: Say 'Pet Policy' or 'Group Booking'. Or, Press 1 for Pet Travel Policy. Press 2 for Group Bookings. Press 0 to go back.",
        "options": {
            "1": {"action": "end_call", "message": "For Pet Travel, small pets in carriers are allowed in the cabin for a fee. Please see our website for size restrictions. This call will now end."},
            "2": {"action": "transfer_agent", "message": "For group bookings of 9 or more, transferring to a specialist."},
            "0": {"action": "goto_menu", "target": "main", "message": "Going back to main menu."}
        }
    }
}

# ==================== ENDPOINTS (Unchanged) ====================

@app.get("/")
def root():
    """Health check"""
    return {
        "status": "IVR Simulator Running",
        "active_calls": len(active_calls),
        "total_calls": len(call_history),
        "PNR_DB_STATUS": MOCK_PNR_DB,
        "FF_DB_STATUS": MOCK_FF_DB # Show FF DB for debugging
    }

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
        "input_buffer": "", # Renamed from pnr_buffer
        "active_pnr": None,
        "active_ff_number": None # NEW state for FF
    }

    print(f"\n📞 NEW CALL: {call_id} from {call_data.caller_number}")

    return {
        "call_id": call_id,
        "status": "connected",
        "prompt": MENU_STRUCTURE["main"]["prompt"]
    }

# ==========================================================
# ##### !!!!! UPDATED handle_voice_input !!!!! #####
# ==========================================================
@app.post("/ivr/process_voice")
async def handle_voice_input(input_data: VoiceInput):
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

    # --- Part 1: Data Collection (PNR, FF Number, PIN) ---
    pnr_input_menus = ["flight_status_pnr", "manage_booking_pnr", "check_in_pnr_for_checkin", "check_in_pnr_for_boardingpass"]
    ff_number_menu = "frequent_flyer_number"
    ff_pin_menu = "frequent_flyer_pin"

    if original_menu in pnr_input_menus:
        # Extract PNR (6 chars)
        cleaned_text = text.replace("pnr", "").replace("is", "").replace("my", "").replace(" ", "")
        data_match = re.search(r'([a-zA-Z0-9]{6})', cleaned_text)
        if data_match:
            data = data_match.group(1).upper()
            print(f"      NLU: Extracted PNR: {data}")
            call["input_buffer"] = data
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input)

    elif original_menu == ff_number_menu:
         # Extract FF Number (9 digits)
        cleaned_text = text.replace("number", "").replace("is", "").replace("my", "").replace(" ", "")
        data_match = re.search(r'(\d{9})', cleaned_text) # Look for exactly 9 digits
        if data_match:
            data = data_match.group(1)
            print(f"      NLU: Extracted FF Number: {data}")
            call["input_buffer"] = data
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input)

    elif original_menu == ff_pin_menu:
         # Extract PIN (4 digits)
        cleaned_text = text.replace("pin", "").replace("is", "").replace("my", "").replace(" ", "")
        # Try to handle spoken numbers like "one two three four" -> "1234"
        spoken_digits = cleaned_text.split()
        pin_digits = ""
        num_map = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
        for word in spoken_digits:
            if word.isdigit():
                pin_digits += word
            elif word in num_map:
                pin_digits += num_map[word]

        data_match = re.search(r'(\d{4})', pin_digits) # Look for exactly 4 digits
        if data_match:
            data = data_match.group(1)
            print(f"      NLU: Extracted PIN: {data}")
            call["input_buffer"] = data
            dtmf_input = DTMFInput(call_id=call_id, digit="#", current_menu=original_menu)
            return await handle_dtmf(dtmf_input)

    # --- Part 2: Map Voice to a DTMF Digit ---

    digit_to_press = None
    menu_to_use = original_menu

    # === 2a. Check for TRULY GLOBAL commands first ===
    if "agent" in text or "speak" in text:
        digit_to_press = "0"
        menu_to_use = "main"
    elif "main menu" in text:
        if original_menu != "main":
            digit_to_press = "0"
            menu_to_use = original_menu
    elif "back" in text:
         # Special case: "back" in PIN menu should go to FF number menu
         if original_menu == ff_pin_menu:
             # This is tricky with voice, maybe just map to '0' on main?
             digit_to_press = "0" # Map to '0' on the PIN menu (which goes back to main)
             menu_to_use = original_menu
         elif original_menu != "main":
            digit_to_press = "0"
            menu_to_use = original_menu

    # === 2b. If NO global command, check for LOCAL commands ===
    if digit_to_press is None:
        if original_menu == "main":
            if "status" in text: digit_to_press = "1"
            elif "manage" in text or "cancel" in text or "change" in text: digit_to_press = "2"
            elif "baggage" in text or "bag" in text: digit_to_press = "3"
            elif "check in" in text or "boarding pass" in text: digit_to_press = "4"
            elif "booking" in text or "book" in text: digit_to_press = "5"
            elif "frequent" in text or "points" in text: digit_to_press = "6" # Map "points" here
            elif "special" in text or "wheelchair" in text: digit_to_press = "7"
            elif "refund" in text or "receipt" in text: digit_to_press = "8"
            elif "other" in text or "pet" in text: digit_to_press = "9"

        elif original_menu == "manage_booking_options":
            if "change" in text: digit_to_press = "1"
            elif "cancel" in text: digit_to_press = "2"

        elif original_menu == "booking":
            if "domestic" in text: digit_to_press = "1"
            elif "international" in text: digit_to_press = "2"
        elif original_menu == "baggage":
            if "lost" in text: digit_to_press = "1"
            elif "allowance" in text: digit_to_press = "2"
        elif original_menu == "check_in_options":
            if "check in" in text: digit_to_press = "1"
            elif "boarding pass" in text: digit_to_press = "2"
        # --- FIX: NLU for frequent_flyer_options ---
        elif original_menu == "frequent_flyer_options":
            if "check" in text or "points" in text: digit_to_press = "1"
            elif "redeem" in text: digit_to_press = "2"
        elif original_menu == "special_assistance":
            if "wheelchair" in text: digit_to_press = "1"
            elif "other" in text: digit_to_press = "2"
        elif original_menu == "refunds":
            if "status" in text: digit_to_press = "1"
            elif "receipt" in text: digit_to_press = "2"
        elif original_menu == "other_inquiries":
            if "pet" in text: digit_to_press = "1"
            elif "group" in text: digit_to_press = "2"

    # --- End NLU Simulation ---

    if digit_to_press:
        print(f"      NLU: Mapped text '{text}' to DTMF digit: {digit_to_press} (using menu: {menu_to_use})")
        dtmf_input = DTMFInput(
            call_id=call_id,
            digit=digit_to_press,
            current_menu=menu_to_use
        )
        return await handle_dtmf(dtmf_input)

    # If NLU fails completely
    print("      NLU: No intent or digit matched.")
    # Give specific prompt if in data collection mode
    prompt_msg = "I'm sorry, I didn't understand that. Please try again."
    if original_menu in pnr_input_menus:
        prompt_msg = "Sorry, I didn't catch that PNR. Please clearly say your 6-digit PNR."
    elif original_menu == ff_number_menu:
        prompt_msg = "Sorry, I didn't catch that. Please say your 9-digit Flying Returns number."
    elif original_menu == ff_pin_menu:
        prompt_msg = "Sorry, I didn't catch that PIN. Please say your 4-digit PIN."

    return {
        "status": "invalid",
        "prompt": prompt_msg,
        "current_menu": original_menu,
        "prompt_original": MENU_STRUCTURE[original_menu]["prompt"] # Send original too
    }

# ==========================================================
# ##### !!!!! UPDATED handle_dtmf !!!!! #####
# ==========================================================
@app.post("/ivr/dtmf")
async def handle_dtmf(input_data: DTMFInput):
    """
    Process DTMF key press (The Legacy System)
    """

    call_id = input_data.call_id
    digit = input_data.digit

    if call_id not in active_calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call = active_calls[call_id]
    current_menu = call["current_menu"] # User's actual current menu

    menu_name_from_input = input_data.current_menu # Menu context for this digit press

    print(f"\n🔢 DTMF INPUT: Call {call_id}, User's Menu: {current_menu}, Action Menu: {menu_name_from_input}, Digit: {digit}")

    menu = MENU_STRUCTURE.get(menu_name_from_input)
    if not menu:
        return {"error": "Invalid menu state"}

    # --- FIX: Unified input buffer logic ---
    input_required_menus = {
        "flight_status_pnr": 6,
        "manage_booking_pnr": 6,
        "check_in_pnr_for_checkin": 6,
        "check_in_pnr_for_boardingpass": 6,
        "frequent_flyer_number": 9,
        "frequent_flyer_pin": 4
    }
    required_length = input_required_menus.get(menu_name_from_input)

    if required_length and digit != "#" and digit != "0":
        call["input_buffer"] += digit
        buffer_content = call["input_buffer"]
        prompt_msg = f"You entered {digit}. Continue entering."
        if len(buffer_content) >= required_length:
             prompt_msg = f"You entered {digit}. Press hash to submit."

        return {
            "status": "collecting",
            "prompt": prompt_msg,
            "collected": buffer_content, # Show current buffer in UI maybe?
            "current_menu": menu_name_from_input
        }
    # --- End Fix ---

    if digit not in menu["options"]:
        invalid_menu_to_use = call["current_menu"]
        return {
            "status": "invalid",
            "prompt": "Invalid option. Please try again.",
            "current_menu": invalid_menu_to_use,
            "valid_options": list(MENU_STRUCTURE[invalid_menu_to_use]["options"].keys())
        }

    # Only log valid inputs
    call["inputs"].append(digit)

    option = menu["options"][digit]
    action = option["action"]
    message = option["message"]

    response = {
        "status": "processed",
        "message": message
    }

    # --- Helper function ---
    def end_call_logic(call_id_to_end, status_msg=""):
        if call_id_to_end in active_calls:
            call_to_end = active_calls[call_id_to_end]
            call_to_end["end_time"] = datetime.now().isoformat()
            if status_msg:
                call_to_end["inputs"].append(status_msg)
            call_history.append(call_to_end.copy())
            del active_calls[call_id_to_end]
    # --- End Helper ---

    # --- Helper function for PNR lookup ---
    def _find_pnr_info(pnr_to_find):
         return MOCK_PNR_DB.get(pnr_to_find.upper())
    # --- End Helper ---

    # --- Helper function for FF lookup ---
    def _find_ff_info(ff_num_to_find):
        return MOCK_FF_DB.get(ff_num_to_find)
    # --- End Helper ---

    # --- Shared logic for invalid input ---
    def _handle_invalid_input(error_message):
        call["input_buffer"] = "" # Clear buffer on error
        response["status"] = "invalid_input" # Custom status?
        response["message"] = error_message
        response["prompt"] = menu["prompt"] # Repeat current prompt
        response["current_menu"] = menu_name_from_input # Stay in same menu
        response["status"] = "processed" # Keep call alive
        return response
    # --- End Helper ---


    if action == "goto_menu":
        target_menu = option["target"]
        call["current_menu"] = target_menu
        call["menu_path"].append(target_menu)
        response["current_menu"] = target_menu
        response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]

        # Clear buffer if leaving an input menu
        if menu_name_from_input in input_required_menus:
             call["input_buffer"] = ""
        # Clear specific state if returning to main
        if target_menu == "main":
            call["active_pnr"] = None
            call["active_ff_number"] = None

    elif action == "end_call":
        response["status"] = "call_ended"
        response["call_action"] = "hangup"
        end_call_logic(call_id, f"Call ended with message: {message}")

    elif action == "transfer_agent":
        response["status"] = "transferring"
        response["call_action"] = "hangup"
        response["message"] = message
        end_call_logic(call_id, f"Transferred to agent: {message}")
        print(f"✅ ACTION: {action} - Sending 'transferring' signal to frontend.")
        return response

    elif action == "lookup_pnr_status":
        pnr = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr)

        if pnr_info:
            response["status"] = "pnr_found"
            response["pnr_info"] = pnr_info
            response["message"] = (
                f"Your PNR {pnr.upper()}: Flight {pnr_info['flight']} from {pnr_info['route']} is {pnr_info['status']}. "
                f"Scheduled time: {pnr_info['time']}. This call will now end."
            )
            response["call_action"] = "hangup"
            end_call_logic(call_id, f"Looked up PNR status: {pnr.upper()}")
        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr.upper()} was not found. Please try again.")

    elif action == "lookup_pnr_manage":
        pnr = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr)

        if pnr_info:
            if pnr_info["status"] == "Cancelled":
                 response["message"] = f"PNR {pnr.upper()} is already marked as Cancelled. Returning to main menu."
                 target_menu = "main"
                 call["active_pnr"] = None
            else:
                 call["active_pnr"] = pnr.upper()
                 target_menu = "manage_booking_options"

            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu

            if target_menu == "manage_booking_options":
                response["prompt"] = f"PNR {pnr.upper()} found. Say 'Change Flight' or 'Cancel Flight'. Or, Press 1 to Change. Press 2 to Cancel. Press 0 to go back."
            else:
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]

        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr.upper()} was not found. Please try again.")

    elif action == "lookup_pnr_checkin":
        pnr = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr)

        if pnr_info:
            if pnr_info["status"] == "Cancelled":
                 response["message"] = f"Cannot check in for cancelled PNR {pnr.upper()}. Returning to main menu."
                 target_menu = "main"
                 # Go back to main menu directly
                 call["current_menu"] = target_menu
                 call["menu_path"].append(target_menu)
                 response["current_menu"] = target_menu
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            else:
                response["status"] = "call_ended"
                response["message"] = f"Check-in successful for PNR {pnr.upper()}. A link has been sent to your phone. This call will now end."
                response["call_action"] = "hangup"
                end_call_logic(call_id, f"Checked in PNR: {pnr.upper()}")
        else:
            response = _handle_invalid_input(f"Sorry, PNR {pnr.upper()} was not found. Please try again.")

    elif action == "lookup_pnr_boardingpass":
        pnr = call["input_buffer"]
        call["input_buffer"] = ""
        pnr_info = _find_pnr_info(pnr)

        if pnr_info:
             if pnr_info["status"] == "Cancelled":
                 response["message"] = f"Cannot get boarding pass for cancelled PNR {pnr.upper()}. Returning to main menu."
                 target_menu = "main"
                 call["current_menu"] = target_menu
                 call["menu_path"].append(target_menu)
                 response["current_menu"] = target_menu
                 response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
             else:
                response["status"] = "call_ended"
                response["message"] = f"Your boarding pass for PNR {pnr.upper()} has been re-sent to your registered email. This call will now end."
                response["call_action"] = "hangup"
                end_call_logic(call_id, f"Sent boarding pass for PNR: {pnr.upper()}")
        else:
             response = _handle_invalid_input(f"Sorry, PNR {pnr.upper()} was not found. Please try again.")

    elif action == "cancel_flight":
        pnr_to_cancel = call.get("active_pnr")
        if pnr_to_cancel and pnr_to_cancel in MOCK_PNR_DB:

            if MOCK_PNR_DB[pnr_to_cancel]["status"] == "Cancelled":
                response["message"] = f"Your flight for PNR {pnr_to_cancel} is already cancelled. This call will now end."
            else:
                MOCK_PNR_DB[pnr_to_cancel]["status"] = "Cancelled"
                print(f"      *** PNR {pnr_to_cancel} STATUS UPDATED TO CANCELLED ***")
                response["message"] = f"Your flight for PNR {pnr_to_cancel} has been successfully cancelled. A confirmation email has been sent. This call will now end."

            response["status"] = "call_ended"
            response["call_action"] = "hangup"
            end_call_logic(call_id, f"Cancelled PNR: {pnr_to_cancel}")
        else:
            # Error case - shouldn't happen if lookup_pnr_manage worked
            response["message"] = "An error occurred finding your PNR. Returning to main menu."
            target_menu = "main"
            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu
            response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            call["active_pnr"] = None

    # --- FIX: Added Frequent Flyer Actions ---
    elif action == "lookup_ff_number":
        ff_number = call["input_buffer"]
        call["input_buffer"] = "" # Clear buffer
        ff_info = _find_ff_info(ff_number)

        if ff_info:
            call["active_ff_number"] = ff_number # Store for PIN check
            target_menu = "frequent_flyer_pin"
            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu
            response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            response["message"] = f"Account {ff_number} found for {ff_info['name']}." # Give confirmation
        else:
             response = _handle_invalid_input(f"Sorry, Flying Returns number {ff_number} was not found. Please try again.")

    elif action == "verify_ff_pin":
        pin_entered = call["input_buffer"]
        call["input_buffer"] = "" # Clear buffer
        active_ff = call.get("active_ff_number")
        ff_info = _find_ff_info(active_ff)

        if ff_info and ff_info["pin"] == pin_entered:
            target_menu = "frequent_flyer_options"
            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu
            response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            response["message"] = "PIN verified."
        else:
            # PIN incorrect, repeat PIN prompt but don't clear active_ff_number
            response = _handle_invalid_input(f"Sorry, that PIN is incorrect. Please try again.")

    elif action == "check_ff_points":
        active_ff = call.get("active_ff_number")
        ff_info = _find_ff_info(active_ff)
        if ff_info:
             points = ff_info["points"]
             response["status"] = "call_ended"
             response["message"] = f"Your Flying Returns balance for account {active_ff} is {points:,} points. This call will now end."
             response["call_action"] = "hangup"
             end_call_logic(call_id, f"Checked points for FF: {active_ff}")
        else:
             # Error case
            response["message"] = "An error occurred finding your account details. Returning to main menu."
            target_menu = "main"
            call["current_menu"] = target_menu
            call["menu_path"].append(target_menu)
            response["current_menu"] = target_menu
            response["prompt"] = MENU_STRUCTURE[target_menu]["prompt"]
            call["active_ff_number"] = None
    # --- End Fix ---

    # Only print action if it wasn't handled by return early (like transfer_agent)
    if response.get("status") != "transferring":
        print(f"✅ ACTION: {action} - {message}")

    return response


# ==================== end_call (Unchanged) ====================
@app.post("/ivr/end")
def end_call(request: CallEndRequest):
    """End call (user hung up)"""
    call_id = request.call_id
    if call_id in active_calls:
        call = active_calls[call_id]
        call["end_time"] = datetime.now().isoformat()
        call["message"] = "Call ended by user."
        call_history.append(call.copy())
        del active_calls[call_id]
        print(f"\n🚫 CALL ENDED BY USER: {call_id}")
        return {"status": "call_ended", "call_id": call_id}
    return {"status": "error", "message": "Call not found"}
