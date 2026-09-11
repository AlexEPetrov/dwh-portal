from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "nymex_rbob_loader",
        "description": "Loads NYMEX RBOB gasoline futures settlements",
        "writes_to": [
            table("src_cme", "nymex_rbob_settlements"),
            view_of("src_cme", "v_nymex_rbob_settlements_latest", "nymex_rbob_settlements"),
        ],
    }
