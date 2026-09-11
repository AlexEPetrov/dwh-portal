from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "ice_cot_loader",
        "description": "Loads ICE Commitments of Traders daily reports",
        "writes_to": [
            table("src_ice", "ice_cot_daily_reports"),
            view("src_ice", "v_ice_cot_daily_reports_latest"),
        ],
    }
