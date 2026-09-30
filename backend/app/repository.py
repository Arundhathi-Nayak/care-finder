"""ALL Firestore access lives here. Everything else depends on the Repository interface,
so tests can swap in an in-memory fake with set_repo()."""
import re
import threading
import time
from typing import Any, Protocol

from . import config


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class Repository(Protocol):
    def get_all_phcs(self) -> list[dict]: ...
    def get_phc(self, phc_id: str) -> dict | None: ...
    def get_inventory_for_phc(self, phc_id: str) -> list[dict]: ...
    def get_inventory_for_medicine(self, medicine_name: str) -> list[dict]: ...
    def get_all_inventory(self) -> list[dict]: ...
    def update_stock(self, phc_id: str, medicine_name: str, qty: int) -> None: ...
    def push_footfall(self, phc_id: str, count: int) -> None: ...
    def update_doctors_present(self, phc_id: str, present: bool) -> None: ...
    def add_report(self, phc_id: str, transcript: str, language: str, extracted: dict, source: str) -> str: ...
    def add_transfer(self, item: str, source_phc_id: str, target_phc_id: str, quantity: int,
                     brief: dict, source: str) -> str: ...
    def list_transfers(self, limit: int = 20) -> list[dict]: ...
    def count_transfers(self) -> int: ...


class _TTLCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < self.ttl:
                return hit[1]
        return None

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = (time.monotonic(), value)

    def clear(self):
        with self._lock:
            self._data.clear()


class FirestoreRepository:
    def __init__(self):
        from firebase_admin import firestore

        from .db import get_client

        self._fs = firestore
        self.db = get_client()
        self._cache = _TTLCache(config.CACHE_TTL_SECONDS)

    # ---------- converters ----------
    @staticmethod
    def _phc(doc) -> dict:
        d = doc.to_dict()
        loc = d.get("location")
        return {
            "phc_id": doc.id,
            "phc_name": d.get("phc_name", doc.id),
            "district": d.get("district", ""),
            "state": d.get("state", ""),
            "lat": loc.latitude if loc else 0.0,
            "lng": loc.longitude if loc else 0.0,
            "beds_available": int(d.get("beds_available", 0)),
            "beds_total": int(d.get("beds_total", 0)),
            "doctors_present": int(d.get("doctors_present", 0)),
            "doctors_total": int(d.get("doctors_total", 0)),
        }

    @staticmethod
    def _inv(doc) -> dict:
        d = doc.to_dict()
        return {
            "phc_id": d["phc_id"],
            "medicine_name": d["medicine_name"],
            "current_stock": int(d.get("current_stock", 0)),
            "footfall_history": [int(x) for x in d.get("footfall_history", [])],
        }

    # ---------- reads ----------
    def get_all_phcs(self) -> list[dict]:
        cached = self._cache.get("phcs")
        if cached is not None:
            return cached
        rows = [self._phc(d) for d in self.db.collection("phcs").stream()]
        rows.sort(key=lambda r: r["phc_id"])
        self._cache.set("phcs", rows)
        return rows

    def get_phc(self, phc_id: str) -> dict | None:
        doc = self.db.collection("phcs").document(phc_id).get()
        return self._phc(doc) if doc.exists else None

    def get_all_inventory(self) -> list[dict]:
        cached = self._cache.get("inventory")
        if cached is not None:
            return cached
        rows = [self._inv(d) for d in self.db.collection("inventory").stream()]
        self._cache.set("inventory", rows)
        return rows

    def get_inventory_for_phc(self, phc_id: str) -> list[dict]:
        docs = self.db.collection("inventory").where("phc_id", "==", phc_id).stream()
        return [self._inv(d) for d in docs]

    def get_inventory_for_medicine(self, medicine_name: str) -> list[dict]:
        docs = self.db.collection("inventory").where("medicine_name", "==", medicine_name).stream()
        return [self._inv(d) for d in docs]

    # ---------- writes (all invalidate the cache) ----------
    def update_stock(self, phc_id: str, medicine_name: str, qty: int) -> None:
        ref = self.db.collection("inventory").document(f"{phc_id}__{slugify(medicine_name)}")
        ref.update({"current_stock": int(qty), "updated_at": self._fs.SERVER_TIMESTAMP})
        self._cache.clear()

    def push_footfall(self, phc_id: str, count: int) -> None:
        batch = self.db.batch()
        for doc in self.db.collection("inventory").where("phc_id", "==", phc_id).stream():
            hist = [int(x) for x in doc.to_dict().get("footfall_history", [])]
            hist = (hist[1:] + [int(count)])[-7:]
            batch.update(doc.reference, {"footfall_history": hist, "updated_at": self._fs.SERVER_TIMESTAMP})
        batch.commit()
        self._cache.clear()

    def update_doctors_present(self, phc_id: str, present: bool) -> None:
        ref = self.db.collection("phcs").document(phc_id)
        snap = ref.get()
        if not snap.exists:
            return
        current = int(snap.to_dict().get("doctors_present", 0))
        new = max(current, 1) if present else 0
        ref.update({"doctors_present": new, "updated_at": self._fs.SERVER_TIMESTAMP})
        self._cache.clear()

    def add_report(self, phc_id, transcript, language, extracted, source) -> str:
        _, ref = self.db.collection("daily_reports").add({
            "phc_id": phc_id, "transcript": transcript, "language": language,
            "extracted": extracted, "source": source,
            "created_at": self._fs.SERVER_TIMESTAMP,
        })
        return ref.id

    def add_transfer(self, item, source_phc_id, target_phc_id, quantity, brief, source) -> str:
        _, ref = self.db.collection("transfers").add({
            "item": item, "source_phc_id": source_phc_id, "target_phc_id": target_phc_id,
            "quantity": int(quantity), "brief": brief, "source": source,
            "created_at": self._fs.SERVER_TIMESTAMP,
        })
        self._cache.clear()
        return ref.id

    def list_transfers(self, limit: int = 20) -> list[dict]:
        q = (self.db.collection("transfers")
             .order_by("created_at", direction=self._fs.Query.DESCENDING).limit(limit))
        out = []
        for doc in q.stream():
            d = doc.to_dict()
            ts = d.get("created_at")
            out.append({
                "id": doc.id, "item": d.get("item"),
                "source_phc_id": d.get("source_phc_id"), "target_phc_id": d.get("target_phc_id"),
                "quantity": int(d.get("quantity", 0)), "brief": d.get("brief", {}),
                "source": d.get("source", "mock"),
                "created_at": ts.isoformat() if ts else None,
            })
        return out

    def count_transfers(self) -> int:
        cached = self._cache.get("transfer_count")
        if cached is not None:
            return cached
        try:
            n = int(self.db.collection("transfers").count().get()[0][0].value)
        except Exception:
            n = sum(1 for _ in self.db.collection("transfers").stream())
        self._cache.set("transfer_count", n)
        return n


_repo: Repository | None = None


def get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = FirestoreRepository()
    return _repo


def set_repo(repo: Repository | None) -> None:
    """Test hook: install an in-memory fake (or None to reset)."""
    global _repo
    _repo = repo
