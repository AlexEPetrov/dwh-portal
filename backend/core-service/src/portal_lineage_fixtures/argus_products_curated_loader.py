from portal_lineage_fixtures._targets import table, view


def get_metadata() -> dict:
    """Second process for the dual-handler Argus products demo (replaces RestApi)."""
    return {
        "schema_version": "1.0",
        "name": "argus_products_curated_loader",
        "description": "Curates Argus products into a normalized staging table + view",
        "writes_to": [
            table("src_argus", "argus_products_assessments_curated"),
            view("src_argus", "v_argus_products_assessments_curated"),
        ],
    }
