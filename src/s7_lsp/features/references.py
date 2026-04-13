"""Find-references provider — STUB (Phase 2).

Will provide:
- Find all usages of a variable within a block
- Find all call sites of a function/FB
- Find all uses of a UDT across the workspace
- Cross-file reference search
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument


def get_references(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
    include_declaration: bool = True,
) -> list[lsp.Location]:
    """Return all references to the symbol at position. STUB."""
    return []
