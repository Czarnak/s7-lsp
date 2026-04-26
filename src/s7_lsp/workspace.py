"""Workspace document manager.

Tracks open documents, routes files to the correct parser based on
extension, and caches parsed results. The server delegates all
document state management here.

Design decisions:
- We store both raw source text and parsed results per document.
  Raw text is needed for position-based lookups (hover, completion).
- Parsing happens on every change (didChange). For typical PLC files
  (< 5k lines), this is fast enough. If it becomes a bottleneck,
  we can add debouncing or incremental parsing later.
- The extension → parser routing is centralized here so the server
  doesn't need to know about parser internals.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.parsers.awl_parser import parse_awl
from s7_lsp.parsers.resource_parser import parse_resource
from s7_lsp.parsers.scl_parser import parse_scl
from s7_lsp.semantic.symbol_table import SymbolTable

logger = logging.getLogger(__name__)

# Extension → language ID mapping used by LSP clients
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".scl": "siemens-scl",
    ".st": "siemens-scl",
    ".s7dcl": "siemens-scl",
    ".udt": "siemens-scl",
    ".db": "siemens-scl",
    ".s7res": "siemens-resource",
    ".awl": "siemens-awl",
}

# Language ID → parser function
_LANGUAGE_PARSERS = {
    "siemens-scl": parse_scl,
    "siemens-resource": parse_resource,
    "siemens-awl": parse_awl,
}


class Workspace:
    """Manages document state across the workspace.

    Stores source text and parsed results for all tracked documents.
    Documents are tracked when opened (didOpen) and untracked when
    closed (didClose).
    """

    def __init__(self) -> None:
        self._sources: dict[str, str] = {}
        self._parsed: dict[str, ParsedDocument] = {}
        self._symbol_table = SymbolTable()

    @property
    def documents(self) -> dict[str, ParsedDocument]:
        """All currently parsed documents, keyed by URI."""
        return self._parsed

    @property
    def symbol_table(self) -> SymbolTable:
        """Workspace-wide symbol registry."""
        return self._symbol_table

    def open_document(self, uri: str, source: str) -> ParsedDocument:
        """Register and parse a newly opened document.

        Args:
            uri: Document URI (file:///path/to/file.scl)
            source: Full document text.

        Returns:
            Parsed document with blocks and diagnostics.
        """
        self._sources[uri] = source
        return self._parse(uri)

    def update_document(self, uri: str, source: str) -> ParsedDocument:
        """Update source text and re-parse.

        Called on every textDocument/didChange event.

        Args:
            uri: Document URI.
            source: Updated full document text.

        Returns:
            Re-parsed document.
        """
        self._sources[uri] = source
        return self._parse(uri)

    def close_document(self, uri: str) -> None:
        """Remove a document from tracking.

        Called on textDocument/didClose.
        """
        self._sources.pop(uri, None)
        self._parsed.pop(uri, None)
        self._symbol_table.remove_document(uri)

    def get_document(self, uri: str) -> ParsedDocument | None:
        """Get the most recent parsed result for a document."""
        return self._parsed.get(uri)

    def get_source(self, uri: str) -> str | None:
        """Get the current source text for a document."""
        return self._sources.get(uri)

    def get_language_id(self, uri: str) -> str | None:
        """Determine the language ID from a document URI's extension."""
        ext = PurePosixPath(uri).suffix.lower()
        return _EXTENSION_TO_LANGUAGE.get(ext)

    def _parse(self, uri: str) -> ParsedDocument:
        """Route to the correct parser based on file extension."""
        source = self._sources.get(uri, "")
        language_id = self.get_language_id(uri)

        if language_id is None:
            logger.warning("Unknown file extension for URI: %s", uri)
            doc = ParsedDocument(uri=uri)
            self._parsed[uri] = doc
            return doc

        parser_fn = _LANGUAGE_PARSERS.get(language_id)
        if parser_fn is None:
            logger.warning("No parser registered for language: %s", language_id)
            doc = ParsedDocument(uri=uri)
            self._parsed[uri] = doc
            return doc

        doc = parser_fn(source, uri)
        self._parsed[uri] = doc

        self._symbol_table.remove_document(uri)
        self._symbol_table.add_from_document(uri, doc.blocks)

        logger.debug(
            "Parsed %s: %d block(s), %d diagnostic(s)",
            uri,
            len(doc.blocks),
            len(doc.diagnostics),
        )

        return doc
