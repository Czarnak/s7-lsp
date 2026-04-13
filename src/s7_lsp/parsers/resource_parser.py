"""Resource file parser — STUB (Phase 4).

Will handle .s7res files containing multilingual text definitions
and other configuration data in YAML-like format.
"""

from __future__ import annotations

from s7_lsp.ast_nodes import ParsedDocument


def parse_resource(source: str, uri: str = "") -> ParsedDocument:
    """Parse a resource file. Currently returns an empty document."""
    return ParsedDocument(uri=uri)
