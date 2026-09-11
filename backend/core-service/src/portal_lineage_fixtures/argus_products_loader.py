from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "argus_products_loader",
        "description": "Loads Argus refined products assessments (primary Python handler)",
        "writes_to": [
            table("src_argus", "argus_products_assessments"),
            view("src_argus", "v_argus_products_assessments_latest"),
        ],
    }
