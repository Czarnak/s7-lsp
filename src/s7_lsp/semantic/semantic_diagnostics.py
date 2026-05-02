"""Semantic diagnostics for SCL source files.

Performs the following checks after a successful parse:

1. Duplicate variable declarations within a block (Warning).
2. Variable type references to unknown UDTs — not a built-in type and not a
   registered block in the symbol table (Warning).
3. Undeclared variable usage via ``#identifier`` syntax inside a block body (Error).
4. Assignment to VAR_INPUT variables inside FUNCTION_BLOCK bodies (Error).
"""

from __future__ import annotations

import re

from s7_lsp.ast_nodes import (
    BlockDeclaration,
    BlockKind,
    Diagnostic,
    ParsedDocument,
    Position,
    Range,
    VarSectionKind,
)
from s7_lsp.semantic.symbol_table import SymbolTable
from s7_lsp.semantic.type_checker import is_builtin_type

# Pattern to match #identifier usage in SCL source bodies.
_HASH_IDENT_RE = re.compile(r"#([A-Za-z_][A-Za-z0-9_]*)")

# Pattern to match assignment to a hash-prefixed variable: #varName :=
_HASH_ASSIGN_RE = re.compile(r"#([A-Za-z_][A-Za-z0-9_]*)\s*:=")

# Type names that are compound/structural and should be skipped for UDT checks.
_SKIP_TYPE_PREFIXES = ("ARRAY", "STRUCT")

# Mapping of BlockKind to expected closing keyword (PRD 2.6)
_BLOCK_KIND_TO_END = {
    BlockKind.FUNCTION_BLOCK: "END_FUNCTION_BLOCK",
    BlockKind.FUNCTION: "END_FUNCTION",
    BlockKind.ORGANIZATION_BLOCK: "END_ORGANIZATION_BLOCK",
    BlockKind.DATA_BLOCK: "END_DATA_BLOCK",
    BlockKind.TYPE: "END_TYPE",
}

# Pattern to match any END_* keyword
_END_KW_RE = re.compile(
    r"\b(END_FUNCTION_BLOCK|END_FUNCTION|END_ORGANIZATION_BLOCK|END_DATA_BLOCK|END_TYPE)\b",
    re.IGNORECASE,
)


def get_semantic_diagnostics(
    doc: ParsedDocument,
    symbol_table: SymbolTable,
) -> list[Diagnostic]:
    """Return semantic diagnostics for *doc* using *symbol_table*.

    Returns an empty list when called on a document that failed to parse
    (i.e. ``doc.diagnostics`` contains Error-level entries), because the
    AST may be incomplete and source-text offsets may be unreliable.

    Parameters
    ----------
    doc:
        The fully parsed document whose blocks will be analysed.
    symbol_table:
        Workspace-wide symbol table used to resolve block/type references.
    """
    # Guard: skip semantic analysis when the parse produced errors.
    if _has_parse_errors(doc):
        return []

    results: list[Diagnostic] = []

    source_lines = doc.source.splitlines() if doc.source else []

    for block in doc.blocks:
        results.extend(_check_duplicate_declarations(block))
        results.extend(_check_undeclared_type_references(block, symbol_table))
        results.extend(_check_cross_document_duplicate(block, symbol_table, doc.uri))
        if source_lines:
            results.extend(_check_undeclared_variable_usage(block, source_lines))
            if block.kind == BlockKind.FUNCTION_BLOCK:
                results.extend(_check_var_input_assignment(block, source_lines))
            # Check END_* keyword mismatches (PRD 2.6)
            results.extend(_check_end_keyword_mismatch(block, source_lines))

    return results


# ─── Guard helper ─────────────────────────────────────────────


def _has_parse_errors(doc: ParsedDocument) -> bool:
    """Return True if *doc* has any Error-severity (severity == 1) diagnostics."""
    return any(d.severity == 1 for d in doc.diagnostics)


# ─── Check 1: Duplicate variable declarations ──────────────────


def _check_duplicate_declarations(block: BlockDeclaration) -> list[Diagnostic]:
    """Warn when two variables in the same block share the same name (case-insensitive)."""
    seen: dict[str, str] = {}  # lowercase_name -> original name (first occurrence)
    diagnostics: list[Diagnostic] = []

    for section in block.var_sections:
        for decl in section.declarations:
            key = decl.name.lower()
            if key in seen:
                diagnostics.append(
                    Diagnostic(
                        message=(
                            f"Duplicate variable declaration '{decl.name}' in block "
                            f"'{block.name}' (first declared as '{seen[key]}')"
                        ),
                        range=decl.range,
                        severity=2,  # Warning
                    )
                )
            else:
                seen[key] = decl.name

    return diagnostics


# ─── Check 2: Undeclared type/block references ─────────────────


def _check_undeclared_type_references(
    block: BlockDeclaration,
    symbol_table: SymbolTable,
) -> list[Diagnostic]:
    """Warn when a variable's type is neither a built-in type nor a known block."""
    diagnostics: list[Diagnostic] = []

    for section in block.var_sections:
        for decl in section.declarations:
            type_name = decl.type_name.strip()

            # Skip compound structural types.
            upper = type_name.upper()
            if any(upper.startswith(prefix) for prefix in _SKIP_TYPE_PREFIXES):
                continue

            # Skip empty type names (malformed AST — parser issue, not semantic).
            if not type_name:
                continue

            # Skip built-in types.
            if is_builtin_type(type_name):
                continue

            # Skip types that are registered blocks (UDTs, FBs used as types, etc.).
            if symbol_table.lookup_block(type_name) is not None:
                continue

            diagnostics.append(
                Diagnostic(
                    message=(
                        f"Unknown type '{type_name}' for variable '{decl.name}' "
                        f"in block '{block.name}'"
                    ),
                    range=decl.range,
                    severity=2,  # Warning
                )
            )

    return diagnostics


# ─── Check: Cross-document duplicate block name ────────────────


def _check_cross_document_duplicate(
    block: BlockDeclaration,
    symbol_table: SymbolTable,
    current_uri: str,
) -> list[Diagnostic]:
    """Warn when the same block name is defined in another open document."""
    all_symbols = symbol_table.lookup_all_blocks(block.name)
    other_uris = [sym.definition_uri for sym in all_symbols if sym.definition_uri != current_uri]
    if not other_uris:
        return []
    short_names = ", ".join(uri.rstrip("/").split("/")[-1] for uri in other_uris)
    return [
        Diagnostic(
            message=f"Block '{block.name}' is already defined in: {short_names}",
            range=block.range,
            severity=2,  # Warning
            source="s7-lsp",
        )
    ]


# ─── Check 3: Undeclared #variable usage ──────────────────────


def _collect_declared_names(block: BlockDeclaration) -> set[str]:
    """Return the set of all declared variable names (lowercase) in *block*."""
    names: set[str] = set()
    for section in block.var_sections:
        for decl in section.declarations:
            names.add(decl.name.lower())
    return names


def _block_body_lines(block: BlockDeclaration, source_lines: list[str]) -> list[tuple[int, str]]:
    """Return (line_index, line_text) pairs for lines inside *block*'s range.

    The block range includes VAR sections, so we return all lines from
    start to end (inclusive).  The caller uses the range to restrict
    scanning to the block body as best we can without a full expression AST.
    """
    start = block.range.start.line
    end = min(block.range.end.line, len(source_lines) - 1)
    return [(i, source_lines[i]) for i in range(start, end + 1)]


def _check_undeclared_variable_usage(
    block: BlockDeclaration,
    source_lines: list[str],
) -> list[Diagnostic]:
    """Report Error for each ``#identifier`` in the block body that is not declared."""
    declared = _collect_declared_names(block)
    diagnostics: list[Diagnostic] = []
    reported: set[str] = set()  # avoid duplicate errors for the same name

    for line_idx, line_text in _block_body_lines(block, source_lines):
        if line_text.lstrip().startswith("//"):
            continue
        code_part, _, _ = line_text.partition("//")
        for match in _HASH_IDENT_RE.finditer(code_part):
            ident = match.group(1)
            if ident.lower() not in declared and ident.lower() not in reported:
                reported.add(ident.lower())
                col_start = match.start()
                col_end = match.end()
                diagnostics.append(
                    Diagnostic(
                        message=(f"Undeclared variable '#{ident}' used in block '{block.name}'"),
                        range=Range(
                            start=Position(line=line_idx, character=col_start),
                            end=Position(line=line_idx, character=col_end),
                        ),
                        severity=1,  # Error
                    )
                )

    return diagnostics


# ─── Check 4: Assignment to VAR_INPUT inside FUNCTION_BLOCK ───


def _collect_var_input_names(block: BlockDeclaration) -> set[str]:
    """Return lowercase names of all VAR_INPUT variables in *block*."""
    names: set[str] = set()
    for section in block.var_sections:
        if section.kind == VarSectionKind.VAR_INPUT:
            for decl in section.declarations:
                names.add(decl.name.lower())
    return names


def _check_var_input_assignment(
    block: BlockDeclaration,
    source_lines: list[str],
) -> list[Diagnostic]:
    """Report Error when a VAR_INPUT variable is assigned to inside a FB body."""
    var_input_names = _collect_var_input_names(block)
    if not var_input_names:
        return []

    diagnostics: list[Diagnostic] = []
    reported: set[str] = set()

    for line_idx, line_text in _block_body_lines(block, source_lines):
        for match in _HASH_ASSIGN_RE.finditer(line_text):
            ident = match.group(1)
            if ident.lower() in var_input_names and ident.lower() not in reported:
                reported.add(ident.lower())
                col_start = match.start()
                col_end = match.end()
                diagnostics.append(
                    Diagnostic(
                        message=(
                            f"Assignment to VAR_INPUT variable '#{ident}' "
                            f"is not allowed inside FUNCTION_BLOCK '{block.name}'"
                        ),
                        range=Range(
                            start=Position(line=line_idx, character=col_start),
                            end=Position(line=line_idx, character=col_end),
                        ),
                        severity=1,  # Error
                    )
                )

    return diagnostics


# ─── Check 5: END_* keyword mismatch ──────────────────────────────


def _check_end_keyword_mismatch(
    block: BlockDeclaration,
    source_lines: list[str],
) -> list[Diagnostic]:
    """Check that each block is closed with the correct END_* keyword (PRD 2.6)."""
    diagnostics: list[Diagnostic] = []

    expected_end = _BLOCK_KIND_TO_END.get(block.kind)
    if expected_end is None:
        return diagnostics

    # Scan the last few lines of the block range for any END_* keyword
    start_line = block.range.start.line
    end_line = block.range.end.line
    search_start = max(start_line, end_line - 5)  # scan last 5 lines of block

    for i in range(search_start, min(end_line + 1, len(source_lines))):
        if i < 0 or i >= len(source_lines):
            continue
        line = source_lines[i]
        match = _END_KW_RE.search(line)
        if match:
            found_end = match.group(1).upper()
            if found_end != expected_end.upper():
                diagnostics.append(
                    Diagnostic(
                        message=(
                            f"Block '{block.name}' ({block.kind.name}) closed with "
                            f"'{found_end}', expected '{expected_end}'"
                        ),
                        range=Range(
                            start=Position(line=i, character=match.start()),
                            end=Position(line=i, character=match.end()),
                        ),
                        severity=2,  # Warning
                    )
                )
            break  # Only report once per block

    return diagnostics
