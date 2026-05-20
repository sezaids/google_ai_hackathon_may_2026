# 🤖 Hamdam (ہمدم) — AI Service Orchestrator

> **End-to-End Booking Lifecycle Automation for Lahore's Informal Economy**
>
> Book local plumbers, electricians, carpenters, painters, and appliance repair workers — using natural language in Roman Urdu, Urdu script, or English.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Environment Variables](#environment-variables)
- [Service Categories](#service-categories)
- [How the AI Works](#how-the-ai-works)
- [Offline Fallback System](#offline-fallback-system)
- [UI Design System](#ui-design-system)
- [Booking Lifecycle](#booking-lifecycle)

---

## Overview

**Hamdam** is a full-stack AI-powered service booking platform simulating a mobile app experience for Pakistani households. Users can have a natural conversation — in any mix of Roman Urdu, Urdu, or English — to find and book local home service workers.

The system uses **OpenAI GPT-4o-mini** as the primary intelligence layer for understanding multilingual intent, extracting entities (service type, time slot, name, phone number), and managing the full booking conversation. A robust **offline state machine** ensures the app keeps working even when the OpenAI API is unavailable.

---

## Features

- 🗣️ **Multilingual Chat** — Understands Roman Urdu, Urdu script, and English natively. No translation or pre-processing.
- 🤖 **Dual AI Agent System** — Primary OpenAI agentic loop with function-calling + offline keyword/regex fallback.
- ⚡ **Hard Timeout Protection** — `concurrent.futures` thread-level kill at 12s ensures the app never freezes, regardless of network state.
- 🔌 **Circuit Breaker** — After an OpenAI failure, skips all API calls for 60 seconds to prevent cascading hangs.
- 📱 **Mobile App Mockup UI** — Fully interactive smartphone frame UI with real-time chat.
- 📊 **Live Execution Trace Console** — See the AI's reasoning, actions, and observations in real time.
- 🔄 **Agent State Flow Visualizer** — Animated 5-step pipeline diagram that updates as booking progresses.
- 📅 **Booking Lifecycle Simulation** — Advance any booking through Pending → Confirmed → Dispatched → Completed.
- ♻️ **One-Tap Rebook** — Re-book a past worker from booking history with a single tap.
- 🌐 **Quick-Select Category Grid** — Instantly start a booking for any of the 5 service types.
- 📈 **Live Stats Chips** — Total orders and saved workers count, updated dynamically.
- 🔁 **Full System Reset** — Wipe all sessions and bookings with a single button.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI (Python) |
| **ASGI Server** | Uvicorn |
| **AI / NLU** | OpenAI GPT-4o-mini (function calling + JSON mode) |
| **HTTP Client** | httpx (via OpenAI SDK) |
| **Frontend** | Vanilla HTML5, CSS3, JavaScript (no framework) |
| **Fonts** | Google Fonts — Outfit + JetBrains Mono |
| **Environment** | python-dotenv |
| **Data Store** | In-memory MockDatabase (no external DB) |

---

## Project Structure

```
antigravity_mobile_app/
│
├── .env                        # Environment variables (OpenAI API key)
├── README.md                   # This file
│
├── backend/
│   ├── main.py                 # FastAPI app, routes, async timeout wrapper
│   ├── orchestrator.py         # AI agents, state machine, entity extraction
│   ├── mock_db.py              # In-memory provider & booking database
│   └── requirements.txt        # Python dependencies
│
└── frontend/
    ├── index.html              # App shell, semantic HTML, SEO meta tags
    ├── style.css               # Full design system — green dark theme
    └── app.js                  # All UI logic, event delegation, chat handler
```

---

## Architecture

```
Browser (frontend/)
    │
    │  POST /api/chat  { session_id, message }
    ▼
FastAPI (backend/main.py)
    │  asyncio.wait_for(..., timeout=20s)
    │  run_in_executor → background thread
    ▼
orchestrate_chat()  (backend/orchestrator.py)
    │
    ├─► OpenAI API available?
    │       YES → OpenAIAgent (GPT-4o-mini function calling)
    │               └── Hard 12s thread kill (concurrent.futures)
    │               └── On timeout/error → StateMachineAgent
    │
    └─► OpenAI unavailable / circuit tripped?
            → StateMachineAgent (offline, instant)
                └── extract_entities() → _extract_offline() fallback
```

### Agent Modes

| Mode | Description | Latency |
|---|---|---|
| **OpenAIAgent** | Full GPT-4o-mini with function-calling. Handles vague input, mid-flow switches, complex Urdu. | 2–12s |
| **StateMachineAgent** | Explicit state-driven flow. Uses `_extract_offline()` for entity extraction. | < 100ms |
| **Offline Extractor** | Pure regex + keyword matching for service, time slot, phone, and name. Zero network calls. | < 1ms |

---

## API Reference

### `POST /api/chat`
Send a user message and receive an AI response with reasoning trace.

**Request:**
```json
{
  "session_id": "sess-abc123",
  "message": "mujhe plumber chahiye"
}
```

**Response:**
```json
{
  "response": "**Kamran Ahmed** (1.2 km, 4.8★, 1200 PKR/hr)\n\nAvailable slots:\n1. **10:00 AM**\n2. **2:00 PM**\n\nKonsa time book karein ge?",
  "trace": [
    { "step": 1, "type": "THOUGHT", "message": "state=AWAITING_SERVICE lang=roman_ur" },
    { "step": 2, "type": "ACTION",  "message": "find_providers(service='Plumber')" },
    { "step": 3, "type": "OBSERVATION", "message": "2 providers found." }
  ]
}
```

---

### `GET /api/providers`
List all providers, optionally filtered by service.

```
GET /api/providers?service=Electrician
```

---

### `GET /api/bookings`
Get all active bookings.

---

### `POST /api/bookings/{booking_id}/simulate`
Advance a booking's status one step: `Pending → Confirmed → Dispatched → Completed`.

---

### `POST /api/reset`
Reset all bookings and restore provider slot availability.

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- `uv` or `pip` package manager
- OpenAI API key (get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys))

### 1. Clone / open the project
```
cd antigravity_mobile_app
```

### 2. Create a virtual environment
```bash
# Using uv (recommended)
uv venv .venv

# Or using standard Python
python -m venv .venv
```

### 3. Activate the environment
```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r backend/requirements.txt
```

---

## Running the App

```bash
# From the project root
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then open your browser at: **http://localhost:8000**

The FastAPI backend serves the frontend SPA directly — no separate frontend server needed.

---

## Environment Variables

Create or edit `.env` in the project root:

```env
# OpenAI API Key
# Get it from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-your-key-here
```

> **Note:** If `OPENAI_API_KEY` is empty or missing, the app automatically uses the offline `StateMachineAgent` — no errors, just instant keyword-based responses.

---

## Service Categories

| Category | Triggers (sample keywords) |
|---|---|
| **Plumber** | water, pipe, tap, leak, flush, toty, pani, nal, motor, drain |
| **Electrician** | bijli, fan, wiring, switch, socket, pankha, light, short circuit |
| **Carpenter** | wood, door, furniture, almari, darwaza, chabi, lock, sofa |
| **Painter** | paint, rang, deewar, wall, colour |
| **Appliance Repair** | AC, fridge, washing machine, oven, TV, microwave, compressor |

The AI understands semantic root cause — so "pani ata nahi" (water isn't coming) correctly maps to **Plumber**.

---

## How the AI Works

### Primary Path — OpenAIAgent
Uses GPT-4o-mini with **function calling** and three registered tools:

| Tool | Purpose |
|---|---|
| `find_providers` | Query the mock DB for providers by service, distance, rating |
| `get_provider_details` | Fetch full provider info by ID |
| `create_booking` | Create a confirmed booking and return a receipt |

The agent maintains a **conversation history** (last 6 messages / 3 turns) and drives the full booking flow autonomously.

### Entity Extraction — `extract_entities()`
A separate OpenAI call using **JSON mode** extracts structured data from each message:
```json
{
  "service_category": "Plumber",
  "time_slot": "10:00 AM",
  "user_name": "Zaid Sohail",
  "phone_number": "03124567890"
}
```

### Timeout Protection
Every OpenAI call is wrapped with `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=12.0)` + `shutdown(wait=False)`. This guarantees the stuck network thread is **abandoned immediately** at 12 seconds, regardless of what httpx or the OS socket layer is doing.

---

## Offline Fallback System

### Circuit Breaker
After any OpenAI error (timeout, connection, auth), OpenAI is marked as "down" for **60 seconds**. All calls during that window instantly use the offline agent — no waiting.

### Name Extraction (Two-Pass)
The offline extractor uses a two-pass strategy for name detection:

**Pass 1 — Formal patterns:**
```
"mera naam X"  /  "my name is X"  /  "naam hai X"  /  "I am X"
```

**Pass 2 — Residual extraction:**
Strip phone digits → strip Urdu/English fillers → treat remaining 1–4 alpha words as the name.

Examples:
| Input | Extracted Name |
|---|---|
| `zaid 03124567890` | `Zaid` |
| `Zaid sohail` | `Zaid Sohail` |
| `mera naam Ali hai` | `Ali` |
| `Zaid Sohail 03001234567` | `Zaid Sohail` |

---

## UI Design System

### Color Palette
| Token | Value | Usage |
|---|---|---|
| `--bg-app` | `#0E0F0C` | Page background |
| `--bg-card` | `rgba(22,51,0,0.45)` | Cards, containers |
| `--accent` | `#9FE870` | Buttons, highlights, glow |
| `--text-primary` | `#FFFFFF` | All body text |
| `--text-muted` | `#9CA3AF` | Labels, timestamps |
| Phone border / notch | `#163300` | Smartphone frame chrome |

### Typography
- **UI Font:** Outfit (300, 400, 500, 600, 700) — Google Fonts
- **Monospace:** JetBrains Mono (400, 500) — booking IDs, console logs

### Key Components
- **Smartphone Frame** — Full mobile mockup with notch, status bar, and scrollable content
- **Chat Bubbles** — Incoming (dark glass) / Outgoing (lime green gradient)
- **Trace Cards** — Color-coded by type: THOUGHT (indigo), ACTION (amber), OBSERVATION (emerald), REASONING (lime)
- **State Flow Diagram** — 5-node animated pipeline
- **History Cards** — Horizontal scroll with one-tap Rebook buttons
- **Stats Chips** — Total orders and saved workers counters

---

## Booking Lifecycle

```
User Message
    │
    ▼
[1] AWAITING_SERVICE
    → Detect service category
    → Query providers (sorted by rating, then distance)
    → Show top provider + available slots
    │
    ▼
[2] SELECTING_SLOT
    → Match user's time preference (even vague: "sham ko", "das baje")
    → Resolve AM/PM using current server time
    │
    ▼
[3] AWAITING_INFO
    → Extract full name + Pakistani phone number (03xxxxxxxxx)
    │
    ▼
[4] BOOKING CONFIRMED
    → Remove slot from provider availability
    → Generate unique Booking ID (BKG-XXXXXX)
    → Show formatted receipt with all details
    │
    ▼
[5] SIMULATION (optional)
    → Pending → Confirmed → Dispatched → Completed
    → Completed bookings move to History
```

---

## Provider Database

10 pre-seeded providers across 5 service categories, sorted by rating + proximity:

| # | Name | Service | Rating | Distance | Rate |
|---|---|---|---|---|---|
| 1 | Kamran Ahmed | Plumber | ⭐ 4.8 | 1.2 km | 1200 PKR/hr |
| 2 | Sajid Ali | Plumber | ⭐ 4.2 | 3.5 km | 1000 PKR/hr |
| 3 | Muhammad Arsalan | Electrician | ⭐ 4.9 | 0.8 km | 1500 PKR/hr |
| 4 | Zeeshan Khan | Electrician | ⭐ 4.5 | 2.1 km | 1100 PKR/hr |
| 5 | Tariq Mahmood | Carpenter | ⭐ 4.7 | 1.8 km | 1800 PKR/hr |
| 6 | Yasir Hussain | Carpenter | ⭐ 4.1 | 4.2 km | 1400 PKR/hr |
| 7 | Bilal Shah | Painter | ⭐ 4.6 | 2.7 km | 1000 PKR/hr |
| 8 | Imran Nazir | Painter | ⭐ 4.3 | 5.0 km | 900 PKR/hr |
| 9 | Rizwan Ahmed | Appliance Repair | ⭐ 4.8 | 1.5 km | 1600 PKR/hr |
| 10 | Fahad Mustafa | Appliance Repair | ⭐ 4.4 | 3.0 km | 1300 PKR/hr |

---

## Built With ❤️ by Zaid • 2026
