"""S7-LSP server — pygls-based Language Server Protocol implementation.

This module creates and configures the LSP server, registering handlers
for each protocol message. The handlers are intentionally thin — they
extract parameters, delegate to the workspace and feature modules,
and return LSP protocol types.

Architecture:
    Client (Claude Code / VS Code)
      ↕ JSON-RPC over stdio
    Server (this module)
      → Workspace (document state, parser routing)
      → Features (diagnostics, symbols, hover, etc.)
      → Parsers (SCL, Resource, AWL)
"""

from __future__ import annotations

import logging

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from s7_lsp import __version__
from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.completion import get_completions
from s7_lsp.features.definition import get_definition
from s7_lsp.features.diagnostics import get_diagnostics
from s7_lsp.features.hover import get_hover
from s7_lsp.features.references import get_references
from s7_lsp.features.symbols import get_document_symbols, search_workspace_symbols
from s7_lsp.workspace import Workspace

logger = logging.getLogger(__name__)


def create_server() -> LanguageServer:
    """Create and configure the S7-LSP language server.

    Returns a fully configured LanguageServer ready to start.
    Call server.start_io() to begin communication over stdio.
    """
    server = LanguageServer(
        name="s7-lsp",
        version=__version__,
    )

    # Shared workspace state — lives for the lifetime of the server process
    workspace = Workspace()

    # ─── Lifecycle ────────────────────────────────────────

    @server.feature(lsp.INITIALIZE)
    def on_initialize(params: lsp.InitializeParams) -> lsp.InitializeResult:
        """Handle the initialize request — declare server capabilities.

        This tells the client what features we support. Claude Code
        checks these capabilities to know which LSP tools to enable.
        """
        logger.info("Initializing S7-LSP v%s", __version__)

        return lsp.InitializeResult(
            capabilities=lsp.ServerCapabilities(
                # Sync: we want full document content on every change
                # (incremental sync is an optimization for Phase 2+)
                text_document_sync=lsp.TextDocumentSyncOptions(
                    open_close=True,
                    change=lsp.TextDocumentSyncKind.Full,
                    save=lsp.SaveOptions(include_text=True),
                ),
                # Phase 1: active
                diagnostic_provider=lsp.DiagnosticOptions(
                    inter_file_dependencies=False,
                    workspace_diagnostics=False,
                ),
                document_symbol_provider=True,
                workspace_symbol_provider=True,
                # Phase 2: stubs (registered so client knows we'll support them)
                hover_provider=True,
                definition_provider=True,
                references_provider=True,
                # Phase 3: stubs
                completion_provider=lsp.CompletionOptions(
                    trigger_characters=[".", "#", '"'],
                ),
            ),
            server_info=lsp.ServerInfo(
                name="s7-lsp",
                version=__version__,
            ),
        )

    # ─── Document Sync ────────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def on_did_open(params: lsp.DidOpenTextDocumentParams) -> None:
        """Handle document open — parse and publish initial diagnostics."""
        uri = params.text_document.uri
        source = params.text_document.text

        logger.debug("Document opened: %s", uri)
        doc = workspace.open_document(uri, source)
        _publish_diagnostics(server, uri, doc, workspace.symbol_table)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def on_did_change(params: lsp.DidChangeTextDocumentParams) -> None:
        """Handle document change — re-parse and update diagnostics.

        We use Full sync, so the entire document text is in the first
        content change event.
        """
        uri = params.text_document.uri
        if not params.content_changes:
            return

        # Full sync: the last content change has the complete text
        source = params.content_changes[-1].text

        doc = workspace.update_document(uri, source)
        _publish_diagnostics(server, uri, doc, workspace.symbol_table)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
    def on_did_close(params: lsp.DidCloseTextDocumentParams) -> None:
        """Handle document close — clear diagnostics and stop tracking."""
        uri = params.text_document.uri
        logger.debug("Document closed: %s", uri)

        workspace.close_document(uri)
        # Clear diagnostics for the closed file
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def on_did_save(params: lsp.DidSaveTextDocumentParams) -> None:
        """Handle document save — re-parse if text is included."""
        uri = params.text_document.uri
        if params.text is not None:
            doc = workspace.update_document(uri, params.text)
            _publish_diagnostics(server, uri, doc, workspace.symbol_table)

    # ─── Document Symbols ─────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def on_document_symbol(
        params: lsp.DocumentSymbolParams,
    ) -> list[lsp.DocumentSymbol] | None:
        """Return document symbols (file outline).

        Claude Code uses this to understand the structure of an SCL file:
        which blocks are defined, what variables they declare.
        """
        doc = workspace.get_document(params.text_document.uri)
        if doc is None:
            return None
        return get_document_symbols(doc)

    # ─── Workspace Symbols ────────────────────────────────

    @server.feature(lsp.WORKSPACE_SYMBOL)
    def on_workspace_symbol(
        params: lsp.WorkspaceSymbolParams,
    ) -> list[lsp.SymbolInformation] | None:
        """Search for symbols across all open documents.

        Claude Code uses this when it needs to find a block or variable
        by name across the workspace.
        """
        return search_workspace_symbols(params.query, workspace.documents)

    # ─── Hover ────────────────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def on_hover(params: lsp.HoverParams) -> lsp.Hover | None:
        """Return hover information at cursor position. Phase 2."""
        doc = workspace.get_document(params.text_document.uri)
        source = workspace.get_source(params.text_document.uri)
        if doc is None or source is None:
            return None
        return get_hover(doc, params.position, source, workspace.symbol_table)

    # ─── Go-to-Definition ─────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
    def on_definition(
        params: lsp.DefinitionParams,
    ) -> lsp.Location | list[lsp.Location] | None:
        """Return definition location for symbol at cursor. Phase 2."""
        doc = workspace.get_document(params.text_document.uri)
        source = workspace.get_source(params.text_document.uri)
        if doc is None or source is None:
            return None
        return get_definition(doc, params.position, source, workspace.symbol_table)

    # ─── Find References ──────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_REFERENCES)
    def on_references(params: lsp.ReferenceParams) -> list[lsp.Location] | None:
        """Return all references to symbol at cursor. Phase 2."""
        doc = workspace.get_document(params.text_document.uri)
        source = workspace.get_source(params.text_document.uri)
        if doc is None or source is None:
            return None
        docs = {
            uri: src
            for uri in workspace.documents
            if (src := workspace.get_source(uri)) is not None
        }
        return get_references(
            doc,
            params.position,
            source,
            workspace.symbol_table,
            include_declaration=params.context.include_declaration,
            documents=docs,
        )

    # ─── Completion ───────────────────────────────────────

    @server.feature(lsp.TEXT_DOCUMENT_COMPLETION)
    def on_completion(params: lsp.CompletionParams) -> lsp.CompletionList | None:
        """Return completion items at cursor position. Phase 3."""
        doc = workspace.get_document(params.text_document.uri)
        source = workspace.get_source(params.text_document.uri)
        if doc is None or source is None:
            return None
        return get_completions(doc, params.position, source, workspace.symbol_table)

    return server


# ─── Helpers ──────────────────────────────────────────────────


def _publish_diagnostics(
    server: LanguageServer,
    uri: str,
    doc: ParsedDocument,
    symbol_table=None,
) -> None:
    """Convert parsed diagnostics to LSP format and publish them."""

    lsp_diagnostics = get_diagnostics(doc, symbol_table)
    server.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=lsp_diagnostics)
    )

    if lsp_diagnostics:
        logger.debug("Published %d diagnostic(s) for %s", len(lsp_diagnostics), uri)
