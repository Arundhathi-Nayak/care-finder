import pytest
from pydantic import ValidationError

from app.availability import availability_level, data_as_of
from app.schemas import ChatRequest, ChatResponse, PhcCard


@pytest.mark.parametrize("stock,status,expected", [
    (0, "GREEN", "OUT"),
    (0, "CRITICAL", "OUT"),
    (5, "CRITICAL", "LOW"),
    (50, "WARNING", "LOW"),
    (500, "GREEN", "IN_STOCK"),
])
def test_availability_mapping(stock, status, expected):
    assert availability_level(stock, status) == expected


def test_history_truncated_to_last_10():
    hist = [{"role": "user", "text": f"m{i}"} for i in range(15)]
    req = ChatRequest(message="hi", history=hist)
    assert len(req.history) == 10
    assert req.history[-1].text == "m14"


def test_bad_coordinates_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", location={"lat": 123, "lng": 10})


def test_empty_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_response_shape():
    card = PhcCard(phc_id="PHC001", name="Hebri PHC", district="Udupi",
                   beds_available=2, beds_total=6, doctors_present=1,
                   doctors_total=2, maps_url="https://x")
    r = ChatResponse(reply="ok", source="mock", data_as_of=data_as_of(), cards=[card])
    d = r.model_dump()
    assert d["emergency"] is False and d["cards"][0]["type"] == "phc"