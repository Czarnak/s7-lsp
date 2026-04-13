"""Auto-completion provider — STUB (Phase 3).

Will provide:
- Keyword completion (IF, THEN, END_IF, etc.)
- Variable completion (in-scope variables with # prefix)
- Type completion (BOOL, INT, REAL, etc.)
- Named parameter completion (param_name :=)
- Block name completion ("MyFB", "MyDB")
- Snippet templates (IF...END_IF, FOR...END_FOR)
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument


def get_completions(
    document: ParsedDocument,
    position: lsp.Position,
    source: str,
) -> lsp.CompletionList:
    """Return completion items at the given position. STUB."""
    return lsp.CompletionList(is_incomplete=False, items=[])
