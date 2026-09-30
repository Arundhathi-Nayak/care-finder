"""Pure forecasting functions (no I/O)."""
import numpy as np
from sklearn.linear_model import Ridge

from app import config

MAX_DAYS = 999.0


def predict_daily_patients(history: list[float], horizon: int = 7) -> list[float]:
    """Ridge(alpha=1.0) linear trend on the footfall history -> next `horizon` days (clipped >= 0)."""
    y = np.asarray(history, dtype=float)
    x = np.arange(len(y)).reshape(-1, 1)
    model = Ridge(alpha=1.0).fit(x, y)
    future = np.arange(len(y), len(y) + horizon).reshape(-1, 1)
    return [float(v) for v in np.maximum(model.predict(future), 0.0)]


def status_for(days_to_stockout: float) -> str:
    if days_to_stockout < config.CRITICAL_DAYS:
        return "CRITICAL"
    if days_to_stockout < config.WARNING_DAYS:
        return "WARNING"
    return "GREEN"


def days_until_stockout(stock: float, daily_demand: list[float]) -> float:
    """Walk stock forward day by day; after the horizon assume the average daily demand continues."""
    remaining = float(stock)
    for i, d in enumerate(daily_demand):
        if remaining <= d:
            return i + (remaining / d if d > 0 else 0.0)
        remaining -= d
    avg = sum(daily_demand) / len(daily_demand) if daily_demand else 0.0
    if avg <= 0:
        return MAX_DAYS
    return min(MAX_DAYS, len(daily_demand) + remaining / avg)


def forecast(history: list[float], stock: float, usage_rate: float) -> dict:
    demand = [p * usage_rate for p in predict_daily_patients(history)]
    avg = sum(demand) / len(demand)
    days = days_until_stockout(stock, demand)
    return {
        "projected_demand_7d": round(sum(demand), 1),
        "avg_daily_demand": round(avg, 2),
        "days_to_stockout": round(days, 1),
        "status": status_for(days),
        "_avg_raw": avg,  # unrounded, used by transfer maths
    }
