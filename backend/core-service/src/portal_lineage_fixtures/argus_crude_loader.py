from portal_lineage_fixtures._targets import table, view_of


def get_metadata() -> dict:
    return {
        "schema_version": "1.0",
        "name": "argus_crude_loader",
        "description": "Loads Argus crude price assessments",
        "writes_to": [
            table("src_argus", "argus_crude_assessments"),
            view_of("src_argus", "v_argus_crude_assessments_latest", "argus_crude_assessments"),
        ],
    }
