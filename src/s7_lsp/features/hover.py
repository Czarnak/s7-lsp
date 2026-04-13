"""Hover information provider (Phase 2).

Provides type information, block signatures, and built-in type documentation
at a cursor position.

Logic:
- Hash-prefixed identifier (#var): resolve to VariableSymbol, show type + section kind
- Double-quoted identifier ("Block"): resolve to BlockSymbol, show block signature
- Member chain (struct.field): resolve chain to VariableSymbol, show type info
- Plain identifier: check built-in type first, then try scope resolution
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.utils import word_at_position
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import BlockSymbol, SymbolTable, VariableSymbol
from s7_lsp.semantic.type_info import get_type_hover_text


def _make_hover(markdown_text: str) -> lsp.Hover:
    """Wrap a markdown string in an lsp.Hover response."""
    return lsp.Hover(
        contents=lsp.MarkupContent(
            kind=lsp.MarkupKind.Markdown,
            value=markdown_text,
        )
    )


def _format_variable_hover(var: VariableSymbol) -> str:
    """Format a VariableSymbol into a markdown hover string."""
    return f"**#{var.name}** : {var.type_name} ({var.section_kind})"


def _format_block_hover(block: BlockSymbol) -> str:
    """Format a BlockSymbol into a markdown block signature string."""
    # Determine readable block kind label
    kind_label_map = {
        "FUNCTION_BLOCK": "FB",
        "FUNCTION": "FC",
        "OB": "OB",
        "DB": "DB",
        "TYPE": "TYPE",
    }
    kind_label = kind_label_map.get(block.block_kind, block.block_kind)

    header = f'**{kind_label} "{block.name}"**'

    # For functions, append return type
    if block.block_kind == "FUNCTION" and block.return_type:
        header += f" : {block.return_type}"

    lines = [header]

    # List parameters (VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT)
    params = list(block.parameters)
    if params:
        lines.append("")
        lines.append("Parameters:")
        for p in params:
            lines.append(f"- {p.name} : {p.type_name} ({p.section_kind})")

    return "\n".join(lines)


def get_hover(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
    symbol_table: SymbolTable | None = None,
) -> lsp.Hover | None:
    """Return hover information at the given position.

    Parameters
    ----------
    document:
        The parsed document for the file being hovered.
    position:
        The LSP Position (0-based line and character).
    source:
        The raw source text of the document.
    symbol_table:
        The workspace symbol table. When None, only built-in type hover is
        available.
    """
    word_info = word_at_position(source, position.line, position.character)
    if word_info is None:
        return None

    scope_manager: ScopeManager | None = None
    if symbol_table is not None:
        scope_manager = ScopeManager(symbol_table)

    # ── Hash-prefixed identifier: #localVar ───────────────────
    if word_info.prefix == "#":
        if scope_manager is None:
            return None
        sym = scope_manager.resolve_name(word_info.word, document.uri, position.line)
        if isinstance(sym, VariableSymbol):
            return _make_hover(_format_variable_hover(sym))
        return None

    # ── Double-quoted identifier: "BlockName" ─────────────────
    if word_info.prefix == '"':
        if symbol_table is None:
            return None
        # Check if this is a member chain ("DB".field) — resolve chain instead
        if len(word_info.chain) > 1 and scope_manager is not None:
            # Strip quote wrappers from chain segments for member resolution
            parts = []
            for seg in word_info.chain:
                if seg.startswith('"') and seg.endswith('"'):
                    parts.append(seg[1:-1])
                elif seg.startswith("#"):
                    parts.append(seg[1:])
                else:
                    parts.append(seg)
            sym = scope_manager.resolve_member_chain(parts, document.uri, position.line)
            if isinstance(sym, VariableSymbol):
                return _make_hover(_format_variable_hover(sym))
        # Simple block name lookup
        block = symbol_table.lookup_block(word_info.word)
        if block is not None:
            return _make_hover(_format_block_hover(block))
        return None

    # ── Member chain: struct.field (len > 1) ──────────────────
    if len(word_info.chain) > 1 and scope_manager is not None:
        # Strip sigils for resolution
        parts = []
        for seg in word_info.chain:
            if seg.startswith('"') and seg.endswith('"'):
                parts.append(seg[1:-1])
            elif seg.startswith("#"):
                parts.append(seg[1:])
            else:
                parts.append(seg)
        sym = scope_manager.resolve_member_chain(parts, document.uri, position.line)
        if isinstance(sym, VariableSymbol):
            return _make_hover(_format_variable_hover(sym))

    # ── Plain identifier: built-in type or scope resolution ───
    # 1. Check built-in type first (case-insensitive)
    type_text = get_type_hover_text(word_info.word)
    if type_text is not None:
        return _make_hover(type_text)

    # 2. Try scope resolution (local variable or block)
    if scope_manager is not None:
        sym = scope_manager.resolve_name(word_info.word, document.uri, position.line)
        if isinstance(sym, VariableSymbol):
            return _make_hover(_format_variable_hover(sym))
        if isinstance(sym, BlockSymbol):
            return _make_hover(_format_block_hover(sym))

    return None
