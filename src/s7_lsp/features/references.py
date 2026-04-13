"""Find-references provider (Phase 2).

Provides:
- Find all usages of a variable within the file where its block is defined
- Find all call sites of a function/FB across all open documents
- Find all uses of a UDT across the workspace
- Cross-file reference search for BlockSymbols
"""

from __future__ import annotations

import re

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.utils import word_at_position
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import BlockSymbol, SymbolTable, VariableSymbol


def get_references(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
    symbol_table: SymbolTable | None = None,
    include_declaration: bool = False,
    documents: dict[str, str] | None = None,
) -> list[lsp.Location]:
    """Return all reference locations for the symbol at *position*.

    Parameters
    ----------
    document:
        The parsed document in which the cursor resides.
    position:
        Zero-based line/character of the cursor.
    source:
        Raw source text of the document at *document.uri*.
    symbol_table:
        Workspace-wide symbol registry. If ``None``, returns ``[]``.
    include_declaration:
        When ``True``, prepend the symbol's definition location to the results.
    documents:
        Mapping of URI -> source text for all open documents. Used for
        cross-file scanning of BlockSymbol references. When ``None``, only the
        current *source* is scanned.
    """
    # Step 1: extract the word under the cursor.
    word_info = word_at_position(source, position.line, position.character)
    if word_info is None or symbol_table is None:
        return []

    # Step 2: create scope manager and resolve the symbol.
    scope_manager = ScopeManager(symbol_table)
    symbol = scope_manager.resolve_name(word_info.word, document.uri, position.line)
    if symbol is None:
        return []

    locations: list[lsp.Location] = []

    if isinstance(symbol, VariableSymbol):
        # Variable: scan only the file where the variable's block is defined.
        target_uri = symbol.definition_uri
        if documents is not None and target_uri in documents:
            target_source = documents[target_uri]
        elif target_uri == document.uri:
            target_source = source
        else:
            # Fall back to current source when target doc is not available.
            target_source = source
            target_uri = document.uri

        # Build regex pattern: hash-prefixed or plain word-boundary.
        if word_info.prefix == "#":
            pattern = re.compile(r"\#" + re.escape(symbol.name) + r"\b", re.IGNORECASE)
        else:
            pattern = re.compile(r"\b" + re.escape(symbol.name) + r"\b", re.IGNORECASE)

        locations = _find_occurrences(target_source, pattern, target_uri)

        if include_declaration:
            decl_location = _symbol_location(symbol)
            locations = [decl_location, *locations]

    elif isinstance(symbol, BlockSymbol):
        # Block: scan all open documents (or just current source).
        scan_docs = documents if documents is not None else {document.uri: source}

        # Match both quoted form "BlockName" and plain \bBlockName\b.
        pattern = re.compile(
            r'"' + re.escape(symbol.name) + r'"' + r"|" + r"\b" + re.escape(symbol.name) + r"\b",
            re.IGNORECASE,
        )

        for uri, doc_source in scan_docs.items():
            locations.extend(_find_occurrences(doc_source, pattern, uri))

        if include_declaration:
            decl_location = _symbol_location(symbol)
            locations = [decl_location, *locations]

    return locations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_occurrences(source: str, pattern: re.Pattern, uri: str) -> list[lsp.Location]:
    """Scan *source* line-by-line for *pattern* and return LSP Location objects."""
    if not source:
        return []
    locations: list[lsp.Location] = []
    for line_num, line_text in enumerate(source.splitlines()):
        for match in pattern.finditer(line_text):
            start_char = match.start()
            end_char = match.end()
            locations.append(
                lsp.Location(
                    uri=uri,
                    range=lsp.Range(
                        start=lsp.Position(line=line_num, character=start_char),
                        end=lsp.Position(line=line_num, character=end_char),
                    ),
                )
            )
    return locations


def _symbol_location(symbol) -> lsp.Location:
    """Convert a Symbol's definition range to an LSP Location."""
    return lsp.Location(
        uri=symbol.definition_uri,
        range=lsp.Range(
            start=lsp.Position(
                line=symbol.definition_range_start_line,
                character=symbol.definition_range_start_char,
            ),
            end=lsp.Position(
                line=symbol.definition_range_end_line,
                character=symbol.definition_range_end_char,
            ),
        ),
    )
