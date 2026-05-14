# tools.py
# Tool definitions sent to OpenAI + the Python functions behind them.

import json
import math
from datetime import datetime, timedelta
from db import save_reservation, save_callback_request, get_all_reservations

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_business_info",
            "description": "Returns restaurant info: hours, location, services, menu highlights.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Checks if the restaurant has enough tables available for a given date, time and party size. Returns alternative times if the slot is full.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time in HH:MM 24h format"},
                    "party_size": {"type": "integer", "description": "Number of guests"}
                },
                "required": ["date", "time", "party_size"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_reservation",
            "description": "Creates a reservation after all details are confirmed and availability is checked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":       {"type": "string",  "description": "Full name of the guest"},
                    "phone":      {"type": "string",  "description": "Guest's phone number"},
                    "date":       {"type": "string",  "description": "Date in YYYY-MM-DD format"},
                    "time":       {"type": "string",  "description": "Time in HH:MM 24h format"},
                    "party_size": {"type": "integer", "description": "Number of guests"}
                },
                "required": ["name", "phone", "date", "time", "party_size"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_callback_request",
            "description": "Stores a callback request when a guest wants to be called back.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":  {"type": "string", "description": "Name of the person"},
                    "phone": {"type": "string", "description": "Phone number to call back"}
                },
                "required": ["name", "phone"]
            }
        }
    }
]

# ── RESTAURANT CONFIGURATION ──────────────────────────────────────
TOTAL_TABLES        = 5
SEATS_PER_TABLE     = 4
SLOT_DURATION_HOURS = 1

OPENING_HOURS = {
    0: None,                  # Monday — closed
    1: ("12:00", "22:00"),    # Tuesday
    2: ("12:00", "22:00"),    # Wednesday
    3: ("12:00", "22:00"),    # Thursday
    4: ("12:00", "23:00"),    # Friday
    5: ("11:00", "23:00"),    # Saturday
    6: ("11:00", "21:00"),    # Sunday
}


# ── TOOL FUNCTIONS ────────────────────────────────────────────────

def get_business_info() -> dict:
    return {
        "name": "Bella Vista Restaurant",
        "location": "Rruga e Dibres 42, Prishtine 10000, Kosovo",
        "phone": "+383 44 123 456",
        "email": "info@bellavista-ks.com",
        "hours": {
            "Monday": "Closed",
            "Tuesday-Thursday": "12:00 - 22:00",
            "Friday": "12:00 - 23:00",
            "Saturday": "11:00 - 23:00",
            "Sunday": "11:00 - 21:00"
        },
        "services": ["Dine-in", "Private events", "Takeaway", "Catering"],
        "menu_highlights": ["Homemade pasta", "Wood-fired pizza", "Fresh seafood"],
        "parking": "Free parking behind the restaurant",
        "capacity": f"{TOTAL_TABLES} tables, {TOTAL_TABLES * SEATS_PER_TABLE} guests maximum"
    }


def calculate_tables_needed(party_size: int) -> int:
    return math.ceil(party_size / SEATS_PER_TABLE)


def get_tables_used_in_slot(date: str, time: str, all_reservations: list) -> int:
    try:
        slot_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        slot_end = slot_start + timedelta(hours=SLOT_DURATION_HOURS)
        total_tables_used = 0

        for r in all_reservations:
            r_date = str(r.get("date", ""))
            r_time = str(r.get("time", ""))[:5]
            r_tables = int(r.get("tables_needed", 1))
            if not r_date or not r_time:
                continue
            try:
                r_start = datetime.strptime(f"{r_date} {r_time}", "%Y-%m-%d %H:%M")
                r_end = r_start + timedelta(hours=SLOT_DURATION_HOURS)
                if r_start < slot_end and r_end > slot_start:
                    total_tables_used += r_tables
            except ValueError:
                continue

        return total_tables_used
    except ValueError:
        return 0


def get_available_slots(date: str, requested_time: str, tables_needed: int, all_reservations: list) -> list:
    try:
        date_obj    = datetime.strptime(date, "%Y-%m-%d")
        hours       = OPENING_HOURS.get(date_obj.weekday())
        if not hours:
            return []

        open_time  = datetime.strptime(f"{date} {hours[0]}", "%Y-%m-%d %H:%M")
        close_time = datetime.strptime(f"{date} {hours[1]}", "%Y-%m-%d %H:%M")
        req_dt     = datetime.strptime(f"{date} {requested_time}", "%Y-%m-%d %H:%M")

        candidates = []
        current = open_time
        while current + timedelta(hours=SLOT_DURATION_HOURS) <= close_time:
            time_str = current.strftime("%H:%M")
            if time_str != requested_time:
                used = get_tables_used_in_slot(date, time_str, all_reservations)
                if (TOTAL_TABLES - used) >= tables_needed:
                    candidates.append((abs((current - req_dt).total_seconds()), time_str))
            current += timedelta(hours=SLOT_DURATION_HOURS)

        candidates.sort(key=lambda x: x[0])
        return [t for _, t in candidates[:3]]
    except ValueError:
        return []


def check_availability(date: str, time: str, party_size: int = 1) -> dict:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M")
    except ValueError:
        return {"available": False, "message": "Invalid date or time format."}

    tables_needed = calculate_tables_needed(party_size)
    all_reservations = get_all_reservations()
    tables_used = get_tables_used_in_slot(date, time, all_reservations)
    tables_free = TOTAL_TABLES - tables_used

    print(f"[AVAILABILITY] {date} {time} | Used: {tables_used}/{TOTAL_TABLES} | Needed: {tables_needed} | Free: {tables_free}")

    if tables_free >= tables_needed:
        return {
            "available": True,
            "date": date, "time": time,
            "party_size": party_size,
            "tables_needed": tables_needed,
            "tables_free": tables_free,
            "message": f"We have availability on {date} at {time} for {party_size} guests. That requires {tables_needed} table(s), and we have {tables_free} free."
        }

    alternatives = get_available_slots(date, time, tables_needed, all_reservations)
    if alternatives:
        return {
            "available": False,
            "date": date, "time": time,
            "tables_needed": tables_needed, "tables_free": tables_free,
            "alternative_times": alternatives,
            "message": f"Sorry, {time} on {date} does not have enough tables for {party_size} guests. The closest available times are: {', '.join(alternatives)}. Would any of these work?"
        }
    return {
        "available": False,
        "date": date, "time": time,
        "tables_needed": tables_needed, "tables_free": tables_free,
        "alternative_times": [],
        "message": f"Sorry, there are no available slots for {party_size} guests on {date}. Would you like to try a different date?"
    }


def create_reservation(name: str, phone: str, date: str, time: str, party_size: int) -> dict:
    max_guests = TOTAL_TABLES * SEATS_PER_TABLE
    if party_size < 1 or party_size > max_guests:
        return {"success": False, "message": f"Sorry, we can accommodate between 1 and {max_guests} guests maximum."}

    tables_needed    = calculate_tables_needed(party_size)
    all_reservations = get_all_reservations()
    tables_used      = get_tables_used_in_slot(date, time, all_reservations)
    tables_free      = TOTAL_TABLES - tables_used

    if tables_free < tables_needed:
        return {"success": False, "message": f"Sorry, {time} on {date} just became fully booked. Please choose another time."}

    result = save_reservation(
        name=name, phone=phone, date=date,
        time=time, party_size=party_size, tables_needed=tables_needed
    )

    if result["success"]:
        return {
            "success": True,
            "reservation_id": result.get("id"),
            "tables_reserved": tables_needed,
            "message": f"Reservation confirmed for {name}, {party_size} guests ({tables_needed} table(s)), on {date} at {time}. We look forward to seeing you!"
        }
    return {"success": False, "message": "Could not save reservation. Please try again."}


def create_callback_request(name: str, phone: str) -> dict:
    result = save_callback_request(name=name, phone=phone)
    if result["success"]:
        return {"success": True, "message": f"Callback noted for {name} at {phone}. We will call you soon!"}
    return {"success": False, "message": "Could not save callback. Please call us directly."}


# ── TOOL DISPATCHER ───────────────────────────────────────────────
def run_tool(tool_name: str, tool_args: dict) -> str:
    try:
        if tool_name == "get_business_info":
            result = get_business_info()
        elif tool_name == "check_availability":
            result = check_availability(
                date=tool_args.get("date", ""),
                time=tool_args.get("time", ""),
                party_size=int(tool_args.get("party_size", 1))
            )
        elif tool_name == "create_reservation":
            result = create_reservation(
                name=tool_args.get("name", ""),
                phone=tool_args.get("phone", ""),
                date=tool_args.get("date", ""),
                time=tool_args.get("time", ""),
                party_size=int(tool_args.get("party_size", 1))
            )
        elif tool_name == "create_callback_request":
            result = create_callback_request(
                name=tool_args.get("name", ""),
                phone=tool_args.get("phone", "")
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        print(f"[TOOL ERROR] {tool_name} failed: {e}")
        result = {"error": f"Tool {tool_name} encountered an error: {str(e)}"}

    return json.dumps(result)
