from types import SimpleNamespace

from api.management import curves as curves_api
from domains.management.models.curve import CurveDefinitionModel


def test_get_curves_list_returns_full_curve_definitions_with_uom(monkeypatch):
    curve = CurveDefinitionModel(name="Brent", slug="BRENT", uom="USD/bbl")

    class FakeCurveDefinitionRepository:
        def __init__(self, session):
            assert session == "db-session"

        def get_all(self):
            yield curve

    monkeypatch.setattr(
        curves_api,
        "CurveDefinitionRepository",
        FakeCurveDefinitionRepository,
    )

    result = curves_api.get_curves_list(SimpleNamespace(session="db-session"))

    assert result == [curve]
    assert result[0].uom == "USD/bbl"
