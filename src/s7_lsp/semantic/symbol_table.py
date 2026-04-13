"""Symbol table for cross-reference resolution (Phase 2).

Provides:
- Registration of all declared symbols (blocks, variables) per document URI
- Per-document invalidation and rebuild
- Lookup by name (case-insensitive for block and variable names)
- Cross-file block/variable registry
"""

from __future__ import annotations

from dataclasses import dataclass, field

from s7_lsp.ast_nodes import BlockDeclaration, BlockKind, VarSectionKind

# ─── Symbol Dataclasses ───────────────────────────────────────


@dataclass(frozen=True)
class Symbol:
    """A named entity in the source code."""

    name: str
    kind: str  # "block" | "variable"
    definition_uri: str
    definition_range_start_line: int
    definition_range_start_char: int
    definition_range_end_line: int
    definition_range_end_char: int


# Forward reference: VariableSymbol is referenced in BlockSymbol.
# We define VariableSymbol first so it is available when BlockSymbol is constructed.


@dataclass(frozen=True)
class VariableSymbol(Symbol):
    """A variable declaration within a block's VAR section."""

    type_name: str = ""
    section_kind: str = "VAR"  # one of the VAR* section kind strings
    block_name: str = ""


@dataclass(frozen=True)
class BlockSymbol(Symbol):
    """A top-level block declaration (FB, FC, OB, DB, TYPE)."""

    block_kind: str = "FUNCTION_BLOCK"  # "FUNCTION_BLOCK"|"FUNCTION"|"OB"|"DB"|"TYPE"
    return_type: str | None = None
    # VAR_INPUT + VAR_OUTPUT + VAR_IN_OUT variables only
    parameters: tuple[VariableSymbol, ...] = field(default_factory=tuple)
    # All variables across all VAR sections
    all_variables: tuple[VariableSymbol, ...] = field(default_factory=tuple)


# ─── Section kind mapping ─────────────────────────────────────

_VAR_SECTION_KIND_NAMES: dict[VarSectionKind, str] = {
    VarSectionKind.VAR: "VAR",
    VarSectionKind.VAR_INPUT: "VAR_INPUT",
    VarSectionKind.VAR_OUTPUT: "VAR_OUTPUT",
    VarSectionKind.VAR_IN_OUT: "VAR_IN_OUT",
    VarSectionKind.VAR_TEMP: "VAR_TEMP",
    VarSectionKind.VAR_GLOBAL: "VAR_GLOBAL",
    VarSectionKind.VAR_EXTERNAL: "VAR_EXTERNAL",
    VarSectionKind.VAR_CONSTANT: "CONSTANT",
    VarSectionKind.VAR_RETAIN: "VAR",
}

_PARAMETER_SECTION_KINDS: set[VarSectionKind] = {
    VarSectionKind.VAR_INPUT,
    VarSectionKind.VAR_OUTPUT,
    VarSectionKind.VAR_IN_OUT,
}

_BLOCK_KIND_NAMES: dict[BlockKind, str] = {
    BlockKind.FUNCTION_BLOCK: "FUNCTION_BLOCK",
    BlockKind.FUNCTION: "FUNCTION",
    BlockKind.ORGANIZATION_BLOCK: "OB",
    BlockKind.DATA_BLOCK: "DB",
    BlockKind.TYPE: "TYPE",
}


# ─── SymbolTable ──────────────────────────────────────────────


class SymbolTable:
    """Tracks all symbols across a workspace.

    Internal storage:
      _blocks: dict[str, BlockSymbol]
          lowercase block name -> BlockSymbol
      _document_blocks: dict[str, set[str]]
          uri -> set of lowercase block names registered from that document
    """

    def __init__(self) -> None:
        self._blocks: dict[str, BlockSymbol] = {}
        self._document_blocks: dict[str, set[str]] = {}

    # ── Public API ────────────────────────────────────────────

    def add_from_document(self, uri: str, blocks: list[BlockDeclaration]) -> None:
        """Register all symbols from a parsed document.

        If the URI already has symbols registered, they are removed first
        (automatic per-document invalidation).

        Parameters
        ----------
        uri:
            The document URI (e.g. ``file:///path/to/file.scl``).
        blocks:
            A list of :class:`~s7_lsp.ast_nodes.BlockDeclaration` objects
            produced by the parser.
        """
        # Invalidate old entries for this URI first.
        self.remove_document(uri)

        registered_names: set[str] = set()

        for block in blocks:
            block_symbol = self._build_block_symbol(uri, block)
            key = block_symbol.name.lower()
            self._blocks[key] = block_symbol
            registered_names.add(key)

        self._document_blocks[uri] = registered_names

    def remove_document(self, uri: str) -> None:
        """Remove all symbols that were registered from *uri*."""
        if uri not in self._document_blocks:
            return
        for name_key in self._document_blocks.pop(uri):
            self._blocks.pop(name_key, None)

    def lookup_block(self, name: str) -> BlockSymbol | None:
        """Case-insensitive block name lookup.

        Returns ``None`` if no block with that name is registered.
        """
        return self._blocks.get(name.lower())

    def lookup_variable(self, name: str, block_name: str) -> VariableSymbol | None:
        """Find a variable by name within a specific block.

        Comparison is case-insensitive for both *name* and *block_name*.
        Returns ``None`` if the block or variable is not found.
        """
        block = self.lookup_block(block_name)
        if block is None:
            return None
        name_lower = name.lower()
        for var in block.all_variables:
            if var.name.lower() == name_lower:
                return var
        return None

    def get_all_blocks(self) -> list[BlockSymbol]:
        """Return all registered :class:`BlockSymbol` objects."""
        return list(self._blocks.values())

    def get_variables_in_block(self, block_name: str) -> list[VariableSymbol]:
        """Return all variables declared in the named block.

        Returns an empty list if the block is not found.
        """
        block = self.lookup_block(block_name)
        if block is None:
            return []
        return list(block.all_variables)

    def get_block_at(self, uri: str, line: int) -> BlockSymbol | None:
        """Return the block that contains *line* in *uri*, or ``None``.

        A block is considered to contain *line* when::

            block.definition_range_start_line <= line <= block.definition_range_end_line
        """
        if uri not in self._document_blocks:
            return None
        for name_key in self._document_blocks[uri]:
            block = self._blocks.get(name_key)
            if block is None:
                continue
            if (
                block.definition_uri == uri
                and block.definition_range_start_line <= line <= block.definition_range_end_line
            ):
                return block
        return None

    # ── Legacy helpers (kept for backward compatibility) ──────

    def clear(self) -> None:
        """Remove all symbols from all documents."""
        self._blocks.clear()
        self._document_blocks.clear()

    def lookup(self, name: str) -> Symbol | None:
        """Look up any symbol by name (blocks only for now)."""
        return self.lookup_block(name)

    def find_references(self, name: str) -> list[object]:
        """Find all references to a symbol. STUB."""
        return []

    # ── Private helpers ───────────────────────────────────────

    def _build_block_symbol(self, uri: str, block: BlockDeclaration) -> BlockSymbol:
        """Construct a :class:`BlockSymbol` from a :class:`BlockDeclaration`."""
        r = block.range
        block_kind_str = _BLOCK_KIND_NAMES.get(block.kind, str(block.kind))

        # Build variable symbols for each VAR section.
        all_vars: list[VariableSymbol] = []
        param_vars: list[VariableSymbol] = []

        for section in block.var_sections:
            section_kind_str = _VAR_SECTION_KIND_NAMES.get(section.kind, str(section.kind))
            is_param_section = section.kind in _PARAMETER_SECTION_KINDS

            for decl in section.declarations:
                dr = decl.range
                var_sym = VariableSymbol(
                    name=decl.name,
                    kind="variable",
                    definition_uri=uri,
                    definition_range_start_line=dr.start.line,
                    definition_range_start_char=dr.start.character,
                    definition_range_end_line=dr.end.line,
                    definition_range_end_char=dr.end.character,
                    type_name=decl.type_name,
                    section_kind=section_kind_str,
                    block_name=block.name,
                )
                all_vars.append(var_sym)
                if is_param_section:
                    param_vars.append(var_sym)

        return BlockSymbol(
            name=block.name,
            kind="block",
            definition_uri=uri,
            definition_range_start_line=r.start.line,
            definition_range_start_char=r.start.character,
            definition_range_end_line=r.end.line,
            definition_range_end_char=r.end.character,
            block_kind=block_kind_str,
            return_type=block.return_type,
            parameters=tuple(param_vars),
            all_variables=tuple(all_vars),
        )
