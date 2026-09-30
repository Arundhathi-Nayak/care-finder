"""In-memory Repository loaded from the real CSVs in data/."""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"


class FakeRepo:
    def __init__(self):
        phcs = pd.read_csv(DATA / "phc_directory.csv").to_dict("records")
        self.phcs = {p["phc_id"]: {k: (int(v) if k.startswith(("beds", "doctors")) else v) for k, v in p.items()} for p in phcs}
        self.inv = {}
        for r in pd.read_csv(DATA / "inventory_telemetry.csv").to_dict("records"):
            self.inv[(r["phc_id"], r["medicine_name"])] = {
                "phc_id": r["phc_id"], "medicine_name": r["medicine_name"],
                "current_stock": int(r["current_stock"]),
                "footfall_history": [int(x) for x in str(r["daily_patient_footfall_history"]).split(",")],
            }
        self.transfers, self.reports = [], []

    def get_all_phcs(self): return sorted((dict(p) for p in self.phcs.values()), key=lambda p: p["phc_id"])
    def get_phc(self, phc_id): return dict(self.phcs[phc_id]) if phc_id in self.phcs else None
    def get_all_inventory(self): return [dict(v) for v in self.inv.values()]
    def get_inventory_for_phc(self, phc_id): return [dict(v) for v in self.inv.values() if v["phc_id"] == phc_id]
    def get_inventory_for_medicine(self, name): return [dict(v) for v in self.inv.values() if v["medicine_name"] == name]

    def update_stock(self, phc_id, medicine_name, qty): self.inv[(phc_id, medicine_name)]["current_stock"] = int(qty)

    def push_footfall(self, phc_id, count):
        for v in self.inv.values():
            if v["phc_id"] == phc_id:
                v["footfall_history"] = (v["footfall_history"][1:] + [int(count)])[-7:]

    def update_doctors_present(self, phc_id, present):
        p = self.phcs[phc_id]
        p["doctors_present"] = max(p["doctors_present"], 1) if present else 0

    def add_report(self, phc_id, transcript, language, extracted, source):
        self.reports.append({"phc_id": phc_id, "extracted": extracted, "source": source}); return str(len(self.reports))

    def add_transfer(self, item, source_phc_id, target_phc_id, quantity, brief, source):
        self.transfers.insert(0, {"id": str(len(self.transfers) + 1), "item": item, "source_phc_id": source_phc_id,
                                  "target_phc_id": target_phc_id, "quantity": quantity, "brief": brief, "source": source,
                                  "created_at": datetime.now(timezone.utc).isoformat()})
        return self.transfers[0]["id"]

    def list_transfers(self, limit=20): return [dict(t) for t in self.transfers[:limit]]
    def count_transfers(self): return len(self.transfers)
