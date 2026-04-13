"""Hover information provider — STUB (Phase 2).

Will provide:
- Type information on variable hover (#myVar → INT)
- Block signature on block name hover ("MyFB" → FB with params)
- Documentation from comments above declarations
- Named parameter info in function calls
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument


def get_hover(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
) -> lsp.Hover | None:
    """Return hover information at the given position. STUB."""
    return None
