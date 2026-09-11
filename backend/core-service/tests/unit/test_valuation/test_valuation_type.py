import pytest

from domains.risk.valuation_type import normalize_valuation_type


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" eod ", "eod"),
        ("Forecast 2027.01", "Forecast 2027.01"),
        ("стресс_сценарий-1", "стресс_сценарий-1"),
    ],
)
def test_normalize_valuation_type_accepts_storage_safe_text(raw: str, expected: str) -> None:
    assert normalize_valuation_type(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "a/b", "a\\b", "a=b", "a\nb", "a:b"])
def test_normalize_valuation_type_rejects_empty_or_unsafe_text(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_valuation_type(raw)
