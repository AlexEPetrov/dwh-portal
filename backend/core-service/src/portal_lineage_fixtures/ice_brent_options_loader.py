from portal_lineage_fixtures._targets import storage, table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "ice_brent_options_loader",
        "description": "Loads ICE Brent options settlement rows into inbox (+ archive object)",
        "writes_to": [
            table("inbox", "inbox_ice_options_daily_market_reports"),
            storage("s3://dwh-archive/ice/options/brent/", kind="s3"),
            view_of(
                "inbox",
                "v_ice_options_daily_market_reports_latest",
                "inbox_ice_options_daily_market_reports",
            ),
        ],
    }
