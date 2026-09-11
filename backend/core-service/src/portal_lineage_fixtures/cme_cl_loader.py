from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "cme_cl_loader",
        "description": "Loads CME CL (WTI) futures settlements",
        "writes_to": [
            table("src_cme", "cme_cl_settlements"),
            view("src_cme", "v_cme_cl_settlements_latest"),
        ],
    }
