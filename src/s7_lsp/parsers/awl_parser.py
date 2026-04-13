"""AWL/STL parser — STUB (Phase 5).

Will handle .awl files containing Siemens Statement List code.
STL is a stack-based assembly-like language, fundamentally different
from SCL, requiring its own grammar and semantic analysis.
"""

from __future__ import annotations

from s7_lsp.ast_nodes import ParsedDocument


def parse_awl(source: str, uri: str = "") -> ParsedDocument:
    """Parse an AWL/STL file. Currently returns an empty document."""
    return ParsedDocument(uri=uri)
