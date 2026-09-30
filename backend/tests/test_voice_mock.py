from app.routers.voice import mock_extract


def test_hindi_devanagari_numerals():
    r = mock_extract("आज १२० मरीज आए, पैरासिटामोल 30 बचे हैं, डॉक्टर मौजूद हैं")
    assert r["patient_count"] == 120
    assert r["paracetamol_stock"] == 30
    assert r["doctor_present"] is True


def test_hindi_doctor_absent():
    r = mock_extract("आज 45 मरीज आए, डॉक्टर नहीं आए")
    assert r["patient_count"] == 45
    assert r["paracetamol_stock"] is None
    assert r["doctor_present"] is False


def test_kannada_numerals_and_absent_doctor():
    r = mock_extract("ಇಂದು ೮೫ ರೋಗಿಗಳು ಬಂದಿದ್ದಾರೆ, ಪ್ಯಾರಸಿಟಮಾಲ್ ೪೦ ಉಳಿದಿದೆ, ವೈದ್ಯರು ಇಲ್ಲ")
    assert r["patient_count"] == 85
    assert r["paracetamol_stock"] == 40
    assert r["doctor_present"] is False


def test_english_and_500mg_not_read_as_stock():
    r = mock_extract("Today 60 patients, paracetamol 500mg 25 left, no doctor")
    assert r["patient_count"] == 60
    assert r["paracetamol_stock"] == 25
    assert r["doctor_present"] is False


def test_unstated_values_are_null():
    r = mock_extract("Everything is fine today")
    assert r["patient_count"] is None and r["paracetamol_stock"] is None and r["doctor_present"] is None
