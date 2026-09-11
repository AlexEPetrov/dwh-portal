from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "eex_gas_loader",
        "description": "Loads EEX natural gas spot indices",
        "writes_to": [
            table("src_eex", "eex_gas_spot"),
            view_of("src_eex", "v_eex_gas_spot_latest", "eex_gas_spot"),
        ],
    }
