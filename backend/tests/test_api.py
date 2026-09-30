def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "ai_mode": "mock"}


def test_network_status_shape_and_counts(client):
    d = client.get("/api/v1/network-status").json()
    s = d["summary"]
    assert s["total_phcs"] == 12 and len(d["phcs"]) == 12
    assert s["active_stockout_alerts"] == 3 and s["ai_mode"] == "mock"
    assert sum(len(p["inventory"]) for p in d["phcs"]) == 72


def test_every_critical_item_has_a_donor(client):
    d = client.get("/api/v1/network-status").json()
    for p in d["phcs"]:
        for i in p["inventory"]:
            if i["status"] == "CRITICAL":
                assert i["suggested_source_id"], (p["phc_id"], i["medicine_name"])


def test_voice_report_persists_to_repo(client, repo):
    r = client.post("/api/v1/log-daily-voice-report", json={
        "audio_transcript": "आज १२० मरीज आए, पैरासिटामोल 30 बचे हैं, डॉक्टर मौजूद हैं",
        "phc_id": "PHC003", "language": "hi-IN"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mock" and body["fallback_reason"]
    assert repo.inv[("PHC003", "Paracetamol 500mg")]["current_stock"] == 30
    assert repo.inv[("PHC003", "Paracetamol 500mg")]["footfall_history"][-1] == 120
    assert repo.phcs["PHC003"]["doctors_present"] >= 1  # was 0


def test_voice_unknown_phc_404(client):
    r = client.post("/api/v1/log-daily-voice-report", json={"audio_transcript": "hi", "phc_id": "X"})
    assert r.status_code == 404


def test_nearby_sorted_and_limited(client):
    r = client.get("/api/v1/phcs/nearby", params={"lat": 13.47, "lng": 74.98, "radius_km": 50, "limit": 3}).json()
    assert len(r) == 3 and r[0]["name"] == "Hebri PHC"
    assert [x["distance_km"] for x in r] == sorted(x["distance_km"] for x in r)
    assert r[0]["maps_url"].startswith("https://www.google.com/maps/dir/")


def test_transfers_listing_after_dispatch(client):
    client.post("/api/v1/recommend-redistribution",
                json={"source_phc_id": "PHC005", "target_phc_id": "PHC003", "item_name": "ORS Sachets"})
    t = client.get("/api/v1/transfers").json()
    assert len(t) == 1 and t[0]["target_phc_name"] == "Brahmavar PHC"
    assert client.get("/api/v1/network-status").json()["summary"]["active_ai_transfers"] == 1
