"""Scope manager for symbol resolution at a cursor position (Phase 2).

Provides:
- Visible variable lookup based on cursor position
- Block-at-position delegation
- Name resolution with local scope priority over global scope
- Dotted member chain resolution (e.g. "MyDB.field")
"""

from __future__ import annotations

from s7_lsp.semantic.symbol_table import BlockSymbol, Symbol, SymbolTable, VariableSymbol


class ScopeManager:
    """Resolves visible symbols at a given cursor position.

    The ScopeManager is stateless — it does not own the SymbolTable and does
    not mutate it. All methods are synchronous and pure: given the same
    SymbolTable state they return the same result.

    Parameters
    ----------
    symbol_table:
        The workspace-wide symbol registry to query.
    """

    def __init__(self, symbol_table: SymbolTable) -> None:
        self._symbol_table = symbol_table

    # ── Public API ────────────────────────────────────────────

    def get_visible_variables(self, uri: str, position_line: int) -> list[VariableSymbol]:
        """Return all variables visible at the given cursor position.

        Looks up which block contains *position_line* in *uri*, then returns
        all :class:`~s7_lsp.semantic.symbol_table.VariableSymbol` objects
        declared in that block. Returns an empty list when the cursor is not
        inside any block.

        Parameters
        ----------
        uri:
            Document URI (e.g. ``file:///path/to/file.scl``).
        position_line:
            Zero-based line number of the cursor.
        """
        block = self._symbol_table.get_block_at(uri, position_line)
        if block is None:
            return []
        return self._symbol_table.get_variables_in_block(block.name)

    def get_block_at_position(self, uri: str, position_line: int) -> BlockSymbol | None:
        """Return the block that contains *position_line* in *uri*, or ``None``.

        Delegates directly to
        :meth:`~s7_lsp.semantic.symbol_table.SymbolTable.get_block_at`.

        Parameters
        ----------
        uri:
            Document URI.
        position_line:
            Zero-based line number of the cursor.
        """
        return self._symbol_table.get_block_at(uri, position_line)

    def resolve_name(self, name: str, uri: str, position_line: int) -> Symbol | None:
        """Resolve a single identifier to its :class:`Symbol`.

        Resolution order:

        1. Local variable in the block containing the cursor (highest priority).
        2. Global block name (case-insensitive).

        Returns ``None`` if the name cannot be resolved.

        Parameters
        ----------
        name:
            The identifier to resolve.
        uri:
            Document URI.
        position_line:
            Zero-based line number of the cursor.
        """
        # 1. Try local variable in the enclosing block.
        block = self._symbol_table.get_block_at(uri, position_line)
        if block is not None:
            var = self._symbol_table.lookup_variable(name, block.name)
            if var is not None:
                return var

        # 2. Try global block name lookup.
        block_sym = self._symbol_table.lookup_block(name)
        if block_sym is not None:
            return block_sym

        return None

    def resolve_member_chain(self, parts: list[str], uri: str, position_line: int) -> Symbol | None:
        """Resolve a dotted reference such as ``["MyDB", "field"]``.

        Resolution strategy:

        * The first part is resolved as a block name (global scope).  If
          found, the second part is looked up as a variable (field) inside
          that block and returned.
        * If the first part is a local variable whose ``type_name`` names a
          known block, the second part is looked up as a variable in that
          block instead.
        * Returns ``None`` if resolution fails at any step.

        Only two-part chains are currently supported. Longer chains are not
        resolved and return ``None``.

        Parameters
        ----------
        parts:
            Ordered list of identifier segments (e.g. ``["MyDB", "field"]``).
        uri:
            Document URI.
        position_line:
            Zero-based line number of the cursor.
        """
        if not parts or len(parts) < 2:
            return None

        first, second = parts[0], parts[1]

        # Strategy A: first part is a block name.
        owning_block = self._symbol_table.lookup_block(first)
        if owning_block is not None:
            return self._symbol_table.lookup_variable(second, owning_block.name)

        # Strategy B: first part is a local variable whose type is a block.
        block = self._symbol_table.get_block_at(uri, position_line)
        if block is not None:
            var = self._symbol_table.lookup_variable(first, block.name)
            if var is not None:
                # Use the variable's type_name as the block name.
                type_block = self._symbol_table.lookup_block(var.type_name)
                if type_block is not None:
                    return self._symbol_table.lookup_variable(second, type_block.name)

        return None
