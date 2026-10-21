"""Portal admin domain: write-side configuration of document/extraction sources.

DDD-lite layout (same shape as ``domains.catalog``):

- ``models`` — domain entities / value objects
- ``services`` — application use-cases
- ``repositories`` — persistence ports and adapters
- ``providers`` — external systems (DWH registry, etc.)
- ``runtime`` — composition root

HTTP lives under ``api`` with tag ``admin``; this package must not grow
catalog browse/read concerns.
"""
