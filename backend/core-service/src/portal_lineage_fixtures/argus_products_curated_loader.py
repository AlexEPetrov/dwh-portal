from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    """Second process for the dual-handler Argus products demo."""
    return {
        "schema_version": "1.0",
        "name": "argus_products_curated_loader",
        "description": "Curates Argus products into a normalized staging table + view",
        "writes_to": [
            table("src_argus", "argus_products_assessments_curated"),
            view_of(
                "src_argus",
                "v_argus_products_assessments_curated",
                "argus_products_assessments_curated",
            ),
        ],
    }
