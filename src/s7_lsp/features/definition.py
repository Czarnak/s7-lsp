"""Go-to-definition provider (Phase 2).

Provides:
- Jump to variable declaration from usage (#myVar -> VAR section)
- Jump to block definition from call ("MyFB"(...) -> FB declaration)
- Jump to type definition from usage (myVar : "MyUDT" -> TYPE)
- Cross-file resolution (requires workspace-level symbol table)
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.utils import ContextKind, get_context, word_at_position
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import Symbol, SymbolTable


def _symbol_to_location(symbol: Symbol) -> lsp.Location:
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


def _strip_sigil(token: str) -> str:
    """Strip leading '#' or surrounding '"..."' from a chain token.

    Examples:
        '#myVar'  -> 'myVar'
        '"MyDB"'  -> 'MyDB'
        'plain'   -> 'plain'
    """
    if token.startswith("#"):
        return token[1:]
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return token[1:-1]
    return token


def get_definition(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
    symbol_table: SymbolTable | None = None,
) -> lsp.Location | None:
    """Return the definition location for the symbol at *position*.

    Parameters
    ----------
    document:
        The parsed document in which the cursor resides.
    position:
        Zero-based LSP cursor position.
    source:
        Raw source text of the document (used for word extraction).
    symbol_table:
        Workspace-wide symbol registry.  When ``None``, returns ``None``.

    Returns
    -------
    lsp.Location | None
        The location of the symbol's declaration, or ``None`` when the symbol
        cannot be resolved.
    """
    # Step 1: Guard checks.
    if symbol_table is None:
        return None

    word_info = word_at_position(source, position.line, position.character)
    if word_info is None:
        return None

    scope_manager = ScopeManager(symbol_table)

    resolved: Symbol | None = None

    # Step 2: Member-access chain (e.g. "DB_Motor".Speed or #struct.field).
    if len(word_info.chain) > 1:
        # Strip sigils from each segment before passing to resolve_member_chain.
        clean_parts = [_strip_sigil(seg) for seg in word_info.chain]
        resolved = scope_manager.resolve_member_chain(clean_parts, document.uri, position.line)
        if resolved is not None:
            return _symbol_to_location(resolved)
        # Fall through — chain resolution may fail for the root segment; do not
        # fall through to single-name logic because we already have the answer.
        return None

    # Step 3: Hash-prefixed local variable (#localVar).
    if word_info.prefix == "#":
        resolved = scope_manager.resolve_name(word_info.word, document.uri, position.line)
        if resolved is not None:
            return _symbol_to_location(resolved)
        return None

    # Step 4: Quoted block name ("MyFB").
    if word_info.prefix == '"':
        resolved = symbol_table.lookup_block(word_info.word)
        if resolved is not None:
            return _symbol_to_location(resolved)
        return None

    # Step 5: Plain identifier — try local variable first, then block name.
    resolved = scope_manager.resolve_name(word_info.word, document.uri, position.line)
    if resolved is not None:
        return _symbol_to_location(resolved)

    # Step 6: If in TYPE_POSITION context (after ':'), also try block/type lookup.
    context = get_context(source, position.line, position.character)
    if context == ContextKind.TYPE_POSITION:
        resolved = symbol_table.lookup_block(word_info.word)
        if resolved is not None:
            return _symbol_to_location(resolved)

    return None
