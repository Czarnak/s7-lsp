"""Symbol table for cross-reference resolution — STUB (Phase 2).

Will provide:
- Registration of all declared symbols (blocks, variables, types)
- Lookup by name with scope awareness
- Cross-file symbol resolution (e.g., "MyDB".field)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from s7_lsp.ast_nodes import BlockDeclaration, Position, Range


@dataclass
class Symbol:
    """A named entity in the source code."""

    name: str
    kind: str  # "block", "variable", "type", "parameter"
    type_name: str | None = None
    definition_uri: str = ""
    definition_range: Range = field(default_factory=lambda: Range(Position(0, 0), Position(0, 0)))


class SymbolTable:
    """Tracks all symbols across a workspace.

    Phase 2 will implement:
    - add_block(), add_variable(), add_type()
    - lookup(name, scope) → Symbol | None
    - find_references(name) → list[Location]
    - resolve_member_access("DB".field) → Symbol | None
    """

    def __init__(self) -> None:
        self._symbols: dict[str, list[Symbol]] = {}

    def clear(self) -> None:
        self._symbols.clear()

    def add_from_document(self, uri: str, blocks: list[BlockDeclaration]) -> None:
        """Register all symbols from a parsed document. STUB."""

    def lookup(self, name: str) -> Symbol | None:
        """Look up a symbol by name. STUB."""
        return None

    def find_references(self, name: str) -> list[tuple[str, Range]]:
        """Find all references to a symbol. STUB."""
        return []
