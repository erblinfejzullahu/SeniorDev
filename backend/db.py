# db.py
# Database layer — connected to real Supabase.

import os
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

USE_SUPABASE = True

if USE_SUPABASE:
    from supabase import create_client, Client
    supabase: Client = create_client(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY")
    )
    print(f"[DB] Connected to Supabase: {os.getenv('SUPABASE_URL')}")

_mock_reservations = []
_mock_callbacks = []


# ── SETTINGS (persistent config) ──────────────────────────────────

def get_admin_password() -> str:
    """
    Reads the admin password from the Supabase `settings` table.
    Falls back to ADMIN_PASSWORD in .env if the table is empty or unreachable.
    """
    if USE_SUPABASE:
        try:
            response = (
                supabase.table("settings")
                .select("value")
                .eq("key", "admin_password")
                .single()
                .execute()
            )
            if response.data:
                return response.data["value"]
        except Exception as e:
            print(f"[DB] Could not read admin password from settings: {e}")
    return os.getenv("ADMIN_PASSWORD", "admin123")


def set_admin_password(new_password: str) -> bool:
    """
    Persists a new admin password to the Supabase `settings` table.
    Uses upsert so the row is created on the first call.
    """
    if USE_SUPABASE:
        try:
            supabase.table("settings").upsert({
                "key": "admin_password",
                "value": new_password
            }).execute()
            print("[DB] Admin password updated in Supabase")
            return True
        except Exception as e:
            print(f"[DB ERROR] Could not save admin password: {e}")
            return False
    # Without Supabase there's nowhere to persist the change
    return False


# ── RESERVATIONS ──────────────────────────────────────────────────

def save_reservation(
    name: str,
    date: str,
    time: str,
    party_size: int,
    tables_needed: int,
    phone: str = "",
) -> dict:
    reservation_id = str(uuid.uuid4())
    if USE_SUPABASE:
        try:
            response = supabase.table("reservations").insert({
                "name": name,
                "date": date,
                "time": time,
                "party_size": party_size,
                "tables_needed": tables_needed,
                "phone": phone,
            }).execute()
            saved_id = response.data[0]["id"] if response.data else reservation_id
            print(f"[DB] Reservation saved: {name} | {phone} | {party_size} guests | {tables_needed} table(s) | {date} {time}")
            return {"success": True, "id": saved_id}
        except Exception as e:
            print(f"[DB ERROR] Failed to save reservation: {e}")
            return {"success": False}
    else:
        record = {
            "id": reservation_id, "name": name, "date": date,
            "time": time, "party_size": party_size,
            "tables_needed": tables_needed, "phone": phone,
            "created_at": datetime.now().isoformat()
        }
        _mock_reservations.append(record)
        return {"success": True, "id": reservation_id}


def get_all_reservations() -> list:
    if USE_SUPABASE:
        try:
            response = supabase.table("reservations").select("*").order("date").order("time").execute()
            return response.data
        except Exception as e:
            print(f"[DB ERROR] Failed to fetch reservations: {e}")
            return []
    return _mock_reservations


def delete_reservation(reservation_id: str) -> bool:
    if USE_SUPABASE:
        try:
            supabase.table("reservations").delete().eq("id", reservation_id).execute()
            print(f"[DB] Reservation deleted: {reservation_id}")
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to delete reservation: {e}")
            return False
    global _mock_reservations
    _mock_reservations = [r for r in _mock_reservations if r["id"] != reservation_id]
    return True


# ── CALLBACKS ─────────────────────────────────────────────────────

def save_callback_request(name: str, phone: str) -> dict:
    callback_id = str(uuid.uuid4())
    if USE_SUPABASE:
        try:
            response = supabase.table("callback_requests").insert({
                "name": name,
                "phone": phone,
                "status": "pending"
            }).execute()
            saved_id = response.data[0]["id"] if response.data else callback_id
            print(f"[DB] Callback saved: {name} | {phone}")
            return {"success": True, "id": saved_id}
        except Exception as e:
            print(f"[DB ERROR] Failed to save callback: {e}")
            return {"success": False}
    else:
        record = {
            "id": callback_id, "name": name, "phone": phone,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        _mock_callbacks.append(record)
        return {"success": True, "id": callback_id}


def get_all_callbacks() -> list:
    if USE_SUPABASE:
        try:
            response = supabase.table("callback_requests").select("*").order("created_at", desc=True).execute()
            return response.data
        except Exception as e:
            print(f"[DB ERROR] Failed to fetch callbacks: {e}")
            return []
    return _mock_callbacks


def mark_callback_done(callback_id: str) -> bool:
    if USE_SUPABASE:
        try:
            supabase.table("callback_requests").update({"status": "done"}).eq("id", callback_id).execute()
            print(f"[DB] Callback marked done: {callback_id}")
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to mark callback done: {e}")
            return False
    for c in _mock_callbacks:
        if c["id"] == callback_id:
            c["status"] = "done"
            return True
    return False
