"""Scope management for variable resolution — STUB (Phase 2).

Will provide:
- Nested scope tracking (workspace → file → block → var_section)
- Variable shadowing rules
- Scope-aware completion candidates
"""

from __future__ import annotations


class Scope:
    """Represents a lexical scope in SCL code.

    SCL scope hierarchy:
        Global (workspace-level: DBs, FBs, FCs, UDTs)
        └── Block (FB/FC/OB body)
            └── VAR sections (INPUT, OUTPUT, TEMP, etc.)
                └── Nested blocks (IF, FOR, etc. — but SCL
                    doesn't have block-scoped variables)
    """

    def __init__(self, name: str, parent: Scope | None = None) -> None:
        self.name = name
        self.parent = parent
        self._children: list[Scope] = []

    def add_child(self, name: str) -> Scope:
        child = Scope(name, parent=self)
        self._children.append(child)
        return child
