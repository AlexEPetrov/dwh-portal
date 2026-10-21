"""Portal documents domain: operational document intake / upload.

DDD-lite layout (same shape as ``domains.catalog``):

- ``models`` — upload jobs, document references
- ``services`` — intake use-cases
- ``repositories`` — persistence ports and adapters
- ``providers`` — storage / inbox integrations
- ``runtime`` — composition root

HTTP lives under ``api`` with tag ``documents``. This package must not own
catalog browse or extraction-source admin edits.
"""
