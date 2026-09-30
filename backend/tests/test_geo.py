from app import geo


def test_zero_distance():
    assert geo.haversine_km(13.47, 74.98, 13.47, 74.98) == 0


def test_hebri_to_karkala_reasonable():
    assert 25 <= geo.haversine_km(13.4756, 74.9836, 13.2144, 74.9917) <= 33


def test_maps_url():
    assert geo.maps_url(13.4, 74.9) == "https://www.google.com/maps/dir/?api=1&destination=13.4,74.9"
