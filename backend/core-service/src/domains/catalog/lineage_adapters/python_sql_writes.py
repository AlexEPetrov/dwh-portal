"""Conservative PostgreSQL write-target extraction for Python lineage.

This is a lexer and a bounded DML recognizer, not a general SQL parser. It
never treats SQL in comments, string literals or dollar-quoted bodies as DML.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(
    r"\s+|--[^\n]*|/\*|\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$|"
    r"[eE]?'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
    r"[A-Za-z_\u0080-\uffff][\w$]*|[();,.]|[^\s]",
    re.UNICODE,
)
_IDENT = re.compile(r"[A-Za-z_\u0080-\uffff][\w$]*\Z", re.UNICODE)
_MAX_SQL = 262144
_MAX_TOKENS = 16384


def _tokens(sql):
    """Return tokens or None for an incomplete/oversized lexical input."""
    if len(sql) > _MAX_SQL:
        return None
    tokens = []
    pos = 0
    while pos < len(sql):
        match = _TOKEN.match(sql, pos)
        if match is None:
            return None
        token = match.group()
        pos = match.end()
        if token.isspace() or token.startswith("--"):
            continue
        if token == "/*":
            depth = 1
            while depth and pos < len(sql):
                if sql.startswith("/*", pos):
                    depth += 1
                    pos += 2
                elif sql.startswith("*/", pos):
                    depth -= 1
                    pos += 2
                else:
                    pos += 1
            if depth:
                return None
            continue
        if token.startswith("$") and token.endswith("$") and len(token) >= 2:
            end = sql.find(token, pos)
            if end < 0:
                return None
            pos = end + len(token)
            tokens.append("<literal>")
        elif token.startswith(("'", "E'", "e'")):
            # Escape-string syntax is deliberately not approximated: a backslash
            # can change the position of the closing quote.
            if token[:2].lower() == "e'" and "\\" in token:
                return None
            if not token.endswith("'") or len(token) == 1:
                return None
            tokens.append("<literal>")
        elif token == '"':
            return None
        else:
            tokens.append(token)
        if len(tokens) > _MAX_TOKENS:
            return None
    return tokens


def _identifier(token):
    if token.startswith('"') and token.endswith('"') and len(token) > 2:
        return token[1:-1].replace('""', '"')
    if _IDENT.fullmatch(token):
        return token.lower()
    return None


def _relation(tokens, pos):
    only = pos < len(tokens) and tokens[pos].upper() == "ONLY"
    if only:
        pos += 1
    wrapped = only and pos < len(tokens) and tokens[pos] == "("
    if wrapped:
        pos += 1
    if pos >= len(tokens):
        return None, pos
    first = _identifier(tokens[pos])
    pos += 1
    if first is None or (pos < len(tokens) and tokens[pos] == "&"):
        return None, pos
    if pos < len(tokens) and tokens[pos] == ".":
        if pos + 1 >= len(tokens):
            return None, pos
        second = _identifier(tokens[pos + 1])
        pos += 2
        if second is None or (pos < len(tokens) and tokens[pos] in {".", "&"}):
            return None, pos
        target = (first, second)
    else:
        target = (None, first)
    if wrapped:
        if pos >= len(tokens) or tokens[pos] != ")":
            return None, pos
        pos += 1
    return target, pos


def _matching_paren(tokens, start):
    depth = 0
    for pos in range(start, len(tokens)):
        if tokens[pos] == "(":
            depth += 1
        elif tokens[pos] == ")":
            depth -= 1
            if depth == 0:
                return pos
    return None


def _statement(tokens, depth=0):
    """Return (targets, incomplete), including data-modifying CTEs."""
    if not tokens:
        return [], False
    if depth >= 16:
        return [], True
    head = tokens[0].upper()
    if "__PORTAL_UNKNOWN_VALUE__" in head:
        return [], True
    if head == "WITH":
        pos = 1
        targets = []
        incomplete = False
        if pos < len(tokens) and tokens[pos].upper() == "RECURSIVE":
            pos += 1
        while pos < len(tokens):
            if _identifier(tokens[pos]) is None:
                return targets, True
            pos += 1
            if pos < len(tokens) and tokens[pos] == "(":
                end = _matching_paren(tokens, pos)
                if end is None:
                    return targets, True
                pos = end + 1
            if pos >= len(tokens) or tokens[pos].upper() != "AS":
                return targets, True
            pos += 1
            if pos < len(tokens) and tokens[pos].upper() == "NOT":
                pos += 1
            if pos < len(tokens) and tokens[pos].upper() == "MATERIALIZED":
                pos += 1
            if pos >= len(tokens) or tokens[pos] != "(":
                return targets, True
            end = _matching_paren(tokens, pos)
            if end is None:
                return targets, True
            inner, uncertain = _statement(tokens[pos + 1:end], depth + 1)
            targets.extend(inner)
            incomplete |= uncertain
            pos = end + 1
            if pos < len(tokens) and tokens[pos] == ",":
                pos += 1
                continue
            outer, uncertain = _statement(tokens[pos:], depth + 1)
            return targets + outer, incomplete or uncertain
        return targets, True
    if head in {"INSERT", "MERGE", "DELETE"}:
        expected = "FROM" if head == "DELETE" else "INTO"
        if len(tokens) < 2 or tokens[1].upper() != expected:
            return [], True
        target, pos = _relation(tokens, 2)
        if target is None or (pos >= len(tokens) and head != "DELETE"):
            return [], True
        if pos < len(tokens) and tokens[pos] in {".", "&", "-", "+", "/", "=", "<literal>"}:
            return [], True
        return [target], False
    if head == "UPDATE":
        target, pos = _relation(tokens, 1)
        if target is None or pos >= len(tokens) or tokens[pos] in {".", "&", "-", "+", "/", "=", "<literal>"}:
            return [], True
        return [target], False
    if head == "COPY":
        if len(tokens) > 1 and tokens[1] == "(":
            return [], False  # COPY (query) TO is a read.
        target, pos = _relation(tokens, 1)
        if target is None:
            return [], True
        if pos < len(tokens) and tokens[pos] == "(":
            end = _matching_paren(tokens, pos)
            if end is None:
                return [], True
            pos = end + 1
        if pos >= len(tokens):
            return [], True
        direction = tokens[pos].upper()
        if direction == "FROM":
            return [target], False
        return [], direction != "TO"
    if head == "TRUNCATE":
        pos = 1
        if pos < len(tokens) and tokens[pos].upper() == "TABLE":
            pos += 1
        targets = []
        while True:
            target, pos = _relation(tokens, pos)
            if target is None:
                return targets, True
            targets.append(target)
            if pos < len(tokens) and tokens[pos] == "*":
                pos += 1
            if pos >= len(tokens) or tokens[pos] != ",":
                return targets, False
            pos += 1
    # These can conceal writes, but do not prove a table identity.
    return [], head in {"CALL", "DO", "EXECUTE", "PREPARE", "EXPLAIN", "CREATE", "ALTER", "DROP"}


def sql_write_targets(sql):
    """Extract direct DML destinations and flag unsupported/incomplete syntax."""
    tokens = _tokens(sql)
    if tokens is None:
        return [], True
    targets = []
    incomplete = False
    start = depth = 0
    for index, token in enumerate(tokens + [";"]):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                return targets, True
        elif token == ";" and depth == 0:
            found, uncertain = _statement(tokens[start:index])
            targets.extend(found)
            incomplete |= uncertain
            start = index + 1
    return targets, incomplete or depth != 0
