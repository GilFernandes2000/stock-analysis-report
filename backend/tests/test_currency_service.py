from unittest.mock import MagicMock, patch

import pytest

from app.services.currency_service import (
    CurrencyService,
    normalize_to_major,
)


def test_gbp_pence_normalization_3839():
    result = normalize_to_major(3839.0, "GBp")
    assert result.currency == "GBP"
    assert result.amount == 38.39
    assert result.was_minor_unit is True


def test_gbp_pence_normalization_111():
    result = normalize_to_major(111.4, "GBp")
    assert result.currency == "GBP"
    assert result.amount == 1.114
    assert result.was_minor_unit is True


def test_eur_identity():
    svc = CurrencyService(MagicMock())
    assert svc.convert(100.0, "EUR", "EUR") == 100.0
    assert svc.get_fx_rate("EUR", "EUR") == 1.0


def test_validate_display_currency():
    db = MagicMock()
    svc = CurrencyService(db)
    assert svc.validate_display_currency("eur") == "EUR"
    with pytest.raises(ValueError, match="Unsupported"):
        svc.validate_display_currency("JPY")


@patch.object(CurrencyService, "_fetch_fx_rate", return_value=1.15)
def test_gbp_to_eur_conversion(mock_fetch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = CurrencyService(db)
    converted = svc.convert(38.39, "GBP", "EUR")
    assert converted == round(38.39 * 1.15, 4)
    mock_fetch.assert_called_once_with("GBP", "EUR")


@patch.object(CurrencyService, "_fetch_fx_rate", return_value=1.15)
def test_normalize_and_convert(mock_fetch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = CurrencyService(db)
    display, native_cur, native_price, note = svc.normalize_and_convert(
        3839.0, "GBp", "EUR"
    )
    assert native_cur == "GBP"
    assert native_price == 38.39
    assert display == round(38.39 * 1.15, 4)
    assert note is not None
    assert "GBp" in note
