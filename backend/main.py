# main.py
# FastAPI server — run with: uvicorn main:app --reload --port 8001

import os
import io
import uuid
import secrets
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("OPENAI_API_KEY")
print(f"[STARTUP] API key loaded: {'YES' if api_key else 'NO - KEY NOT FOUND'}")

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from openai import OpenAI

import assistant
import db

app = FastAPI(title="Bella Vista AI Receptionist", version="1.0.0")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── ADMIN AUTH ────────────────────────────────────────────────────
_admin_tokens: set[str] = set()
_bearer = HTTPBearer()


def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if credentials.credentials not in _admin_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")


# ── REQUEST / RESPONSE MODELS ─────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

class ChatResponse(BaseModel):
    reply: str
    session_id: str

class TTSRequest(BaseModel):
    text: str

class AdminLoginRequest(BaseModel):
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── CUSTOMER ENDPOINTS ────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Bella Vista AI is online"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        reply = assistant.chat(session_id=session_id, user_message=request.message)
        return ChatResponse(reply=reply, session_id=session_id)
    except Exception as e:
        print(f"[ERROR] Chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = audio.filename or "recording.webm"
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        print(f"[STT] Transcribed: {transcription.text}")
        return {"text": transcription.text}
    except Exception as e:
        print(f"[ERROR] STT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/text-to-speech")
async def text_to_speech(request: TTSRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=request.text,
            speed=1.0
        )
        audio_bytes = response.read()
        audio_stream = io.BytesIO(audio_bytes)
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3"}
        )
    except Exception as e:
        print(f"[ERROR] TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    assistant.clear_session(session_id)
    return {"message": f"Session {session_id} cleared"}


# ── ADMIN AUTH ENDPOINTS ──────────────────────────────────────────

@app.post("/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Validates password against the DB (falls back to .env) and issues a Bearer token."""
    current_password = db.get_admin_password()
    if request.password != current_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = secrets.token_hex(32)
    _admin_tokens.add(token)
    print("[ADMIN] Login successful — token issued")
    return {"token": token}


@app.post("/admin/logout")
async def admin_logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    _admin_tokens.discard(credentials.credentials)
    return {"message": "Logged out"}


@app.patch("/admin/change-password", dependencies=[Depends(verify_admin)])
async def change_password(request: ChangePasswordRequest):
    """
    Verifies the current password, saves the new one to Supabase,
    then clears all active tokens — everyone must re-login.
    """
    current_password = db.get_admin_password()
    if request.current_password != current_password:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    success = db.set_admin_password(request.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="Could not save new password. Make sure the 'settings' table exists in Supabase.")

    _admin_tokens.clear()
    print("[ADMIN] Password changed — all tokens invalidated")
    return {"message": "Password updated successfully. Please log in again."}


# ── ADMIN DATA ENDPOINTS (all protected) ─────────────────────────

@app.get("/admin/reservations", dependencies=[Depends(verify_admin)])
async def get_reservations():
    try:
        return {"reservations": db.get_all_reservations()}
    except Exception as e:
        print(f"[ERROR] Get reservations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/callbacks", dependencies=[Depends(verify_admin)])
async def get_callbacks():
    try:
        return {"callbacks": db.get_all_callbacks()}
    except Exception as e:
        print(f"[ERROR] Get callbacks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/admin/callbacks/{callback_id}/done", dependencies=[Depends(verify_admin)])
async def mark_callback_done(callback_id: str):
    try:
        result = db.mark_callback_done(callback_id)
        if result:
            return {"message": "Callback marked as done"}
        raise HTTPException(status_code=404, detail="Callback not found")
    except Exception as e:
        print(f"[ERROR] Mark callback done: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/reservations/{reservation_id}", dependencies=[Depends(verify_admin)])
async def delete_reservation(reservation_id: str):
    try:
        result = db.delete_reservation(reservation_id)
        if result:
            return {"message": "Reservation deleted"}
        raise HTTPException(status_code=404, detail="Reservation not found")
    except Exception as e:
        print(f"[ERROR] Delete reservation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
