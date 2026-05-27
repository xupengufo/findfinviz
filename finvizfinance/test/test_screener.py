import pytest
from finvizfinance.screener import (
    Overview,
    Custom,
    Financial,
    Ownership,
    Performance,
    Technical,
    Valuation,
    get_signal,
    get_filters,
    get_filter_options
)


def test_screener_overview():
    foverview = Overview()
    filters_dict = {'Exchange': 'AMEX', 'Sector': 'Basic Materials'}
    foverview.set_filter(filters_dict=filters_dict)
    df = foverview.screener_view(order="Company", ascend=False)
    assert(df is not None)
    ticker = 'TSLA'
    foverview.set_filter(signal='', filters_dict={}, ticker=ticker)
    df = foverview.screener_view()
    assert(df is not None)


def test_screener_get_settings():
    signals = get_signal()
    assert type(signals) is list

    filters = get_filters()
    assert type(filters) is list

    filter_options = get_filter_options('Exchange')
    assert type(filter_options) is list

    with pytest.raises(ValueError):
        get_filter_options('Dummy')


def test_no_results():
    # Test all screener types with a filter that returns no results to ensure they return None gracefully instead of throwing exceptions.
    for ScreenerClass in [Overview, Custom, Financial, Ownership, Performance, Technical, Valuation]:
        screener = ScreenerClass()
        # Setting extremely conflicting filters to guarantee 0 matches
        # Oversold + Overbought is an impossible combination
        screener.set_filter(signal="Oversold")
        screener.set_filter(filters_dict={"RSI (14)": "Overbought (80)"})
        try:
            df = screener.screener_view(limit=5)
            assert df is None, f"{ScreenerClass.__name__} should return None when there are no matches"
        except Exception as e:
            # Any exception (AttributeError, IndexError, etc.) means it failed to handle the 0-results page gracefully
            assert False, f"{ScreenerClass.__name__} raised an exception on empty results: {e}"

