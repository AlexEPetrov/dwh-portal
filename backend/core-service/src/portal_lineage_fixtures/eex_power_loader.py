from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "eex_power_loader",
        "description": "Loads EEX day-ahead power spot prices",
        "writes_to": [
            table("src_eex", "eex_power_spot"),
            view_of("src_eex", "v_eex_power_spot_latest", "eex_power_spot"),
        ],
    }
