"""Document and workspace symbol providers.

Provides the file outline (document symbols) and workspace-wide symbol
search. Claude Code uses these for navigation — when it asks "what's
in this file?" or "find the FB named X", these handlers respond.

Document symbols return a hierarchy:
    FUNCTION_BLOCK "MyFB"
    ├── VAR_INPUT
    │   ├── param1 : INT
    │   └── param2 : BOOL
    ├── VAR_OUTPUT
    │   └── result : REAL
    └── VAR_TEMP
        └── tempVar : DINT
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import (
    BlockDeclaration,
    BlockKind,
    ParsedDocument,
    Range,
    VarDeclaration,
    VarSection,
    VarSectionKind,
)

# ─── Block Kind → LSP SymbolKind ─────────────────────────────

_BLOCK_SYMBOL_KIND: dict[BlockKind, lsp.SymbolKind] = {
    BlockKind.FUNCTION_BLOCK: lsp.SymbolKind.Class,
    BlockKind.FUNCTION: lsp.SymbolKind.Function,
    BlockKind.ORGANIZATION_BLOCK: lsp.SymbolKind.Module,
    BlockKind.DATA_BLOCK: lsp.SymbolKind.Struct,
    BlockKind.TYPE: lsp.SymbolKind.TypeParameter,
}

_BLOCK_KIND_LABEL: dict[BlockKind, str] = {
    BlockKind.FUNCTION_BLOCK: "FB",
    BlockKind.FUNCTION: "FC",
    BlockKind.ORGANIZATION_BLOCK: "OB",
    BlockKind.DATA_BLOCK: "DB",
    BlockKind.TYPE: "UDT",
}

_VAR_SECTION_LABEL: dict[VarSectionKind, str] = {
    VarSectionKind.VAR: "VAR",
    VarSectionKind.VAR_INPUT: "VAR_INPUT",
    VarSectionKind.VAR_OUTPUT: "VAR_OUTPUT",
    VarSectionKind.VAR_IN_OUT: "VAR_IN_OUT",
    VarSectionKind.VAR_TEMP: "VAR_TEMP",
    VarSectionKind.VAR_GLOBAL: "VAR_GLOBAL",
    VarSectionKind.VAR_EXTERNAL: "VAR_EXTERNAL",
    VarSectionKind.VAR_CONSTANT: "CONSTANT",
    VarSectionKind.VAR_RETAIN: "RETAIN",
}


# ─── Document Symbols ────────────────────────────────────────


def get_document_symbols(document: ParsedDocument) -> list[lsp.DocumentSymbol]:
    """Return hierarchical document symbols for a parsed document.

    Each block becomes a top-level symbol, with VAR sections and their
    declarations nested underneath.
    """
    symbols: list[lsp.DocumentSymbol] = []

    for block in document.blocks:
        block_symbol = _block_to_symbol(block)
        symbols.append(block_symbol)

    return symbols


def _block_to_symbol(block: BlockDeclaration) -> lsp.DocumentSymbol:
    """Convert a block declaration to an LSP DocumentSymbol with children."""
    kind_label = _BLOCK_KIND_LABEL.get(block.kind, "")
    detail = kind_label
    if block.return_type:
        detail = f"{kind_label} → {block.return_type}"
    if block.version:
        detail += f" v{block.version}"

    block_range = _to_lsp_range(block.range)

    children: list[lsp.DocumentSymbol] = []
    for section in block.var_sections:
        section_symbol = _var_section_to_symbol(section)
        children.append(section_symbol)

    return lsp.DocumentSymbol(
        name=block.name,
        detail=detail,
        kind=_BLOCK_SYMBOL_KIND.get(block.kind, lsp.SymbolKind.Module),
        range=block_range,
        selection_range=block_range,
        children=children if children else None,
    )


def _var_section_to_symbol(section: VarSection) -> lsp.DocumentSymbol:
    """Convert a VAR section to a DocumentSymbol containing its declarations."""
    label = _VAR_SECTION_LABEL.get(section.kind, "VAR")
    section_range = _to_lsp_range(section.range)

    children: list[lsp.DocumentSymbol] = []
    for decl in section.declarations:
        children.append(_var_decl_to_symbol(decl))

    return lsp.DocumentSymbol(
        name=label,
        detail=f"{len(section.declarations)} variable(s)",
        kind=lsp.SymbolKind.Namespace,
        range=section_range,
        selection_range=section_range,
        children=children if children else None,
    )


def _var_decl_to_symbol(decl: VarDeclaration) -> lsp.DocumentSymbol:
    """Convert a variable declaration to a DocumentSymbol."""
    decl_range = _to_lsp_range(decl.range)

    return lsp.DocumentSymbol(
        name=decl.name,
        detail=decl.type_name,
        kind=lsp.SymbolKind.Variable,
        range=decl_range,
        selection_range=decl_range,
    )


# ─── Workspace Symbols ───────────────────────────────────────


def search_workspace_symbols(
    query: str, documents: dict[str, ParsedDocument]
) -> list[lsp.SymbolInformation]:
    """Search for symbols across the workspace matching a query string.

    Claude Code uses this when searching for a block or variable by name
    across all open files.
    """
    results: list[lsp.SymbolInformation] = []
    query_lower = query.lower()

    for uri, doc in documents.items():
        for block in doc.blocks:
            if query_lower in block.name.lower():
                results.append(
                    lsp.SymbolInformation(
                        name=block.name,
                        kind=_BLOCK_SYMBOL_KIND.get(block.kind, lsp.SymbolKind.Module),
                        location=lsp.Location(
                            uri=uri,
                            range=_to_lsp_range(block.range),
                        ),
                        container_name=_BLOCK_KIND_LABEL.get(block.kind),
                    )
                )

            # Also search within variable declarations
            for section in block.var_sections:
                for decl in section.declarations:
                    if query_lower in decl.name.lower():
                        results.append(
                            lsp.SymbolInformation(
                                name=decl.name,
                                kind=lsp.SymbolKind.Variable,
                                location=lsp.Location(
                                    uri=uri,
                                    range=_to_lsp_range(decl.range),
                                ),
                                container_name=block.name,
                            )
                        )

    return results


# ─── Helpers ──────────────────────────────────────────────────


def _to_lsp_range(r: Range) -> lsp.Range:
    """Convert our AST Range to LSP Range."""

    return lsp.Range(
        start=lsp.Position(line=r.start.line, character=r.start.character),
        end=lsp.Position(line=r.end.line, character=r.end.character),
    )
