from app import config, services


def test_qty_capped_by_donor_surplus():
    # donor surplus = 1000 - 10*50 = 500 ; need = 10*100 - 100 = 900 -> 500
    assert services.compute_transfer_qty(1000, 50, 100, 100) == 500


def test_qty_capped_by_target_need():
    # surplus = 5000-10*50 = 4500 ; need = 10*100-800 = 200 -> 200
    assert services.compute_transfer_qty(5000, 50, 800, 100) == 200


def test_no_surplus_gives_zero():
    assert services.compute_transfer_qty(100, 50, 0, 100) == 0


def test_hero_row_dispatch_never_breaches_donor_cover(client, repo):
    status = client.get("/api/v1/network-status").json()
    hebri = next(p for p in status["phcs"] if p["phc_id"] == "PHC001")
    para = next(i for i in hebri["inventory"] if i["medicine_name"] == "Paracetamol 500mg")
    assert para["status"] == "CRITICAL" and para["suggested_source_id"]
    donor_id = para["suggested_source_id"]
    r = client.post("/api/v1/recommend-redistribution",
                    json={"source_phc_id": donor_id, "target_phc_id": "PHC001", "item_name": "Paracetamol 500mg"})
    assert r.status_code == 200, r.text
    body = r.json()
    qty = body["brief"]["transfer_quantity"]
    donor_inv = next(i for i in repo.get_inventory_for_phc(donor_id) if i["medicine_name"] == "Paracetamol 500mg")
    avg = services.item_forecast(donor_inv)["_avg_raw"]
    assert donor_inv["current_stock"] - qty >= config.SAFETY_DAYS * avg - 1
    assert body["source"] == "mock" and len(repo.transfers) == 1


def test_donor_without_surplus_returns_409(client):
    r = client.post("/api/v1/recommend-redistribution",
                    json={"source_phc_id": "PHC001", "target_phc_id": "PHC005", "item_name": "Paracetamol 500mg"})
    assert r.status_code == 409


def test_bad_ids_400_and_unknown_item_404(client):
    assert client.post("/api/v1/recommend-redistribution",
                       json={"source_phc_id": "NOPE", "target_phc_id": "PHC001", "item_name": "ORS Sachets"}).status_code == 400
    assert client.post("/api/v1/recommend-redistribution",
                       json={"source_phc_id": "PHC005", "target_phc_id": "PHC001", "item_name": "Aspirin"}).status_code == 404
