"""Shared whitespace normalization for catalog text search and its SQL equivalent."""

# Match browser whitespace handling, including non-breaking and Unicode spaces.
SEARCH_WHITESPACE = (
    " \t\n\r\v\f\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_REMOVE_WHITESPACE = str.maketrans("", "", SEARCH_WHITESPACE)


def compact_catalog_text(value: str | None) -> str:
    """Ignore case and whitespace without translating identifiers or inventing aliases."""
    return (value or "").translate(_REMOVE_WHITESPACE).lower()
