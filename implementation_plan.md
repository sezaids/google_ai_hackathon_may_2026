# Implementation Plan — Fully Dynamic Gemini NLU Routing
### Session: 99312d83 · AI Service Orchestrator App (Initial Build)

This plan outlines the steps to completely remove strict keyword lookup,
string-matching lists, and rigid if-else blocks for intent classification,
transitioning to a fully dynamic LLM semantic analyzer.

---

## User Review Required

> [!IMPORTANT]
> **1. Gemini Full Semantic Autonomy Prompt**
> - Rewrite the `RealGeminiAgent` system prompt with smart contextual analyzer rules:
>   - Water, pipes, motors, taps, leakages, tanks → `'Plumber'`
>   - Fans, lights, wiring, short circuits, switchboards → `'Electrician'`
>   - Furniture, doors, locks, wooden items → `'Carpenter'`
>   - Refrigerators, ACs, washing machines → `'Appliance Repair'`
>   - LLM must force-map any natural language description to a target category
>     and immediately call `find_providers`. No fallback unless complete gibberish.
>
> **2. Clean LLM-Powered Backend Classifier**
> - In `detect_service` and `db.normalize_service`, completely remove the large
>   `SEMANTIC_DOMAINS` keyword lookup dictionary.
> - If `GEMINI_API_KEY` present → dynamically invoke Gemini to classify input.
> - If absent (offline) → fall back to a dynamic soft-matching concept similarity
>   matcher so offline tests pass without an API key.

---

## Proposed Changes

### Backend Components

---

#### [MODIFY] [orchestrator.py](file:///c:/Users/zaids/Desktop/antigravity_mobile_app/backend/orchestrator.py)
1. **Remove hardcoded `SEMANTIC_DOMAINS`** from the main path.
2. **Rewrite `detect_service`**:
   - Check if `GEMINI_API_KEY` is in `os.environ`. If so, invoke the Gemini API
     with a structured single-word classification prompt.
   - If not present, use a clean simulated soft-matching concept scorer strictly
     for offline test support.
3. **Rewrite `RealGeminiAgent` system instruction**:
   - Give Gemini full semantic autonomy.
   - Dynamic evaluation and mapping instructions for Pakistani household problems
     in Roman Urdu, Urdu, and English.
   - Mandate force-mapping into Plumber, Electrician, Carpenter, or Appliance Repair
     and immediate tool invocation.

---

#### [MODIFY] [mock_db.py](file:///c:/Users/zaids/Desktop/antigravity_mobile_app/backend/mock_db.py)
1. **Remove hardcoded `SEMANTIC_DOMAINS`** from `normalize_service`.
2. **Synchronize `normalize_service` with `detect_service`**:
   - If `GEMINI_API_KEY` present → dynamically call Gemini to normalize input.
   - If not present → fall back to the same offline soft-matching similarity logic.

---

## Verification Plan

### Automated Tests
1. **Offline Unit Tests**:
```powershell
.\.venv\Scripts\python.exe scratch/test_subservices.py
.\.venv\Scripts\python.exe scratch/test_typos.py
```

2. **Live API Tests**:
```powershell
.\.venv\Scripts\python.exe scratch/test_subservices_api.py
.\.venv\Scripts\python.exe scratch/test_typos_api.py
```
