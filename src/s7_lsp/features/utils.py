"""Shared feature utilities for S7-LSP.

Provides:
- word_at_position(): extract the SCL identifier under the cursor
- get_context(): detect syntactic context at the cursor
- WordInfo: frozen dataclass holding word info and source range
- ContextKind: enum of possible syntactic contexts

This module has NO project or lsprotocol dependencies — pure Python only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

# ---------------------------------------------------------------------------
# ContextKind
# ---------------------------------------------------------------------------


class ContextKind(Enum):
    """Syntactic context at a cursor position, determined by backwards scan."""

    AFTER_DOT = auto()  # Cursor is immediately after '.' → member completion
    AFTER_HASH = auto()  # Cursor is immediately after '#' → variable completion
    INSIDE_QUOTES = auto()  # Cursor is between "..." → block name completion
    INSIDE_CALL = auto()  # Cursor is inside function-call parentheses → named param completion
    TYPE_POSITION = (
        auto()
    )  # Cursor is after ':' in a variable declaration context → type completion
    GENERAL = auto()  # Everything else → keyword/general completion


# ---------------------------------------------------------------------------
# WordInfo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WordInfo:
    """Information about the SCL identifier under the cursor.

    Attributes:
        word:       The identifier text (without any sigil like '#' or '"').
        prefix:     The sigil that preceded the word: '#', '"', or ''.
        start_line: 0-based line of the word start (including prefix sigil).
        start_char: 0-based character offset of the word start (including prefix sigil).
        end_line:   0-based line of the word end (exclusive).
        end_char:   0-based character offset of the word end (exclusive).
        chain:      For member-access chains the full token list, e.g.
                    ['#struct', 'field'] when cursor is on 'field' in '#struct.field'.
                    For simple identifiers this is a list with just the full token
                    (prefix + word) or the word alone when no prefix.
    """

    word: str
    prefix: str
    start_line: int
    start_char: int
    end_line: int
    end_char: int
    chain: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_line(source: str, line: int) -> str | None:
    """Return the text of the given 0-based line (without trailing newline), or None."""
    lines = source.splitlines(keepends=True)
    if line < 0 or line >= len(lines):
        return None
    return lines[line].rstrip("\r\n")


def _ident_end(row: str, start: int) -> int:
    """Return the exclusive end index of an SCL identifier body beginning at start."""
    end = start
    while end < len(row) and (row[end].isalnum() or row[end] == "_"):
        end += 1
    return end


def _ident_start(row: str, col: int) -> int:
    """Return the inclusive start of the identifier body that contains col."""
    start = col
    while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
        start -= 1
    return start


def _collect_chain_left(row: str, token_start: int) -> list[str]:
    """Walk left from token_start collecting dot-separated tokens.

    Returns the list of preceding tokens in order (leftmost first).
    token_start is the character index of the first character of the current
    token (already including any '#' prefix).
    """
    segments: list[str] = []
    left = token_start - 1

    while left >= 0 and row[left] == ".":
        left -= 1  # skip '.'
        if left < 0:
            break
        if row[left] == '"':
            # Quoted segment: find opening quote
            open_q = row.rfind('"', 0, left)
            if open_q == -1:
                break
            seg = row[open_q : left + 1]
            segments.insert(0, seg)
            left = open_q - 1
        else:
            # Plain or hash-prefixed ident
            seg_end = left + 1
            while left >= 0 and (row[left].isalnum() or row[left] == "_"):
                left -= 1
            seg_body_start = left + 1
            seg_word = row[seg_body_start:seg_end]
            if not seg_word:
                break
            if seg_body_start > 0 and row[seg_body_start - 1] == "#":
                seg = f"#{seg_word}"
                left = seg_body_start - 2
            else:
                seg = seg_word
                left = seg_body_start - 1
            segments.insert(0, seg)

    return segments


# ---------------------------------------------------------------------------
# word_at_position
# ---------------------------------------------------------------------------


def word_at_position(source: str, line: int, character: int) -> WordInfo | None:
    """Extract the SCL word (identifier) at the given 0-based line/character.

    Handles three identifier forms:
    - Plain:          myVar
    - Hash-prefixed:  #localVar
    - Quoted:         "GlobalDB"

    Also handles member-access chains: if cursor is on `field` in
    `#struct.field`, returns `field` as the word and provides
    `chain = ['#struct', 'field']`.

    Returns None when the cursor is on whitespace, an operator, or any
    character that is not part of an SCL identifier.
    """
    row = _get_line(source, line)
    if row is None:
        return None

    col = character
    if col >= len(row):
        return None

    ch = row[col]

    # ---- cursor is on '#' sigil -------------------------------------------
    if ch == "#":
        # The '#' is a sigil, not part of the ident body.
        # Return the following identifier if present.
        ident_start = col + 1
        if ident_start >= len(row) or not (row[ident_start].isalpha() or row[ident_start] == "_"):
            return None
        ident_end = _ident_end(row, ident_start)
        word = row[ident_start:ident_end]
        left_segs = _collect_chain_left(row, col)
        chain = [*left_segs, f"#{word}"]
        return WordInfo(
            word=word,
            prefix="#",
            start_line=line,
            start_char=col,
            end_line=line,
            end_char=ident_end,
            chain=chain,
        )

    # ---- cursor is on opening '"' -------------------------------------------
    if ch == '"':
        close = row.find('"', col + 1)
        if close == -1:
            # Unclosed quote — still return what we have
            word = row[col + 1 :]
            return WordInfo(
                word=word,
                prefix='"',
                start_line=line,
                start_char=col,
                end_line=line,
                end_char=len(row),
                chain=[f'"{word}"'],
            )
        word = row[col + 1 : close]
        left_segs = _collect_chain_left(row, col)
        chain = [*left_segs, f'"{word}"']
        return WordInfo(
            word=word,
            prefix='"',
            start_line=line,
            start_char=col,
            end_line=line,
            end_char=close + 1,
            chain=chain,
        )

    # ---- cursor may be inside a quoted string (between open and close '"') --
    # Count how many '"' characters appear in the line before col.
    # If odd, the cursor is inside a quoted string (the last unmatched '"' is
    # the opening quote).
    quote_positions = [i for i, c in enumerate(row[:col]) if c == '"']
    if len(quote_positions) % 2 == 1:
        # Cursor is inside a quoted string.
        open_q = quote_positions[-1]
        close = row.find('"', col)
        if close == -1:
            close_end = len(row)
            word = row[open_q + 1 :]
        else:
            close_end = close + 1
            word = row[open_q + 1 : close]
        left_segs = _collect_chain_left(row, open_q)
        chain = [*left_segs, f'"{word}"']
        return WordInfo(
            word=word,
            prefix='"',
            start_line=line,
            start_char=open_q,
            end_line=line,
            end_char=close_end,
            chain=chain,
        )

    # ---- plain or hash-preceded identifier ----------------------------------
    # ch must be alphanumeric or underscore; otherwise it is an operator.
    if not (ch.isalpha() or ch == "_"):
        return None

    # Find identifier body boundaries
    body_start = _ident_start(row, col)
    body_end = _ident_end(row, col)
    word = row[body_start:body_end]

    if not word:
        return None

    # Check for '#' prefix immediately left of body_start
    prefix = ""
    token_start = body_start
    if body_start > 0 and row[body_start - 1] == "#":
        prefix = "#"
        token_start = body_start - 1

    left_segs = _collect_chain_left(row, token_start)
    full_token = f"{prefix}{word}" if prefix else word
    chain = [*left_segs, full_token]

    return WordInfo(
        word=word,
        prefix=prefix,
        start_line=line,
        start_char=token_start,
        end_line=line,
        end_char=body_end,
        chain=chain,
    )


# ---------------------------------------------------------------------------
# get_context
# ---------------------------------------------------------------------------


def get_context(source: str, line: int, character: int) -> ContextKind:
    """Detect the syntactic context at the given 0-based line/character.

    Uses backwards scanning from the cursor position — no full parsing needed.

    Returns one of the ContextKind enum values.
    """
    lines = source.splitlines(keepends=False)

    # Build a flat character list from the beginning up to (line, character).
    chars: list[str] = []
    for i, src_line in enumerate(lines):
        if i < line:
            chars.extend(src_line)
            chars.append("\n")
        else:
            chars.extend(src_line[:character])
            break

    if not chars:
        return ContextKind.GENERAL

    # ---- INSIDE_QUOTES check ------------------------------------------------
    # Count '"' chars on the current logical line going backwards.
    # If the count is odd, the cursor is inside a quoted string.
    quote_count = 0
    for i in range(len(chars) - 1, -1, -1):
        c = chars[i]
        if c == "\n":
            break  # quoted identifiers cannot span lines in SCL
        if c == '"':
            quote_count += 1

    if quote_count % 2 == 1:
        return ContextKind.INSIDE_QUOTES

    # ---- Immediately preceding non-whitespace character ---------------------
    idx = len(chars) - 1
    while idx >= 0 and chars[idx] in (" ", "\t"):
        idx -= 1

    if idx < 0:
        return ContextKind.GENERAL

    prev_ch = chars[idx]

    if prev_ch == ".":
        return ContextKind.AFTER_DOT

    if prev_ch == "#":
        return ContextKind.AFTER_HASH

    # ---- INSIDE_CALL: unmatched '(' scanning backwards ---------------------
    paren_depth = 0
    for i in range(len(chars) - 1, -1, -1):
        c = chars[i]
        if c == ")":
            paren_depth += 1
        elif c == "(":
            if paren_depth == 0:
                return ContextKind.INSIDE_CALL
            paren_depth -= 1

    # ---- TYPE_POSITION: ':' (not ':=') preceding the cursor ----------------
    # Pattern: <ident> <ws>* ':' <ws>* cursor
    # Walk backwards from end of chars, skip optional identifier, skip
    # whitespace, then look for ':' that is not part of ':='.
    i = len(chars) - 1
    # Skip partial identifier characters
    while i >= 0 and (chars[i].isalnum() or chars[i] == "_"):
        i -= 1
    # Skip whitespace
    while i >= 0 and chars[i] in (" ", "\t"):
        i -= 1
    if i >= 0 and chars[i] == ":":
        # Check that what follows ':' (at i+1) is not '='
        if i + 1 < len(chars) and chars[i + 1] == "=":
            pass  # assignment operator
        else:
            return ContextKind.TYPE_POSITION

    return ContextKind.GENERAL
