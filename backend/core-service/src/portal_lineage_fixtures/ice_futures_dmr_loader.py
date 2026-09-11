from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "ice_futures_dmr_loader",
        "description": "Loads ICE futures daily market reports",
        "writes_to": [
            table("src_ice", "ice_futures_daily_market_reports"),
            view_of(
                "src_ice",
                "v_ice_futures_daily_market_reports_latest",
                "ice_futures_daily_market_reports",
            ),
        ],
    }
