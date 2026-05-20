"""backend/main.py — FastAPI application entrypoint."""
import os

# Load .env file automatically (OPENAI_API_KEY etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — set env vars manually

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.mock_db import db
from backend.orchestrator import orchestrate_chat

app = FastAPI(title="Hamdam AI Service Orchestrator", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

STATUS_ORDER = ["Pending", "Confirmed", "Dispatched", "Completed"]

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/api/chat")
async def chat(payload: ChatRequest):
    """Natural language chat → agent response + reasoning trace.

    orchestrate_chat() is synchronous (blocks on OpenAI HTTP calls).
    We run it in a thread-pool executor so Uvicorn's event loop stays
    free, then wrap with asyncio.wait_for to enforce a 35-second limit.
    On timeout we return 200 OK with a friendly retry message so the
    frontend can display it normally in the chat bubble.
    """
    import asyncio
    loop = asyncio.get_running_loop()
    try:
        text, trace = await asyncio.wait_for(
            loop.run_in_executor(None, orchestrate_chat, payload.session_id, payload.message),
            timeout=20.0
        )
        return {"response": text, "trace": trace}
    except asyncio.TimeoutError:
        print(f"[main.py][/api/chat] asyncio.TimeoutError after 35s for session={payload.session_id!r} msg={payload.message!r}", flush=True)
        return {
            "response": "⏱️ **OpenAI API abhi thora slow hai.** Apna message dobara bhejein — zyada tar 1-2 retry mein jawab aa jata hai!",
            "trace": [{"step": 1, "type": "THOUGHT", "message": "OpenAI API timeout after 35s. Asking user to retry."}]
        }
    except Exception as e:
        print(f"[main.py][/api/chat] EXCEPTION {type(e).__name__}: {e}", flush=True)
        return {
            "response": f"⚠️ Server error: {type(e).__name__}. Kripya dobara try karein.",
            "trace": [{"step": 1, "type": "THOUGHT", "message": f"Exception {type(e).__name__}: {e}"}]
        }


@app.get("/api/providers")
async def providers(service: str = None):
    """List providers, optionally filtered by service category."""
    return db.get_providers(service=service)


@app.get("/api/bookings")
async def bookings():
    """All active bookings."""
    return db.get_bookings()


@app.post("/api/bookings/{booking_id}/simulate")
async def simulate(booking_id: str):
    """Advance booking status: Pending → Confirmed → Dispatched → Completed."""
    b = next((x for x in db.get_bookings() if x["booking_id"] == booking_id), None)
    if not b:
        raise HTTPException(404, detail="Booking not found")
    idx = STATUS_ORDER.index(b["status"])
    if idx < len(STATUS_ORDER) - 1:
        nxt = STATUS_ORDER[idx + 1]
        return {"message": f"{b['status']} → {nxt}", "booking": db.update_booking_status(booking_id, nxt)}
    return {"message": "Already Completed", "booking": b}


@app.post("/api/reset")
async def reset():
    """Reset provider slots and booking history."""
    db.reset_db()
    return {"message": "Database reset to defaults"}


# Serve frontend SPA
_fe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
os.makedirs(_fe, exist_ok=True)
app.mount("/", StaticFiles(directory=_fe, html=True), name="frontend")
