"""Tests for s7_lsp.semantic.scope.ScopeManager.

Covers every acceptance criterion from task_004:
- get_visible_variables returns all variables from the block containing the cursor
- get_visible_variables returns empty list when cursor is outside all blocks
- resolve_name finds local variables before global block names (local scope priority)
- resolve_name finds global blocks when no local variable matches
- resolve_member_chain resolves 'DB.field' to the field's VariableSymbol
- resolve_member_chain returns None for unresolvable chains
"""

import pytest

from s7_lsp.ast_nodes import (
    BlockDeclaration,
    BlockKind,
    Position,
    Range,
    VarDeclaration,
    VarSection,
    VarSectionKind,
)
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import BlockSymbol, SymbolTable, VariableSymbol

# ─── Helpers ─────────────────────────────────────────────────


def _pos(line: int, char: int = 0) -> Position:
    return Position(line=line, character=char)


def _range(start_line: int, end_line: int) -> Range:
    return Range(start=_pos(start_line), end=_pos(end_line))


def _var_decl(
    name: str,
    type_name: str,
    kind: VarSectionKind = VarSectionKind.VAR,
    line: int = 5,
) -> VarDeclaration:
    return VarDeclaration(
        name=name,
        type_name=type_name,
        section_kind=kind,
        range=_range(line, line),
    )


def _var_section(kind: VarSectionKind, decls: list) -> VarSection:
    return VarSection(kind=kind, declarations=decls)


def _make_block(
    name: str,
    kind: BlockKind = BlockKind.FUNCTION_BLOCK,
    start_line: int = 0,
    end_line: int = 20,
    var_sections: list | None = None,
    return_type: str | None = None,
) -> BlockDeclaration:
    return BlockDeclaration(
        kind=kind,
        name=name,
        return_type=return_type,
        var_sections=var_sections or [],
        range=_range(start_line, end_line),
    )


URI = "file:///project/test.scl"
OTHER_URI = "file:///project/other.scl"


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture()
def table() -> SymbolTable:
    return SymbolTable()


@pytest.fixture()
def fb_with_vars() -> BlockDeclaration:
    """FUNCTION_BLOCK 'Controller' at lines 0-40 with several variables."""
    return _make_block(
        name="Controller",
        kind=BlockKind.FUNCTION_BLOCK,
        start_line=0,
        end_line=40,
        var_sections=[
            _var_section(
                VarSectionKind.VAR_INPUT,
                [_var_decl("setpoint", "REAL", VarSectionKind.VAR_INPUT, line=2)],
            ),
            _var_section(
                VarSectionKind.VAR_OUTPUT,
                [_var_decl("output", "REAL", VarSectionKind.VAR_OUTPUT, line=5)],
            ),
            _var_section(
                VarSectionKind.VAR_TEMP,
                [_var_decl("tmp", "INT", VarSectionKind.VAR_TEMP, line=8)],
            ),
        ],
    )


@pytest.fixture()
def db_block() -> BlockDeclaration:
    """DATA_BLOCK 'MotorDB' at lines 50-70 with two fields."""
    return _make_block(
        name="MotorDB",
        kind=BlockKind.DATA_BLOCK,
        start_line=50,
        end_line=70,
        var_sections=[
            _var_section(
                VarSectionKind.VAR,
                [
                    _var_decl("speed", "REAL", VarSectionKind.VAR, line=52),
                    _var_decl("running", "BOOL", VarSectionKind.VAR, line=53),
                ],
            )
        ],
    )


@pytest.fixture()
def scope(table: SymbolTable, fb_with_vars, db_block) -> ScopeManager:
    """ScopeManager wired to a table with Controller (0-40) and MotorDB (50-70)."""
    table.add_from_document(URI, [fb_with_vars, db_block])
    return ScopeManager(table)


# ─── get_visible_variables ────────────────────────────────────


class TestGetVisibleVariables:
    def test_returns_all_variables_inside_block(self, scope):
        """Cursor inside Controller returns all three declared variables."""
        vars_ = scope.get_visible_variables(URI, position_line=10)
        names = {v.name for v in vars_}
        assert names == {"setpoint", "output", "tmp"}

    def test_returns_empty_list_outside_all_blocks(self, scope):
        """Cursor outside every block boundary returns an empty list."""
        # Line 45 is between Controller (0-40) and MotorDB (50-70).
        vars_ = scope.get_visible_variables(URI, position_line=45)
        assert vars_ == []

    def test_returns_empty_list_for_unknown_uri(self, scope):
        """Unknown URI returns an empty list (no blocks registered there)."""
        vars_ = scope.get_visible_variables("file:///unknown.scl", position_line=5)
        assert vars_ == []

    def test_variables_are_variable_symbol_instances(self, scope):
        """Each returned item is a VariableSymbol."""
        vars_ = scope.get_visible_variables(URI, position_line=10)
        assert all(isinstance(v, VariableSymbol) for v in vars_)

    def test_returns_variables_at_block_boundary_lines(self, scope):
        """Cursor exactly on the first and last line of a block returns variables."""
        # start boundary
        assert scope.get_visible_variables(URI, position_line=0) != []
        # end boundary
        assert scope.get_visible_variables(URI, position_line=40) != []

    def test_returns_variables_from_correct_block(self, scope):
        """Cursor inside MotorDB returns MotorDB's fields, not Controller's."""
        vars_ = scope.get_visible_variables(URI, position_line=60)
        names = {v.name for v in vars_}
        assert names == {"speed", "running"}
        assert "setpoint" not in names


# ─── get_block_at_position ────────────────────────────────────


class TestGetBlockAtPosition:
    def test_returns_block_inside_range(self, scope):
        block = scope.get_block_at_position(URI, position_line=10)
        assert block is not None
        assert block.name == "Controller"

    def test_returns_none_outside_range(self, scope):
        block = scope.get_block_at_position(URI, position_line=45)
        assert block is None

    def test_returns_none_for_unknown_uri(self, scope):
        assert scope.get_block_at_position("file:///none.scl", 10) is None

    def test_returns_block_symbol(self, scope):
        block = scope.get_block_at_position(URI, position_line=10)
        assert isinstance(block, BlockSymbol)


# ─── resolve_name ─────────────────────────────────────────────


class TestResolveName:
    def test_finds_local_variable_inside_block(self, scope):
        """resolve_name returns the VariableSymbol for a local variable."""
        sym = scope.resolve_name("setpoint", URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, VariableSymbol)
        assert sym.name == "setpoint"

    def test_local_variable_has_priority_over_block_with_same_name(self, table):
        """When a local variable and a global block share a name, the variable wins."""
        # Create a block named 'Speed' that also has a local variable 'Speed'.
        speed_block = _make_block(
            name="SpeedBlock",
            start_line=0,
            end_line=30,
            var_sections=[
                _var_section(
                    VarSectionKind.VAR,
                    # Variable named 'MotorDB' shadows the global MotorDB block.
                    [_var_decl("MotorDB", "DINT", VarSectionKind.VAR, line=5)],
                )
            ],
        )
        motor_db = _make_block(
            name="MotorDB",
            kind=BlockKind.DATA_BLOCK,
            start_line=50,
            end_line=70,
        )
        table.add_from_document(URI, [speed_block, motor_db])
        sm = ScopeManager(table)

        sym = sm.resolve_name("MotorDB", URI, position_line=10)
        # Should return the *variable* not the block.
        assert sym is not None
        assert isinstance(sym, VariableSymbol)
        assert sym.block_name == "SpeedBlock"

    def test_finds_global_block_when_no_local_match(self, scope):
        """resolve_name falls back to block lookup when no local variable matches."""
        # 'MotorDB' is not a variable in Controller, but it is a global block.
        sym = scope.resolve_name("MotorDB", URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, BlockSymbol)
        assert sym.name == "MotorDB"

    def test_finds_global_block_when_outside_any_block(self, scope):
        """resolve_name finds a block even when cursor is outside all blocks."""
        sym = scope.resolve_name("MotorDB", URI, position_line=45)
        assert sym is not None
        assert isinstance(sym, BlockSymbol)

    def test_returns_none_for_completely_unknown_name(self, scope):
        """resolve_name returns None when no variable or block matches."""
        sym = scope.resolve_name("NonExistent", URI, position_line=10)
        assert sym is None

    def test_case_insensitive_variable_lookup(self, scope):
        """resolve_name finds a variable regardless of case."""
        sym = scope.resolve_name("SETPOINT", URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, VariableSymbol)

    def test_case_insensitive_block_lookup(self, scope):
        """resolve_name finds a block regardless of case."""
        sym = scope.resolve_name("motordb", URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, BlockSymbol)


# ─── resolve_member_chain ─────────────────────────────────────


class TestResolveMemberChain:
    def test_resolves_db_dot_field(self, scope):
        """resolve_member_chain('MotorDB', 'speed') returns the speed VariableSymbol."""
        sym = scope.resolve_member_chain(["MotorDB", "speed"], URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, VariableSymbol)
        assert sym.name == "speed"

    def test_resolves_db_dot_second_field(self, scope):
        """resolve_member_chain resolves the second field too."""
        sym = scope.resolve_member_chain(["MotorDB", "running"], URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, VariableSymbol)
        assert sym.name == "running"

    def test_returns_none_for_unknown_first_part(self, scope):
        """If the first part does not resolve to a block, return None."""
        sym = scope.resolve_member_chain(["UnknownBlock", "field"], URI, position_line=10)
        assert sym is None

    def test_returns_none_for_unknown_field(self, scope):
        """If the block is found but the field is not, return None."""
        sym = scope.resolve_member_chain(["MotorDB", "nonExistentField"], URI, position_line=10)
        assert sym is None

    def test_returns_none_for_empty_parts(self, scope):
        """Empty parts list returns None."""
        assert scope.resolve_member_chain([], URI, position_line=10) is None

    def test_returns_none_for_single_part(self, scope):
        """A single-element chain (no dot) returns None."""
        assert scope.resolve_member_chain(["MotorDB"], URI, position_line=10) is None

    def test_resolves_via_variable_type(self, table):
        """If the first part is a local variable, its type_name is used as block name."""
        # 'db_ref' variable of type 'MotorDB' inside CallerFB.
        caller = _make_block(
            name="CallerFB",
            start_line=0,
            end_line=30,
            var_sections=[
                _var_section(
                    VarSectionKind.VAR,
                    [_var_decl("db_ref", "MotorDB", VarSectionKind.VAR, line=5)],
                )
            ],
        )
        motor_db = _make_block(
            name="MotorDB",
            kind=BlockKind.DATA_BLOCK,
            start_line=50,
            end_line=70,
            var_sections=[
                _var_section(
                    VarSectionKind.VAR,
                    [_var_decl("speed", "REAL", VarSectionKind.VAR, line=52)],
                )
            ],
        )
        table.add_from_document(URI, [caller, motor_db])
        sm = ScopeManager(table)

        sym = sm.resolve_member_chain(["db_ref", "speed"], URI, position_line=10)
        assert sym is not None
        assert isinstance(sym, VariableSymbol)
        assert sym.name == "speed"

    def test_case_insensitive_chain_resolution(self, scope):
        """resolve_member_chain is case-insensitive for both parts."""
        sym = scope.resolve_member_chain(["motordb", "SPEED"], URI, position_line=10)
        assert sym is not None
        assert sym.name == "speed"
