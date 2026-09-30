from app import forecasting


def test_hero_row_is_critical():
    f = forecasting.forecast([45, 52, 60, 58, 70, 85, 92], stock=120, usage_rate=1.0)
    assert f["status"] == "CRITICAL"
    assert 1.0 <= f["days_to_stockout"] <= 1.5


def test_thresholds():
    assert forecasting.status_for(2.9) == "CRITICAL"
    assert forecasting.status_for(3.0) == "WARNING"
    assert forecasting.status_for(6.9) == "WARNING"
    assert forecasting.status_for(7.0) == "GREEN"


def test_zero_stock_is_zero_days():
    assert forecasting.forecast([10] * 7, 0, 1.0)["days_to_stockout"] == 0


def test_demand_never_negative():
    assert min(forecasting.predict_daily_patients([90, 70, 50, 30, 10, 5, 1])) >= 0


def test_plenty_of_stock_is_green():
    assert forecasting.forecast([50] * 7, 5000, 1.0)["status"] == "GREEN"
