"""AWL/STL parser — STUB (Phase 5).

Will handle .awl files containing Siemens Statement List code.
STL is a stack-based assembly-like language, fundamentally different
from SCL, requiring its own grammar and semantic analysis.
"""

from __future__ import annotations

from lsprotocol.types import Diagnostic, Position, Range

from s7_lsp.ast_nodes import ParsedDocument

_AWL_NOT_SUPPORTED = Diagnostic(
    message="AWL/STL parsing is not yet supported. No code intelligence is available for this file.",
    range=Range(Position(0, 0), Position(0, 0)),
    severity=3,  # Information
    source="s7-lsp",
)


def parse_awl(source: str, uri: str = "") -> ParsedDocument:
    """Parse an AWL/STL file. Returns an informational diagnostic until implemented."""
    doc = ParsedDocument(uri=uri)
    doc.diagnostics.append(_AWL_NOT_SUPPORTED)
    return doc
