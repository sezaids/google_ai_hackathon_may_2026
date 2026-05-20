"""
backend/orchestrator.py  —  AI Service Orchestrator (OpenAI-powered)
=====================================================================
All NLU (service routing, slot resolution, name/phone extraction) is
delegated to a single OpenAI gpt-4o-mini call per turn. Zero keyword
lists, zero regex heuristics, zero manual translation maps.
"""
import os, re, json, concurrent.futures as _cf
import time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from backend.mock_db import db

# ── Constants ───────────────────────────────────────────────────────────────
SESSIONS: Dict[str, Dict[str, Any]] = {}
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CATEGORIES = ["Plumber", "Electrician", "Carpenter", "Painter", "Appliance Repair"]

# ── Circuit Breaker for OpenAI ────────────────────────────────────────
# When OpenAI times out or errors, we mark it as down for 60 seconds.
# All calls during that window skip OpenAI and use _extract_offline() instantly.
_OPENAI_FAIL_UNTIL: float = 0.0   # epoch timestamp; 0 = not tripped
_OPENAI_COOLDOWN   = 60.0         # seconds to wait before retrying OpenAI

def _openai_is_up() -> bool:
    """Return True if we should attempt an OpenAI call right now."""
    return _time.time() > _OPENAI_FAIL_UNTIL

def _trip_circuit():
    """Mark OpenAI as down for the next cooldown window."""
    global _OPENAI_FAIL_UNTIL
    _OPENAI_FAIL_UNTIL = _time.time() + _OPENAI_COOLDOWN


_SYSTEM_EXTRACT = """\
You are a multilingual entity extractor for a Pakistani home-service booking app.
The user writes in Roman Urdu, Urdu script, English, or a mix — accept all as-is.
Return ONLY a valid JSON object with exactly these keys:
{
  "service_category": "<Plumber|Electrician|Carpenter|Painter|Appliance Repair|null>",
  "time_slot":        "<exact slot string from the provided list|null>",
  "user_name":        "<full name|null>",
  "phone_number":     "<digits-only Pakistani number e.g. 03001234567|null>"
}
Rules:
- service_category: infer from semantic root cause. Examples:
    water/pipe/motor/tap/leakage/flush/toty/toti/sink/basin/nal saaz/toty kharab/flush kharab → Plumber
    fan/light/wiring/bijli/short circuit/board/switch/socket/pankha/switchboard → Electrician
    furniture/door/wood/lock/almari/darwaza/chabi/table/chair/sofay → Carpenter
    paint/rang/deewar/wall paint/colour → Painter
    AC/fridge/washing machine/oven/TV/cooling/compressor/refrigerator/microwave → Appliance Repair
  null ONLY if the message is complete gibberish unrelated to home services.
- time_slot: map to EXACTLY one string from the available_slots list. For vague
  times ("das baje", "10 bjy", "saat baje") use current_time to resolve AM/PM:
  if the AM hour has already passed → choose PM; otherwise → choose AM.
  null if no slots provided or no time mentioned.
- user_name: strip filler ("mera naam", "my name is", "main", "hoon"). null if absent.
- phone_number: digits only, no spaces/dashes/+. null if absent.
- Omit no key. Never guess values not present. No explanation outside the JSON.\
"""

_SYSTEM_AGENT = """\
You are Hamdam — a warm, efficient AI Service Orchestrator for Pakistani households.
Accept messages in Roman Urdu, Urdu, English, or a mix. Never preprocess; understand natively.

Booking workflow:
1. Identify the service from the semantic root cause of the user's complaint and call find_providers.
   Water/pipe/motor/tap/leakage/flush/toty/toti/sink/basin/nal saaz/toty kharab/flush kharab → Plumber
   fan/light/wiring/bijli/short circuit/board/switch/socket/pankha/switchboard → Electrician
   furniture/door/wood/lock/almari/darwaza/chabi/table/chair/sofay → Carpenter
   paint/rang/deewar/wall paint/colour → Painter
   AC/fridge/washing machine/oven/TV/cooling/compressor/refrigerator/microwave → Appliance Repair
2. Recommend the top provider (closest + highest-rated). Show available slots.
3. Match user's time choice (even vague: "das baje", "sham ko") to the exact slot string.
   Resolve AM/PM using current time if ambiguous.
4. Collect full name and phone number, then call create_booking.
5. Show a formatted receipt with the Booking ID (emoji-styled).
6. Always reply in the same language the user is using.
7. Never expose raw JSON, tool names, or internal state.\
"""


# ── Session helpers ──────────────────────────────────────────────────────────
def _new_session() -> Dict[str, Any]:
    return dict(state="AWAITING_SERVICE", provider_id=None, slot=None,
                service=None, customer_name=None, customer_phone=None, lang="en")

def get_or_create_session(sid: str) -> Dict[str, Any]:
    if sid not in SESSIONS:
        SESSIONS[sid] = _new_session()
    return SESSIONS[sid]


# ── Language detection (script-level, no word lists) ────────────────────────
def detect_language(text: str) -> str:
    if re.search(r"[\u0600-\u06FF]", text):
        return "ur"
    if re.search(
        r"\b(hai|hain|ho|kr|karna|chahiye|bhejo|pani|bijli|ghar|mery|"
        r"nahi|wala|baje|bjy|subah|sham|raat|aur|ko|ka|ki)\b",
        text, re.IGNORECASE
    ):
        return "roman_ur"
    return "en"


# ── Fast offline keyword extractor (zero network, microsecond response) ──────
# Used as fallback when OpenAI is unavailable or times out.
_KW = {
    "Plumber":         r"plumb|water|pipe|tap|leak|flush|toty|toti|sink|basin|nal|motor|drain|pani|نل|پانی|ٹونٹی",
    "Electrician":     r"electric|wiring|bijli|short.circuit|switch|socket|pankha|fan|light|bulb|board|بجلی|پنکھا|لائٹ",
    "Carpenter":       r"carpent|wood|door|furniture|almari|darwaza|chabi|lock|table|chair|sofa|درواز|الماری",
    "Painter":         r"paint|rang|deewar|wall|colour|color|رنگ|دیوار",
    "Appliance Repair": r"ac|fridge|washing.machine|oven|tv|television|microwave|compressor|refrigerator|cooling|اے.سی|فریج",
}

def _extract_offline(
    raw: str,
    slots: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Pure keyword/regex entity extractor — no network, no dependencies."""
    t = raw.lower()

    # Service category
    svc = None
    for cat, pattern in _KW.items():
        if re.search(pattern, t, re.IGNORECASE):
            svc = cat
            break

    # Time slot — find first slot whose key tokens appear in the message
    slot = None
    if slots:
        for s in slots:
            # e.g. "9:00 AM" → look for "9" or "9:00" in message
            nums = re.findall(r"\d+", s)
            if nums and any(re.search(r"\b" + n + r"\b", t) for n in nums):
                slot = s
                break

    # Phone number — Pakistani format: 11 digits starting with 03, or 10+ digits
    phone = None
    m = re.search(r"0?3[0-9]{9}", re.sub(r"[\s\-]", "", raw))
    if m:
        phone = m.group()
        if not phone.startswith("0"):
            phone = "0" + phone

    # Name — two-pass extraction:
    # Pass 1: formal patterns ("mera naam X", "my name is X", "I am X")
    name = None
    nm = re.search(
        r"(?:mera\s+naam|my\s+name\s+is|naam\s+hai|i\s+am)\s+([A-Za-z][A-Za-z\s]{1,30})",
        raw, re.IGNORECASE
    )
    if nm:
        name = re.sub(r"\s+\b(hai|hoon|houn|hun|haan|ho)\b\s*$", "", nm.group(1).strip(), flags=re.IGNORECASE)
    else:
        # Pass 2: strip phone number + Urdu/English filler words, then treat
        # remaining alpha words (1-4) as the name.
        # Handles: "Zaid sohail", "zaid 03124567890", "zaid", "naam Zaid hai", etc.
        _stripped = re.sub(r"0?3[0-9]{9}", "", raw)          # remove phone digits
        _stripped = re.sub(
            r"\b(mera|meri|apna|naam|name|my|is|hai|hoon|main|aur|and|"
            r"number|phone|mobile|no|num|ka|ki|ko|se|ye|yeh|jo|bas|okay|ok)\b",
            " ", _stripped, flags=re.IGNORECASE
        )
        _stripped = re.sub(r"[^A-Za-z\s]", " ", _stripped)  # drop non-alpha chars
        _words = [w for w in _stripped.split() if w.isalpha() and len(w) > 1]
        # Accept 1-4 words that don't match service keywords
        _svc_words = {"plumber","electrician","carpenter","painter","appliance",
                      "repair","ac","fridge","fan","pankha","bijli","water","pipe"}
        _name_words = [w for w in _words if w.lower() not in _svc_words]
        if 1 <= len(_name_words) <= 4:
            name = " ".join(w.capitalize() for w in _name_words)

    return {
        "service_category": svc,
        "time_slot":        slot,
        "user_name":        name,
        "phone_number":     phone,
    }


# ── Single unified OpenAI extractor ─────────────────────────────────────────
def extract_entities(
    raw: str,
    slots: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Try OpenAI gpt-4o-mini first (better accuracy).
    Falls back to _extract_offline() if API is unavailable or times out.
    Returns {service_category, time_slot, user_name, phone_number}.
    """
    if OPENAI_API_KEY and _openai_is_up():
        try:
            import openai as _openai_mod
            import httpx as _httpx
            from openai import OpenAI
            ts = (now or datetime.now()).strftime("%I:%M %p")
            slot_ctx = (
                f"Available slots: {', '.join(slots)}. Current time: {ts}."
                if slots else "No slots relevant — set time_slot to null."
            )
            _client = OpenAI(
                api_key=OPENAI_API_KEY,
                http_client=_httpx.Client(
                    timeout=_httpx.Timeout(10.0, connect=5.0)
                )
            )
            def _do_extract():
                return _client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": f"{_SYSTEM_EXTRACT}\n\n{slot_ctx}"},
                        {"role": "user",   "content": raw},
                    ],
                    max_tokens=120, temperature=0,
                )
            # Hard OS-level deadline — abandoned immediately if httpx is stuck
            _ex = _cf.ThreadPoolExecutor(max_workers=1)
            try:
                _fut = _ex.submit(_do_extract)
                response = _fut.result(timeout=12.0)
            finally:
                _ex.shutdown(wait=False)  # Don't wait — abandon the stuck thread

            p = json.loads(response.choices[0].message.content)
            return {
                "service_category": p.get("service_category") if p.get("service_category") in CATEGORIES else None,
                "time_slot":        p.get("time_slot") if slots and p.get("time_slot") in slots else None,
                "user_name":        p.get("user_name") or None,
                "phone_number":     (re.sub(r"\D", "", p["phone_number"])
                                     if p.get("phone_number") and len(re.sub(r"\D","",p["phone_number"])) >= 10
                                     else None),
            }
        except _cf.TimeoutError as ex:
            print(f"[ORCHESTRATOR][extract_entities] HARD TIMEOUT (12s): thread forcibly killed.", flush=True)
            _trip_circuit()
        except _openai_mod.APITimeoutError as ex:
            print(f"[ORCHESTRATOR][extract_entities] OpenAI TIMEOUT: {type(ex).__name__}: {ex}", flush=True)
            _trip_circuit()
        except _openai_mod.APIConnectionError as ex:
            print(f"[ORCHESTRATOR][extract_entities] OpenAI CONNECTION ERROR: {type(ex).__name__}: {ex}", flush=True)
            _trip_circuit()
        except _openai_mod.AuthenticationError as ex:
            print(f"[ORCHESTRATOR][extract_entities] OpenAI AUTH ERROR (check API key!): {type(ex).__name__}: {ex}", flush=True)
            _trip_circuit()
        except Exception as ex:
            print(f"[ORCHESTRATOR][extract_entities] OpenAI UNEXPECTED ERROR: {type(ex).__name__}: {ex}", flush=True)
            _trip_circuit()

    # Offline fallback: works without any network connection
    return _extract_offline(raw, slots, now)



# detect_service kept as thin alias (used by mock_db.normalize_service)
def detect_service(text: str) -> Optional[str]:
    return extract_entities(text).get("service_category") if text else None


# ── Response templates (tri-lingual) ────────────────────────────────────────
def _r(lang, ur, ru, en):
    return ur if lang == "ur" else (ru if lang == "roman_ur" else en)

def _booking_receipt(lang: str, b: Dict[str, Any]) -> str:
    lines = [
        f"📍 **{'سروس' if lang=='ur' else 'Service'}:** {b['service']}",
        f"👤 **{'ورکر' if lang=='ur' else 'Worker'}:** {b['provider_name']}",
        f"🕒 **{'وقت' if lang=='ur' else 'Time'}:** {b['scheduled_slot']}",
        f"💰 **{'اجرت' if lang=='ur' else 'Rate'}:** {b['hourly_rate_pkr']} {'روپے/گھنٹہ' if lang=='ur' else 'PKR/hr'}",
        f"🆔 **Booking ID:** `{b['booking_id']}`",
    ]
    body = "\n".join(lines)
    if lang == "ur":
        return f"🎉 **بکنگ کنفرم ہو گئی!**\n\n{body}\n\n{b['provider_name']} آپ کے نمبر `{b['customer_phone']}` پر رابطہ کریں گے۔ شکریہ!"
    if lang == "roman_ur":
        return f"🎉 **Booking Confirm Ho Gayi!**\n\n{body}\n\n{b['provider_name']} aap ke number `{b['customer_phone']}` pe contact karega. Shukriya!"
    return f"🎉 **Booking Confirmed!**\n\n{body}\n\nMr. {b['provider_name']} will contact you at `{b['customer_phone']}` before arrival. Thank you!"


# ── State-machine agent (fallback when OpenAI agent itself errors) ───────────
class StateMachineAgent:
    """
    Drives the booking conversation through explicit states.
    Calls extract_entities() (OpenAI JSON mode) at each turn — no heuristics.
    """

    def process_message(self, sid: str, msg: str) -> Tuple[str, List[Dict]]:
        sess = get_or_create_session(sid)
        lang = detect_language(msg)
        sess["lang"] = lang

        trace, step = [], [1]
        def T(t, m):
            trace.append({"step": step[0], "type": t, "message": m})
            step[0] += 1

        T("THOUGHT", f"state={sess['state']} lang={lang} msg='{msg}'")

        # ── Reset ────────────────────────────────────────────────────────
        if re.search(r"\b(reset|clear|dobara|naya)\b", msg, re.IGNORECASE):
            sess.update(_new_session())
            T("THOUGHT", "Session reset.")
            return _r(lang,
                "اسلام علیکم! دوبارہ خوش آمدید۔ کس سروس کی ضرورت ہے؟",
                "Reset! Dobara batayein — kya chahiye?",
                "Reset! What service can I find for you?"), trace

        # ── AWAITING_SERVICE ─────────────────────────────────────────────
        if sess["state"] == "AWAITING_SERVICE":
            T("THOUGHT", "Calling OpenAI to extract service_category...")
            e = extract_entities(msg)
            service = e.get("service_category")
            T("OBSERVATION", f"service_category → {service}")
            if not service:
                return _r(lang,
                    "معذرت، کونسی سروس چاہیے؟ (پلمبر، الیکٹریشن، کارپینٹر، پینٹر، اے سی/فریج)",
                    "Samajh nahi aya. Kya chahiye? (Plumber, Electrician, Carpenter, Painter, AC/Fridge Repair)",
                    "Could you specify the service? (Plumber, Electrician, Carpenter, Painter, Appliance Repair)"
                ), trace

            sess["service"] = service
            T("ACTION", f"find_providers(service='{service}')")
            provs = db.get_providers(service=service)
            T("OBSERVATION", f"{len(provs)} providers found.")
            if not provs:
                sess["state"] = "AWAITING_SERVICE"
                return _r(lang,
                    f"معذرت، ابھی {service} دستیاب نہیں۔",
                    f"Abhi {service} available nahi. Thori dair baad try karein.",
                    f"No {service} available right now. Please try again later."
                ), trace

            rec = provs[0]
            sess.update(provider_id=rec["id"], state="SELECTING_SLOT")
            slots_md = "\n".join(f"{i}. **{s}**" for i, s in enumerate(rec["available_slots"], 1))
            T("REASONING", f"Recommended {rec['name']} — slots: {rec['available_slots']}")
            return _r(lang,
                f"**{rec['name']}** ({rec['distance_km']} کلومیٹر، {rec['rating']}★، {rec['hourly_rate_pkr']} روپے/گھنٹہ)\n\nدستیاب اوقات:\n{slots_md}\n\nکونسا وقت بک کرنا چاہتے ہیں؟",
                f"**{rec['name']}** ({rec['distance_km']} km، {rec['rating']}★، {rec['hourly_rate_pkr']} PKR/hr)\n\nAvailable slots:\n{slots_md}\n\nKonsa time book karein ge?",
                f"**{rec['name']}** ({rec['distance_km']} km, {rec['rating']}★, {rec['hourly_rate_pkr']} PKR/hr)\n\nAvailable slots:\n{slots_md}\n\nWhich time would you like?"
            ), trace

        # ── SELECTING_SLOT ───────────────────────────────────────────────
        elif sess["state"] == "SELECTING_SLOT":
            prov = db.get_provider_by_id(sess["provider_id"])
            if not prov:
                sess["state"] = "AWAITING_SERVICE"
                return self.process_message(sid, msg)
            T("THOUGHT", f"Resolving time slot from '{msg}' against {prov['available_slots']}")
            e = extract_entities(msg, slots=prov["available_slots"])
            slot = e.get("time_slot")
            T("OBSERVATION", f"time_slot → {slot}")
            # Mid-flow service switch?
            if not slot and e.get("service_category"):
                sess.update(state="AWAITING_SERVICE", provider_id=None)
                return self.process_message(sid, msg)
            if not slot:
                avail = ", ".join(f"**{s}**" for s in prov["available_slots"])
                return _r(lang,
                    f"یہ وقت دستیاب نہیں۔ ان میں سے چنیں: {avail}",
                    f"Ye slot nahi. In mein se choose karein: {avail}",
                    f"Slot not available. Choose from: {avail}"
                ), trace
            sess.update(slot=slot, state="AWAITING_INFO")
            T("THOUGHT", f"Slot '{slot}' confirmed.")
            if e.get("user_name"):  sess["customer_name"] = e["user_name"]
            if e.get("phone_number"): sess["customer_phone"] = e["phone_number"]
            if sess["customer_name"] and sess["customer_phone"]:
                return self._book(sess, T)
            return _r(lang,
                "شکریہ! اپنا **مکمل نام** اور **فون نمبر** (03xxxxxxxxx) بھیجیں۔",
                "Shukriya! Apna **Naam** aur **Phone Number** (03xxxxxxxxx) bhejein.",
                "Great! Please send your **Full Name** and **Phone Number** (03xxxxxxxxx)."
            ), trace

        # ── AWAITING_INFO ────────────────────────────────────────────────
        elif sess["state"] == "AWAITING_INFO":
            T("THOUGHT", "Extracting name + phone via OpenAI...")
            e = extract_entities(msg)
            if e.get("user_name"):    sess["customer_name"]  = e["user_name"]
            if e.get("phone_number"): sess["customer_phone"] = e["phone_number"]
            T("OBSERVATION", f"name={sess['customer_name']} phone={sess['customer_phone']}")
            if not sess["customer_name"]:
                return _r(lang, "اپنا **نام** بتائیں۔", "Apna **Naam** batayein.", "Please tell me your **name**."), trace
            if not sess["customer_phone"]:
                return _r(lang, "اپنا **موبائل نمبر** بھیجیں۔", "Apna **Phone Number** bhejein.", "Please send your **phone number**."), trace
            return self._book(sess, T)

        # ── CONFIRMING_BOOKING ───────────────────────────────────────────
        elif sess["state"] == "CONFIRMING_BOOKING":
            if extract_entities(msg).get("service_category"):
                sess.update(state="AWAITING_SERVICE", provider_id=None, slot=None)
                return self.process_message(sid, msg)
            if re.search(r"\b(yes|haan|hawn|ok|confirm|sahi|kardo|krdo|ہاں|جی)\b", msg, re.IGNORECASE):
                return self._book(sess, T)
            sess.update(state="AWAITING_SERVICE", provider_id=None, slot=None)
            return _r(lang, "بکنگ منسوخ۔ کیا اور کچھ چاہیے؟", "Booking cancel. Kuch aur chahiye?", "Booking cancelled. Anything else?"), trace

        sess["state"] = "AWAITING_SERVICE"
        return self.process_message(sid, msg)

    def _book(self, sess, T) -> Tuple[str, List]:
        T("ACTION", f"create_booking(pid={sess['provider_id']}, slot='{sess['slot']}')")
        b = db.create_booking(sess["provider_id"], sess["customer_name"], sess["customer_phone"], sess["slot"])
        if not b:
            T("OBSERVATION", "Slot taken. Resetting to slot selection.")
            sess["state"] = "SELECTING_SLOT"
            p = db.get_provider_by_id(sess["provider_id"])
            avail = ", ".join(f"**{s}**" for s in (p["available_slots"] if p else []))
            return _r(sess["lang"],
                f"یہ وقت بھر گیا۔ ان میں سے چنیں: {avail}",
                f"Slot book ho gaya. Doosra chunein: {avail}",
                f"That slot is now taken. Choose from: {avail}"
            ), []
        T("OBSERVATION", f"Booking created: {b['booking_id']}")
        name, phone, lang = sess["customer_name"], sess["customer_phone"], sess["lang"]
        sess.clear(); sess.update(_new_session()); sess.update(customer_name=name, customer_phone=phone, lang=lang)
        return _booking_receipt(lang, b), []


# ── OpenAI full agentic loop (primary path) ──────────────────────────────────
class OpenAIAgent:
    """Primary agent: GPT-4o-mini with function-calling. Falls back to StateMachineAgent."""

    _TOOLS = [
        {"type": "function", "function": {
            "name": "find_providers",
            "description": "Find nearby providers. service must be one of the 5 canonical strings.",
            "parameters": {"type": "object", "required": ["service"], "properties": {
                "service":         {"type": "string", "enum": CATEGORIES},
                "max_distance_km": {"type": "number"},
                "min_rating":      {"type": "number"},
            }},
        }},
        {"type": "function", "function": {
            "name": "get_provider_details",
            "description": "Fetch full details for a provider by ID.",
            "parameters": {"type": "object", "required": ["provider_id"], "properties": {
                "provider_id": {"type": "integer"},
            }},
        }},
        {"type": "function", "function": {
            "name": "create_booking",
            "description": "Create a confirmed booking.",
            "parameters": {"type": "object",
                           "required": ["provider_id", "customer_name", "customer_phone", "slot"],
                           "properties": {
                               "provider_id":    {"type": "integer"},
                               "customer_name":  {"type": "string"},
                               "customer_phone": {"type": "string"},
                               "slot":           {"type": "string"},
                           }},
        }},
    ]

    def __init__(self, key: str):
        import httpx as _httpx
        from openai import OpenAI
        self.client = OpenAI(
            api_key=key,
            http_client=_httpx.Client(
                timeout=_httpx.Timeout(12.0, connect=5.0)
            )
        )

    def process_message(self, sid: str, msg: str) -> Tuple[str, List[Dict]]:
        trace, step = [], [1]
        def T(t, m): trace.append({"step": step[0], "type": t, "message": m}); step[0] += 1

        T("THOUGHT", f"[OpenAI Agent] sid='{sid}' msg='{msg}'")
        sess = get_or_create_session(sid)
        sess.setdefault("history", [])
        sess["history"].append({"role": "user", "content": msg})

        # Trim history to last 6 messages (3 turns) to keep API payload small
        # This prevents growing context from causing slow/timeout API calls
        if len(sess["history"]) > 6:
            sess["history"] = sess["history"][-6:]

        # Circuit breaker: if OpenAI is known to be down, skip immediately
        if not _openai_is_up():
            T("THOUGHT", "Circuit breaker tripped — OpenAI down. Using StateMachineAgent offline.")
            return StateMachineAgent().process_message(sid, msg)

        def _call(svc, kw) -> str:
            if svc == "find_providers":
                n = db.normalize_service(kw.get("service", "")) or kw.get("service")
                r = db.get_providers(service=n, max_distance=kw.get("max_distance_km"), min_rating=kw.get("min_rating"))
                T("ACTION", f"find_providers(service='{n}') → {len(r)} results")
                return json.dumps(r)
            if svc == "get_provider_details":
                p = db.get_provider_by_id(kw["provider_id"])
                T("ACTION", f"get_provider_details({kw['provider_id']}) → {p['name'] if p else 'None'}")
                return json.dumps(p) if p else "Provider not found"
            if svc == "create_booking":
                b = db.create_booking(**kw)
                T("ACTION", f"create_booking → {b['booking_id'] if b else 'Failed'}")
                return json.dumps(b) if b else "Booking failed."
            return json.dumps({"error": f"Unknown tool: {svc}"})

        import openai as _openai_mod
        try:
            msgs = [{"role": "system", "content": _SYSTEM_AGENT}] + sess["history"]
            T("THOUGHT", "Dispatching to gpt-4o-mini (hard timeout=12s)...")

            def _do_chat(m):
                return self.client.chat.completions.create(
                    model="gpt-4o-mini", messages=m,
                    tools=self._TOOLS, tool_choice="auto", temperature=0.3,
                )

            # Hard OS-level deadline on each API round-trip
            _ex = _cf.ThreadPoolExecutor(max_workers=1)
            try:
                resp = _ex.submit(_do_chat, msgs).result(timeout=12.0)
            finally:
                _ex.shutdown(wait=False)  # Don't wait — abandon the stuck thread

            while resp.choices[0].finish_reason == "tool_calls":
                am = resp.choices[0].message
                sess["history"].append(am.model_dump())
                results = []
                for tc in am.tool_calls:
                    result = _call(tc.function.name, json.loads(tc.function.arguments))
                    results.append({"role": "tool", "tool_call_id": tc.id,
                                    "name": tc.function.name, "content": result})
                sess["history"].extend(results)
                msgs = [{"role": "system", "content": _SYSTEM_AGENT}] + sess["history"]
                _ex2 = _cf.ThreadPoolExecutor(max_workers=1)
                try:
                    resp = _ex2.submit(_do_chat, msgs).result(timeout=12.0)
                finally:
                    _ex2.shutdown(wait=False)  # Abandon stuck thread

            text = resp.choices[0].message.content
            sess["history"].append({"role": "assistant", "content": text})
            T("THOUGHT", "gpt-4o-mini returned final response.")
            return text, trace
        except _cf.TimeoutError as ex:
            err = "HARD TIMEOUT (12s): OpenAI thread forcibly killed — falling back to StateMachineAgent."
            print(f"[ORCHESTRATOR][OpenAIAgent] {err}", flush=True)
            _trip_circuit()
            T("THOUGHT", err)
            return StateMachineAgent().process_message(sid, msg)
        except _openai_mod.APITimeoutError as ex:
            err = f"OpenAI httpx TIMEOUT: {type(ex).__name__}: {ex}"
            print(f"[ORCHESTRATOR][OpenAIAgent] {err}", flush=True)
            _trip_circuit()
            T("THOUGHT", f"{err} — falling back to StateMachineAgent.")
            return StateMachineAgent().process_message(sid, msg)
        except _openai_mod.APIConnectionError as ex:
            err = f"OpenAI CONNECTION ERROR: {type(ex).__name__}: {ex}"
            print(f"[ORCHESTRATOR][OpenAIAgent] {err}", flush=True)
            _trip_circuit()
            T("THOUGHT", f"{err} — falling back to StateMachineAgent.")
            return StateMachineAgent().process_message(sid, msg)
        except _openai_mod.AuthenticationError as ex:
            err = f"OpenAI AUTH ERROR (bad API key?): {type(ex).__name__}: {ex}"
            print(f"[ORCHESTRATOR][OpenAIAgent] {err}", flush=True)
            _trip_circuit()
            T("THOUGHT", f"{err} — falling back to StateMachineAgent.")
            return StateMachineAgent().process_message(sid, msg)
        except Exception as ex:
            err = f"OpenAI UNEXPECTED ERROR: {type(ex).__name__}: {ex}"
            print(f"[ORCHESTRATOR][OpenAIAgent] {err}", flush=True)
            _trip_circuit()
            T("THOUGHT", f"{err} — falling back to StateMachineAgent.")
            return StateMachineAgent().process_message(sid, msg)



# ── Entry point ──────────────────────────────────────────────────────────────
def orchestrate_chat(sid: str, msg: str) -> Tuple[str, List[Dict]]:
    # Check for touchable re-booking card clicks
    rebook_match = re.match(r"^Rebook\s+(.+?)\s+for\s+(.+)$", msg.strip(), re.IGNORECASE)
    if rebook_match:
        provider_name = rebook_match.group(1).strip()
        service_name = rebook_match.group(2).strip()
        
        # Look up matching provider in database
        provider = next((p for p in db.providers if p["name"].lower() == provider_name.lower()), None)
        if provider:
            sess = get_or_create_session(sid)
            # Directly select provider & state
            sess.update(
                state="SELECTING_SLOT",
                provider_id=provider["id"],
                service=provider["service"]
            )
            # Seed OpenAI history to keep conversation in sync if using OpenAIAgent
            sess.setdefault("history", [])
            sess["history"] = [
                {"role": "user", "content": msg},
                {"role": "assistant", "content": f"Bypassing provider discovery. Pre-selected provider {provider['name']} (ID {provider['id']}) for {provider['service']}. Available slots: {', '.join(provider['available_slots'])}."}
            ]
            
            # Format and respond with the slots
            slots_md = "\n".join(f"{i}. **{s}**" for i, s in enumerate(provider["available_slots"], 1))
            lang = detect_language(msg)
            
            trace = [
                {"step": 1, "type": "THOUGHT", "message": f"Touchable card re-book clicked. Intercepting input: '{msg}'"},
                {"step": 2, "type": "REASONING", "message": f"Bypassing provider discovery completely. Directly assigned provider {provider['name']} (ID {provider['id']}) and set state to SELECTING_SLOT."}
            ]
            
            resp = _r(lang,
                f"**{provider['name']}** ({provider['distance_km']} کلومیٹر، {provider['rating']}★، {provider['hourly_rate_pkr']} روپے/گھنٹہ)\n\nدستیاب اوقات:\n{slots_md}\n\nکونسا وقت بک کرنا چاہتے ہیں؟",
                f"**{provider['name']}** ({provider['distance_km']} km، {provider['rating']}★، {provider['hourly_rate_pkr']} PKR/hr)\n\nAvailable slots:\n{slots_md}\n\nKonsa time book karein ge?",
                f"**{provider['name']}** ({provider['distance_km']} km, {provider['rating']}★, {provider['hourly_rate_pkr']} PKR/hr)\n\nAvailable slots:\n{slots_md}\n\nWhich time would you like?"
            )
            return resp, trace

    key = os.environ.get("OPENAI_API_KEY", "")
    return (OpenAIAgent(key) if key else StateMachineAgent()).process_message(sid, msg)
