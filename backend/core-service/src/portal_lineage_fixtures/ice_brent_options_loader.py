from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "ice_brent_options_loader",
        "description": "Loads ICE Brent options settlement rows into inbox",
        "writes_to": [
            table("inbox", "inbox_ice_options_daily_market_reports"),
            view("inbox", "v_ice_options_daily_market_reports_latest"),
        ],
    }
