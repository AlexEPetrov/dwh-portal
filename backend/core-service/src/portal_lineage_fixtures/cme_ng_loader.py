from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "cme_ng_loader",
        "description": "Loads CME NG (Henry Hub) futures settlements",
        "writes_to": [
            table("src_cme", "cme_ng_settlements"),
            view("src_cme", "v_cme_ng_settlements_latest"),
        ],
    }
