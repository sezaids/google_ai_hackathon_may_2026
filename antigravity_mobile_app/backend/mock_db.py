"""backend/mock_db.py — In-memory provider & booking store."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

INITIAL_PROVIDERS = [
    {"id": 1,  "name": "Kamran Ahmed",    "service": "Plumber",         "rating": 4.8, "distance_km": 1.2, "hourly_rate_pkr": 1200, "phone": "+92 300 1234567", "available_slots": ["10:00 AM", "2:00 PM", "4:00 PM"],           "completed_jobs": 42, "avatar": "👨‍🔧"},
    {"id": 2,  "name": "Sajid Ali",       "service": "Plumber",         "rating": 4.2, "distance_km": 3.5, "hourly_rate_pkr": 1000, "phone": "+92 312 9876543", "available_slots": ["11:00 AM", "3:00 PM"],                      "completed_jobs": 19, "avatar": "🔧"},
    {"id": 3,  "name": "Muhammad Arsalan","service": "Electrician",      "rating": 4.9, "distance_km": 0.8, "hourly_rate_pkr": 1500, "phone": "+92 333 4567890", "available_slots": ["09:00 AM", "12:00 PM", "05:00 PM"],          "completed_jobs": 88, "avatar": "⚡"},
    {"id": 4,  "name": "Zeeshan Khan",    "service": "Electrician",      "rating": 4.5, "distance_km": 2.1, "hourly_rate_pkr": 1100, "phone": "+92 321 6543210", "available_slots": ["02:00 PM", "04:00 PM"],                      "completed_jobs": 31, "avatar": "💡"},
    {"id": 5,  "name": "Tariq Mahmood",   "service": "Carpenter",        "rating": 4.7, "distance_km": 1.8, "hourly_rate_pkr": 1800, "phone": "+92 345 5678901", "available_slots": ["10:00 AM", "01:00 PM", "06:00 PM"],          "completed_jobs": 55, "avatar": "🪓"},
    {"id": 6,  "name": "Yasir Hussain",   "service": "Carpenter",        "rating": 4.1, "distance_km": 4.2, "hourly_rate_pkr": 1400, "phone": "+92 301 7654321", "available_slots": ["11:00 AM", "03:00 PM"],                      "completed_jobs": 12, "avatar": "🪵"},
    {"id": 7,  "name": "Bilal Shah",      "service": "Painter",          "rating": 4.6, "distance_km": 2.7, "hourly_rate_pkr": 1000, "phone": "+92 315 2345678", "available_slots": ["08:00 AM", "02:00 PM", "05:00 PM"],          "completed_jobs": 27, "avatar": "🎨"},
    {"id": 8,  "name": "Imran Nazir",     "service": "Painter",          "rating": 4.3, "distance_km": 5.0, "hourly_rate_pkr": 900,  "phone": "+92 306 8765432", "available_slots": ["12:00 PM", "04:00 PM"],                      "completed_jobs": 15, "avatar": "🖌️"},
    {"id": 9,  "name": "Rizwan Ahmed",    "service": "Appliance Repair", "rating": 4.8, "distance_km": 1.5, "hourly_rate_pkr": 1600, "phone": "+92 334 3456789", "available_slots": ["10:00 AM", "01:00 PM", "03:00 PM", "05:00 PM"], "completed_jobs": 63, "avatar": "📺"},
    {"id": 10, "name": "Fahad Mustafa",   "service": "Appliance Repair", "rating": 4.4, "distance_km": 3.0, "hourly_rate_pkr": 1300, "phone": "+92 322 7654321", "available_slots": ["11:00 AM", "02:00 PM"],                      "completed_jobs": 22, "avatar": "🔌"},
]


class MockDatabase:
    def __init__(self):
        self.providers: List[Dict[str, Any]] = []
        self.bookings:  List[Dict[str, Any]] = []
        self.reset_db()

    def reset_db(self):
        self.providers = [dict(p) for p in INITIAL_PROVIDERS]
        self.bookings  = []

    def normalize_service(self, query: str) -> Optional[str]:
        """Delegates to OpenAI-powered detect_service() in orchestrator."""
        if not query:
            return None
        q = query.strip().lower()
        mapping = {
            "plumber": "Plumber",
            "electrician": "Electrician",
            "carpenter": "Carpenter",
            "painter": "Painter",
            "appliance repair": "Appliance Repair"
        }
        if q in mapping:
            return mapping[q]
        from backend.orchestrator import detect_service
        return detect_service(query)

    def get_providers(self, service: Optional[str] = None,
                      max_distance: Optional[float] = None,
                      min_rating:   Optional[float] = None) -> List[Dict[str, Any]]:
        results = self.providers
        if service:
            svc = self.normalize_service(service) or service
            results = [p for p in results if p["service"].lower() == svc.lower()]
        if max_distance is not None:
            results = [p for p in results if p["distance_km"] <= max_distance]
        if min_rating is not None:
            results = [p for p in results if p["rating"] >= min_rating]
        return sorted(results, key=lambda x: (-x["rating"], x["distance_km"]))

    def get_provider_by_id(self, pid: int) -> Optional[Dict[str, Any]]:
        return next((p for p in self.providers if p["id"] == pid), None)

    def create_booking(self, provider_id: int, customer_name: str,
                       customer_phone: str, slot: str) -> Optional[Dict[str, Any]]:
        p = self.get_provider_by_id(provider_id)
        if not p:
            return None
        if slot in p["available_slots"]:
            p["available_slots"].remove(slot)
        b = {
            "booking_id":     f"BKG-{uuid.uuid4().hex[:6].upper()}",
            "provider_id":    provider_id,
            "provider_name":  p["name"],
            "service":        p["service"],
            "customer_name":  customer_name,
            "customer_phone": customer_phone,
            "scheduled_slot": slot,
            "status":         "Pending",
            "avatar":         p["avatar"],
            "hourly_rate_pkr":p["hourly_rate_pkr"],
            "timestamp":      datetime.now().isoformat(),
        }
        self.bookings.append(b)
        return b

    def cancel_booking(self, booking_id: str) -> bool:
        for b in self.bookings:
            if b["booking_id"] == booking_id:
                p = self.get_provider_by_id(b["provider_id"])
                if p and b["scheduled_slot"] not in p["available_slots"]:
                    p["available_slots"].append(b["scheduled_slot"])
                    p["available_slots"].sort()
                self.bookings.remove(b)
                return True
        return False

    def update_booking_status(self, booking_id: str, status: str) -> Optional[Dict[str, Any]]:
        if status not in ("Pending", "Confirmed", "Dispatched", "Completed"):
            return None
        for b in self.bookings:
            if b["booking_id"] == booking_id:
                b["status"] = status
                return b
        return None

    def get_bookings(self) -> List[Dict[str, Any]]:
        return self.bookings


db = MockDatabase()
