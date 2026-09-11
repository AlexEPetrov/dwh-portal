from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "cme_cl_loader",
        "description": "Loads CME CL (WTI) futures settlements",
        "writes_to": [
            table("src_cme", "cme_cl_settlements"),
            view_of("src_cme", "v_cme_cl_settlements_latest", "cme_cl_settlements"),
            # Multi-source demo view (also declared from EEX power loader).
            view_of(
                "src_market",
                "v_cross_source_prices",
                "cme_cl_settlements",
                base_schema="src_cme",
            ),
        ],
    }
