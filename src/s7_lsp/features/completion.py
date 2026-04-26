"""Auto-completion provider (Phase 3).

Provides:
- Keyword completion (IF, THEN, END_IF, etc.) with snippet templates
- Variable completion (in-scope variables with # prefix)
- Type completion (BOOL, INT, REAL, etc.)
- Named parameter completion (param_name :=)
- Block name completion ("MyFB", "MyDB")
"""

from __future__ import annotations

import re

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.utils import ContextKind, get_context
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import SymbolTable, VariableSymbol
from s7_lsp.semantic.type_info import BUILTIN_TYPE_INFO

# ---------------------------------------------------------------------------
# Keyword snippet definitions
# ---------------------------------------------------------------------------

# (label, insert_text, is_snippet)
_SNIPPET_KEYWORDS: list[tuple[str, str, bool]] = [
    (
        "IF",
        "IF ${1:condition} THEN\n\t$0\nEND_IF;",
        True,
    ),
    (
        "IF ... ELSE",
        "IF ${1:condition} THEN\n\t${2:}\nELSE\n\t$0\nEND_IF;",
        True,
    ),
    (
        "FOR",
        "FOR ${1:i} := ${2:1} TO ${3:10} DO\n\t$0\nEND_FOR;",
        True,
    ),
    (
        "WHILE",
        "WHILE ${1:condition} DO\n\t$0\nEND_WHILE;",
        True,
    ),
    (
        "REPEAT",
        "REPEAT\n\t$0\nUNTIL ${1:condition};\nEND_REPEAT;",
        True,
    ),
    (
        "CASE",
        "CASE ${1:var} OF\n\t${2:1}: $0\nEND_CASE;",
        True,
    ),
]

# Plain (non-snippet) keywords always offered in GENERAL context
_PLAIN_KEYWORDS: list[str] = [
    "IF",
    "FOR",
    "WHILE",
    "REPEAT",
    "CASE",
    "RETURN",
    "EXIT",
    "CONTINUE",
]

# Control flow keyword pairs: (open_kw, end_kw)
# Regex patterns used for matching (case-insensitive)
_CONTROL_PAIRS: list[tuple[str, str]] = [
    ("IF", "END_IF"),
    ("FOR", "END_FOR"),
    ("WHILE", "END_WHILE"),
    ("REPEAT", "END_REPEAT"),
    ("CASE", "END_CASE"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_snippet_item(label: str, insert_text: str) -> lsp.CompletionItem:
    """Create a snippet CompletionItem."""
    return lsp.CompletionItem(
        label=label,
        kind=lsp.CompletionItemKind.Keyword,
        insert_text=insert_text,
        insert_text_format=lsp.InsertTextFormat.Snippet,
    )


def _make_plain_item(label: str, insert_text: str | None = None) -> lsp.CompletionItem:
    """Create a plain-text CompletionItem."""
    return lsp.CompletionItem(
        label=label,
        kind=lsp.CompletionItemKind.Keyword,
        insert_text=insert_text if insert_text is not None else label,
        insert_text_format=lsp.InsertTextFormat.PlainText,
    )


def _count_unmatched(lines: list[str], open_kw: str, end_kw: str) -> int:
    """Return the number of unmatched open_kw occurrences in lines.

    Uses a simple counter: increment on open_kw, decrement on end_kw (floor 0).
    The lines should be passed in the order they appear in the source (top to
    bottom) so that the counter reflects the nesting depth.
    """
    open_pat = re.compile(rf"\b{re.escape(open_kw)}\b", re.IGNORECASE)
    end_pat = re.compile(rf"\b{re.escape(end_kw)}\b", re.IGNORECASE)
    count = 0
    for line in lines:
        open_hits = len(open_pat.findall(line))
        end_hits = len(end_pat.findall(line))
        # Process opens first, then closes, to handle same-line edge cases
        count += open_hits
        count = max(0, count - end_hits)
    return count


def _variable_completions(variables: list[VariableSymbol]) -> list[lsp.CompletionItem]:
    """Build CompletionItems for visible in-scope variables.

    Items are labelled without the '#' prefix. VAR_INPUT and VAR_OUTPUT
    variables are given a sort_text prefix of "0_" so they appear first;
    all other variables use "1_".
    """
    items: list[lsp.CompletionItem] = []
    priority_sections = {"VAR_INPUT", "VAR_OUTPUT"}
    for var in variables:
        prefix = "0_" if var.section_kind in priority_sections else "1_"
        items.append(
            lsp.CompletionItem(
                label=var.name,
                kind=lsp.CompletionItemKind.Variable,
                detail=var.type_name,
                documentation=var.section_kind,
                sort_text=prefix + var.name,
            )
        )
    return items


def _builtin_type_completions() -> list[lsp.CompletionItem]:
    """Build CompletionItems for all S7 built-in types."""
    items: list[lsp.CompletionItem] = []
    for type_name, type_desc in BUILTIN_TYPE_INFO.items():
        items.append(
            lsp.CompletionItem(
                label=type_name,
                kind=lsp.CompletionItemKind.TypeParameter,
                detail=type_desc.description,
            )
        )
    return items


def _udt_completions(symbol_table: SymbolTable) -> list[lsp.CompletionItem]:
    """Build CompletionItems for user-defined TYPE blocks in the symbol table."""
    items: list[lsp.CompletionItem] = []
    for block in symbol_table.get_all_blocks():
        if block.block_kind == "TYPE":
            items.append(
                lsp.CompletionItem(
                    label=block.name,
                    kind=lsp.CompletionItemKind.Struct,
                    detail="User-defined type",
                )
            )
    return items


def _keyword_completions(source: str, current_line: int) -> list[lsp.CompletionItem]:
    """Build the list of keyword completion items for GENERAL context.

    1. Always includes snippet templates for control-flow keywords.
    2. Always includes plain keywords (RETURN, EXIT, CONTINUE, etc.).
    3. Scans backwards in source to detect unmatched open keywords and offers
       the matching END_* completion.
    """
    items: list[lsp.CompletionItem] = []

    # --- Snippet templates ---------------------------------------------------
    for label, insert_text, is_snippet in _SNIPPET_KEYWORDS:
        if is_snippet:
            items.append(_make_snippet_item(label, insert_text))
        else:
            items.append(_make_plain_item(label, insert_text))

    # --- Plain keywords that don't have a snippet template ------------------
    # Avoid duplicating labels already added via snippets
    snippet_labels = {label for label, _, _ in _SNIPPET_KEYWORDS}
    for kw in _PLAIN_KEYWORDS:
        if kw not in snippet_labels:
            items.append(_make_plain_item(kw))

    # --- Context-sensitive END_* keywords ------------------------------------
    source_lines = source.splitlines(keepends=False)
    # Only consider lines up to and including the current line
    preceding_lines = source_lines[: current_line + 1]

    for open_kw, end_kw in _CONTROL_PAIRS:
        if _count_unmatched(preceding_lines, open_kw, end_kw) > 0:
            items.append(_make_plain_item(end_kw))

    return items


# ---------------------------------------------------------------------------
# Named parameter completion (PRD 3.4) — INSIDE_CALL context
# ---------------------------------------------------------------------------

_ASSIGNED_PARAM_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=>)",
)


def _find_call_name(line_text: str, char: int) -> str | None:
    """Scan backwards from *char* on *line_text* to find the function/block name.

    Looks for the pattern ``<identifier>(`` where the ``(`` is the unmatched
    open paren containing the cursor.  Returns the identifier string or None.

    Handles plain identifiers, ``#``-prefixed, and ``"quoted"`` identifiers.
    *char* may be equal to ``len(line_text)`` (cursor past the end of the line).
    """
    # Clamp so that scanning starts from the last valid character.
    i = min(char, len(line_text)) - 1
    paren_depth = 0
    while i >= 0:
        c = line_text[i]
        if c == ")":
            paren_depth += 1
        elif c == "(":
            if paren_depth == 0:
                # Found the opening paren.  Skip whitespace before it.
                j = i - 1
                while j >= 0 and line_text[j] in (" ", "\t"):
                    j -= 1
                if j < 0:
                    return None
                # Quoted identifier: "BlockName"(
                if line_text[j] == '"':
                    open_q = line_text.rfind('"', 0, j)
                    if open_q == -1:
                        return None
                    return line_text[open_q + 1 : j]
                # Hash-prefixed or plain identifier.
                end = j + 1
                while j >= 0 and (line_text[j].isalnum() or line_text[j] == "_"):
                    j -= 1
                # Skip optional '#' prefix.
                if j >= 0 and line_text[j] == "#":
                    j -= 1
                name = line_text[j + 1 : end].lstrip("#")
                return name if name else None
            paren_depth -= 1
        i -= 1
    return None


def _text_between_paren_and_cursor(line_text: str, char: int) -> str | None:
    """Return the text between the opening ``(`` and the cursor position.

    *char* may be equal to ``len(line_text)`` (cursor past the end of the line).
    """
    # Clamp to the last valid character.
    i = min(char, len(line_text)) - 1
    paren_depth = 0
    while i >= 0:
        c = line_text[i]
        if c == ")":
            paren_depth += 1
        elif c == "(":
            if paren_depth == 0:
                return line_text[i + 1 : char]
            paren_depth -= 1
        i -= 1
    return None


def _named_param_completions(
    source: str,
    line: int,
    char: int,
    symbol_table: SymbolTable,
) -> list[lsp.CompletionItem]:
    """Return named-parameter completion items for the call under the cursor."""
    lines = source.splitlines(keepends=False)
    if line >= len(lines):
        return []
    line_text = lines[line]

    call_name = _find_call_name(line_text, char)
    if not call_name:
        return []

    block = symbol_table.lookup_block(call_name)
    if block is None:
        return []

    # Determine already-assigned parameters.
    between = _text_between_paren_and_cursor(line_text, char) or ""
    assigned: set[str] = {m.group(1).lower() for m in _ASSIGNED_PARAM_RE.finditer(between)}

    items: list[lsp.CompletionItem] = []
    for param in block.parameters:
        if param.name.lower() in assigned:
            continue
        # Choose operator based on section kind.
        if param.section_kind == "VAR_OUTPUT":
            insert = f"{param.name} => $0"
        else:
            insert = f"{param.name} := $0"
        items.append(
            lsp.CompletionItem(
                label=param.name,
                kind=lsp.CompletionItemKind.Property,
                insert_text=insert,
                insert_text_format=lsp.InsertTextFormat.Snippet,
                detail=param.type_name,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Member completion (PRD 3.5) — AFTER_DOT context
# ---------------------------------------------------------------------------


def _get_identifier_before_dot(line_text: str, char: int) -> str | None:
    """Return the identifier that immediately precedes the dot at ``char - 1``.

    Handles plain, ``#``-prefixed, and ``"quoted"`` identifiers.
    """
    # The dot is at position char - 1 (cursor is right after the dot).
    dot_pos = char - 1
    if dot_pos < 0 or (dot_pos < len(line_text) and line_text[dot_pos] != "."):
        # Cursor might be right after the dot even if dot_pos is out of bounds
        # (e.g. char == len(line_text)); tolerate that case.
        pass

    j = dot_pos - 1  # character just left of the dot
    if j < 0:
        return None

    if line_text[j] == '"':
        # Quoted identifier: find opening quote.
        open_q = line_text.rfind('"', 0, j)
        if open_q == -1:
            return None
        return line_text[open_q + 1 : j]

    # Plain or hash-prefixed identifier.
    end = j + 1
    while j >= 0 and (line_text[j].isalnum() or line_text[j] == "_"):
        j -= 1
    ident = line_text[j + 1 : end]
    if not ident:
        return None
    # Strip leading '#'
    return ident.lstrip("#")


def _member_completions(
    source: str,
    line: int,
    char: int,
    scope_mgr: ScopeManager,
    uri: str,
    symbol_table: SymbolTable | None = None,
) -> list[lsp.CompletionItem]:
    """Return field completion items for the identifier before the dot."""
    lines = source.splitlines(keepends=False)
    if line >= len(lines):
        return []
    line_text = lines[line]

    ident = _get_identifier_before_dot(line_text, char)
    if not ident:
        return []

    sym = scope_mgr.resolve_name(ident, uri, line)

    target_block = None
    if sym is None:
        return []

    from s7_lsp.semantic.symbol_table import BlockSymbol, VariableSymbol

    if isinstance(sym, BlockSymbol):
        target_block = sym
    elif isinstance(sym, VariableSymbol):
        if symbol_table is not None:
            target_block = symbol_table.lookup_variable_type_block(sym)
        else:
            target_block = scope_mgr.lookup_variable_type_block(sym)

    if target_block is None:
        return []

    items: list[lsp.CompletionItem] = []
    for var in target_block.all_variables:
        items.append(
            lsp.CompletionItem(
                label=var.name,
                kind=lsp.CompletionItemKind.Field,
                detail=var.type_name,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Block name completion (PRD 3.6) — INSIDE_QUOTES context
# ---------------------------------------------------------------------------

_BLOCK_KIND_LABEL: dict[str, str] = {
    "FUNCTION_BLOCK": "FB",
    "FUNCTION": "FC",
    "OB": "OB",
    "DB": "DB",
    "TYPE": "UDT",
}

_BLOCK_KIND_COMPLETION_KIND: dict[str, lsp.CompletionItemKind] = {
    "FUNCTION_BLOCK": lsp.CompletionItemKind.Module,
    "FUNCTION": lsp.CompletionItemKind.Function,
    "OB": lsp.CompletionItemKind.Module,
    "DB": lsp.CompletionItemKind.Struct,
    "TYPE": lsp.CompletionItemKind.TypeParameter,
}


def _block_name_completions(symbol_table: SymbolTable) -> list[lsp.CompletionItem]:
    """Return completion items for all workspace blocks (INSIDE_QUOTES context)."""
    items: list[lsp.CompletionItem] = []
    for block in symbol_table.get_all_blocks():
        kind = _BLOCK_KIND_COMPLETION_KIND.get(block.block_kind, lsp.CompletionItemKind.Module)
        detail = _BLOCK_KIND_LABEL.get(block.block_kind, block.block_kind)
        items.append(
            lsp.CompletionItem(
                label=block.name,
                kind=kind,
                detail=detail,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_completions(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
    symbol_table: SymbolTable | None = None,
) -> lsp.CompletionList:
    """Return completion items at the given position."""
    items: list[lsp.CompletionItem] = []

    # Detect context
    context = get_context(source, position.line, position.character)

    # For GENERAL context (or when no other context matches), offer keyword completions
    if context == ContextKind.GENERAL:
        items.extend(_keyword_completions(source, position.line))
    elif context == ContextKind.AFTER_HASH:
        if symbol_table is not None:
            scope_mgr = ScopeManager(symbol_table)
            visible = scope_mgr.get_visible_variables(document.uri, position.line)
            items.extend(_variable_completions(visible))
    elif context == ContextKind.TYPE_POSITION:
        items.extend(_builtin_type_completions())
        if symbol_table is not None:
            items.extend(_udt_completions(symbol_table))
    elif context == ContextKind.INSIDE_CALL and symbol_table is not None:
        items.extend(
            _named_param_completions(source, position.line, position.character, symbol_table)
        )
    elif context == ContextKind.AFTER_DOT and symbol_table is not None:
        scope_mgr = ScopeManager(symbol_table)
        items.extend(
            _member_completions(
                source,
                position.line,
                position.character,
                scope_mgr,
                document.uri,
                symbol_table,
            )
        )
    elif context == ContextKind.INSIDE_QUOTES and symbol_table is not None:
        items.extend(_block_name_completions(symbol_table))

    return lsp.CompletionList(is_incomplete=False, items=items)
