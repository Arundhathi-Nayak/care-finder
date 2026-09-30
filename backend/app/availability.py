"""Public availability levels. Citizens see levels, never exact stock counts."""
from datetime import datetime, timezone


def availability_level(current_stock: int, status: str) -> str:
    """stock == 0 -> OUT; CRITICAL/WARNING -> LOW; GREEN -> IN_STOCK."""
    if current_stock <= 0:
        return "OUT"
    if status in ("CRITICAL", "WARNING"):
        return "LOW"
    return "IN_STOCK"


def data_as_of() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")