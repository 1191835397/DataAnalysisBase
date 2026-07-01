from datetime import date

from dataanalysisbase.domain.price_limits import limit_down_threshold, limit_up_threshold


def test_limit_thresholds_use_security_board_and_risk_warning_name() -> None:
    assert limit_up_threshold("600519.SH", "贵州茅台") == 9.9
    assert limit_down_threshold("600519.SH", "贵州茅台") == -9.9

    assert limit_up_threshold("600000.SH", "ST浦发") == 4.9
    assert limit_down_threshold("600000.SH", "*ST浦发") == -4.9

    assert limit_up_threshold("688001.SH", "华兴源创") == 19.9
    assert limit_down_threshold("300001.SZ", "创业板") == -19.9

    assert limit_up_threshold("830001.BJ", "北交所") == 29.9
    assert limit_down_threshold("920001.BJ", "北交所") == -29.9


def test_limit_thresholds_are_absent_during_new_listing_window() -> None:
    assert (
        limit_up_threshold(
            "001001.SZ",
            "新股",
            listing_date=date(2026, 6, 23),
            snapshot_date=date(2026, 6, 27),
        )
        is None
    )
    assert (
        limit_down_threshold(
            "001001.SZ",
            "新股",
            listing_date=date(2026, 6, 23),
            snapshot_date=date(2026, 6, 27),
        )
        is None
    )
    assert (
        limit_up_threshold(
            "001001.SZ",
            "新股",
            listing_date=date(2026, 6, 23),
            snapshot_date=date(2026, 6, 28),
        )
        == 9.9
    )
