# Task List — AI Service Orchestrator for Informal Economy
### Session: 99312d83 · Initial Full Build

---

## Phase 1 — Core Build
- `[x]` Set up dependencies and requirements
- `[x]` Implement mock database with providers & stateful bookings (`backend/mock_db.py`)
- `[x]` Build AI service orchestrator with bilingual Roman Urdu/Urdu/English parsing
        and multi-step reasoning trace (`backend/orchestrator.py`)
- `[x]` Create FastAPI application server and routes (`backend/main.py`)
- `[x]` Develop premium glassmorphic mobile mockup frontend:
  - `[x]` Design HTML structure (`frontend/index.html`)
  - `[x]` Establish styling tokens, sleek dark theme, glassmorphic layout,
          and micro-animations (`frontend/style.css`)
  - `[x]` Program interactive logic, mock trace queuing, category actions,
          and polling (`frontend/app.js`)
  - `[x]` Build personalized User Dashboard at the top of the main screen
          featuring scrollable booking history & stats chips
  - `[x]` Restructure frontend viewport component order to position
          "Your Active Booking" right under "Quick Search Services"
          and above "Main Chat History"
- `[x]` Perform manual & automated end-to-end verification

---

## Phase 2 — NLU & Typo-Robustness Refactoring
- `[x]` Refactor NLU Intent Parsing in Backend (`backend/orchestrator.py`)
  - `[x]` Add whole-string fuzzy fallback comparing query to standard categories
  - `[x]` Update Gemini system instructions with explicit typo and phonetic examples
  - `[x]` Enhance Gemini tool parameter descriptions to guide service category selection
- `[x]` Refactor Mock Database to accept fuzzy category queries (`backend/mock_db.py`)
  - `[x]` Implement robust `normalize_service` method inside `MockDatabase`
  - `[x]` Update `get_providers` to fuzzy-normalize `service` parameter
- `[x]` Verify mapping of typos via test suites and API endpoints

---

## Phase 3 — Contextual Time Resolution Refactoring
- `[x]` Refactor time extraction in orchestrator (`backend/orchestrator.py`)
  - `[x]` Update `extract_slot` to support vague inputs ("10 baje"/"10 bjy")
          and resolve AM/PM based on available slots & current time
  - `[x]` Refactor Gemini system prompt to guide smart time slot resolution
- `[x]` Write and run verification tests for vague time inputs

---

## Phase 4 — NLU Sub-services & Synonyms Refactoring
- `[x]` Refactor `detect_service` in `backend/orchestrator.py` to support
        multi-lingual household sub-services and synonyms
- `[x]` Update Gemini LLM prompt to map synonyms to canonical categories
        without fallback loops
- `[x]` Refactor `normalize_service` in `backend/mock_db.py` to match
        exact parsing order
- `[x]` Create and run comprehensive sub-services test suite
- `[x]` Create and run live API test suite

---

## Phase 5 — Dynamic Weighted Soft-Scoring NLU Refactoring
- `[x]` Completely remove all strict keyword lookup lists, regex-matching lists,
        and rigid if-else blocks from orchestrator intent detection (`detect_service`)
- `[x]` Completely remove all strict keyword lookup lists from database normalizer
        (`normalize_service`)
- `[x]` Rewrite `RealGeminiAgent` system instructions for full semantic autonomy
- `[x]` Implement dynamic token-level fuzzy soft-scoring concept domains with weights
        to prioritize specific appliance/component nouns over general symptoms/materials
        (resolves ties like "compressor leaks" → Appliance Repair vs Plumber)
- `[x]` Update test suites — 100% pass rate confirmed

---

## Phase 6 — Interactive Dashboard, Typography & UI Redesign
- `[x]` **Touchable Components & One-Tap Re-booking**:
  - `[x]` Wrap History Cards and Stats Chips inside interactive clickable widgets
  - `[x]` Set up event listener to inject `"Rebook [Worker] for [Service]"` into chat
  - `[x]` Build backend orchestrator re-booking interceptor in `orchestrate_chat`
          to bypass provider search and jump to `SELECTING_SLOT`
- `[x]` **Real-time History Synchronization**:
  - `[x]` Map history grid to `historyBookings` dynamic state store in `app.js`
  - `[x]` Wire active booking updates so Completed status auto-injects new history card
- `[x]` **Minimalistic Typography**:
  - `[x]` Replace bulky Urdu title with clean minimalist capitalized **History** header
- `[x]` **Visual Redesign & Slate Color Palette**:
  - `[x]` Deep Charcoal (`#121214`) background, Dark Slate (`#1E1E24`) cards
  - `[x]` Modern border-radius (12px–20px), internal border drop-shadows
  - `[x]` High-contrast fonts, neon/teal accents, emerald completed status badges

---

## Phase 7 — Full Green Theme Color Palette Overhaul
- `[x]` **Color Palette Overhaul**:
  - `[x]` Remove pure black. Implement Deep Green `#163300` & Charcoal `#0E0F0C`
  - `[x]` Set Vibrant Lime Green `#9FE870` as primary accent
  - `[x]` White `#FFFFFF` for crisp readable text
- `[x]` **Rebook Button**:
  - `[x]` Remove click interaction from entire card body
  - `[x]` Create distinct styled "Rebook" button on far right with lime green border
  - `[x]` Restructure layout horizontally (flex-direction: row)
- `[x]` **Simplified Welcome Message**:
  - `[x]` Set to: *"Assalam-o-Alaikum! Main aap ka digital helper."*
