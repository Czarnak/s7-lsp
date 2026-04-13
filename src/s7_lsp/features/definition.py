"""Go-to-definition provider — STUB (Phase 2).

Will provide:
- Jump to variable declaration from usage (#myVar → VAR section)
- Jump to block definition from call ("MyFB"(...) → FB declaration)
- Jump to type definition from usage (myVar : "MyUDT" → TYPE)
- Cross-file resolution (requires workspace-level symbol table)
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument


def get_definition(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
) -> lsp.Location | list[lsp.Location] | None:
    """Return the definition location for the symbol at position. STUB."""
    return None
