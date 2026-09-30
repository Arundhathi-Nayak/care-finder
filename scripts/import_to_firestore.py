#!/usr/bin/env python3
"""Idempotent import of PHC directory + inventory telemetry into Firestore.

Usage (from repo root):
    python scripts/import_to_firestore.py --dry-run
    python scripts/import_to_firestore.py
    python scripts/import_to_firestore.py --wipe      # asks for confirmation
"""
import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
BATCH_LIMIT = 400
WIPE_COLLECTIONS = ["phcs", "inventory", "daily_reports", "transfers"]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_phcs() -> list[dict]:
    df = pd.read_csv(DATA / "phc_directory.csv")
    required = {"phc_id", "phc_name", "district", "state", "lat", "lng",
                "beds_available", "beds_total", "doctors_present", "doctors_total"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"phc_directory.csv missing columns: {sorted(missing)}")
    if df["phc_id"].duplicated().any():
        sys.exit("phc_directory.csv has duplicate phc_id values")
    return df.to_dict("records")


def load_inventory(valid_phc_ids: set[str]) -> list[dict]:
    df = pd.read_csv(DATA / "inventory_telemetry.csv")
    rows = []
    for r in df.to_dict("records"):
        if r["phc_id"] not in valid_phc_ids:
            sys.exit(f"Inventory row references unknown phc_id {r['phc_id']}")
        hist = [int(x) for x in str(r["daily_patient_footfall_history"]).split(",")]
        if len(hist) != 7:
            sys.exit(f"{r['phc_id']} {r['medicine_name']}: history must have 7 values, got {len(hist)}")
        rows.append({
            "phc_id": r["phc_id"],
            "medicine_name": r["medicine_name"],
            "current_stock": int(r["current_stock"]),
            "footfall_history": hist,
        })
    return rows


def init_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        p = Path(cred_path)
        if not p.is_absolute():
            p = (BACKEND / p).resolve()  # relative paths are relative to backend/.env
        if not p.exists():
            sys.exit(f"Service account key not found at {p}")
        firebase_admin.initialize_app(credentials.Certificate(str(p)))
    else:
        firebase_admin.initialize_app()  # Application Default Credentials
    return firestore.client(), firestore


def wipe(db):
    print("This will DELETE ALL documents in:", ", ".join(WIPE_COLLECTIONS))
    if input("Type 'yes' to continue: ").strip().lower() != "yes":
        sys.exit("Aborted.")
    for name in WIPE_COLLECTIONS:
        total = 0
        while True:
            docs = list(db.collection(name).limit(BATCH_LIMIT).stream())
            if not docs:
                break
            batch = db.batch()
            for d in docs:
                batch.delete(d.reference)
            batch.commit()
            total += len(docs)
        print(f"  wiped {name}: {total} docs")


def commit_in_batches(db, ops):
    """ops: list of (doc_ref, data). Commits <=BATCH_LIMIT per batch."""
    for i in range(0, len(ops), BATCH_LIMIT):
        batch = db.batch()
        for ref, data in ops[i:i + BATCH_LIMIT]:
            batch.set(ref, data, merge=True)
        batch.commit()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wipe", action="store_true", help="delete phcs/inventory/daily_reports/transfers first")
    ap.add_argument("--dry-run", action="store_true", help="validate CSVs and print summary, write nothing")
    args = ap.parse_args()

    load_dotenv(BACKEND / ".env")
    phcs = load_phcs()
    inventory = load_inventory({p["phc_id"] for p in phcs})

    if args.dry_run:
        print(f"[dry-run] would write {len(phcs)} phcs and {len(inventory)} inventory docs")
        for r in inventory[:3]:
            print(f"  e.g. inventory/{r['phc_id']}__{slugify(r['medicine_name'])} -> stock={r['current_stock']}")
        return

    db, firestore = init_firestore()
    if args.wipe:
        wipe(db)

    ts = firestore.SERVER_TIMESTAMP
    ops = []
    for p in phcs:
        ops.append((db.collection("phcs").document(p["phc_id"]), {
            "phc_name": p["phc_name"],
            "district": p["district"],
            "state": p["state"],
            "location": firestore.GeoPoint(float(p["lat"]), float(p["lng"])),
            "beds_available": int(p["beds_available"]),
            "beds_total": int(p["beds_total"]),
            "doctors_present": int(p["doctors_present"]),
            "doctors_total": int(p["doctors_total"]),
            "updated_at": ts,
        }))
    for r in inventory:
        doc_id = f"{r['phc_id']}__{slugify(r['medicine_name'])}"
        ops.append((db.collection("inventory").document(doc_id), {**r, "updated_at": ts}))

    commit_in_batches(db, ops)
    print(f"Done: {len(phcs)} phcs, {len(inventory)} inventory docs written.")


if __name__ == "__main__":
    main()