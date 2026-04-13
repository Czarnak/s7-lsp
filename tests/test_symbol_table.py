"""Tests for s7_lsp.semantic.symbol_table.

Covers every acceptance criterion from task_003:
- add_from_document registers BlockSymbol for each block
- add_from_document registers VariableSymbol for each variable in each VAR section
- BlockSymbol.parameters contains only VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT variables
- remove_document(uri) removes all blocks and variables registered from that URI
- Calling add_from_document twice for the same URI does NOT duplicate symbols
- lookup_block is case-insensitive
- lookup_variable returns None for unknown variable/block names
- get_block_at returns the correct block when line falls within range, None otherwise
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
from s7_lsp.semantic.symbol_table import BlockSymbol, SymbolTable, VariableSymbol

# ─── Helpers ─────────────────────────────────────────────────


def _pos(line: int, char: int = 0) -> Position:
    return Position(line=line, character=char)


def _range(start_line: int, end_line: int) -> Range:
    return Range(start=_pos(start_line), end=_pos(end_line))


def _var_decl(name: str, type_name: str, kind: VarSectionKind, line: int = 0) -> VarDeclaration:
    return VarDeclaration(
        name=name,
        type_name=type_name,
        section_kind=kind,
        range=_range(line, line),
    )


def _var_section(kind: VarSectionKind, decls: list) -> VarSection:
    return VarSection(kind=kind, declarations=decls)


def _make_fb(
    name: str = "MyFB",
    start_line: int = 0,
    end_line: int = 20,
    var_sections: list | None = None,
) -> BlockDeclaration:
    return BlockDeclaration(
        kind=BlockKind.FUNCTION_BLOCK,
        name=name,
        return_type=None,
        var_sections=var_sections or [],
        range=_range(start_line, end_line),
    )


def _make_fc(
    name: str = "MyFC",
    return_type: str = "INT",
    start_line: int = 30,
    end_line: int = 50,
    var_sections: list | None = None,
) -> BlockDeclaration:
    return BlockDeclaration(
        kind=BlockKind.FUNCTION,
        name=name,
        return_type=return_type,
        var_sections=var_sections or [],
        range=_range(start_line, end_line),
    )


URI_A = "file:///project/block_a.scl"
URI_B = "file:///project/block_b.scl"


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture()
def table() -> SymbolTable:
    return SymbolTable()


@pytest.fixture()
def fb_with_vars() -> BlockDeclaration:
    """A FUNCTION_BLOCK with one variable in each interesting section."""
    return _make_fb(
        name="Controller",
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
                VarSectionKind.VAR_IN_OUT,
                [_var_decl("status", "BOOL", VarSectionKind.VAR_IN_OUT, line=8)],
            ),
            _var_section(
                VarSectionKind.VAR, [_var_decl("integral", "REAL", VarSectionKind.VAR, line=11)]
            ),
            _var_section(
                VarSectionKind.VAR_TEMP,
                [_var_decl("tmp", "REAL", VarSectionKind.VAR_TEMP, line=14)],
            ),
        ],
    )


# ─── Tests ───────────────────────────────────────────────────


class TestAddFromDocument:
    def test_registers_block_for_each_block_in_document(self, table):
        """add_from_document registers a BlockSymbol for each block."""
        blocks = [_make_fb("FB1"), _make_fc("FC1")]
        table.add_from_document(URI_A, blocks)

        assert table.lookup_block("FB1") is not None
        assert table.lookup_block("FC1") is not None
        assert len(table.get_all_blocks()) == 2

    def test_registers_block_symbol_fields(self, table):
        """BlockSymbol stores correct name, kind, uri, and range."""
        fb = _make_fb("MyFB", start_line=5, end_line=25)
        table.add_from_document(URI_A, [fb])

        sym = table.lookup_block("MyFB")
        assert sym is not None
        assert isinstance(sym, BlockSymbol)
        assert sym.name == "MyFB"
        assert sym.kind == "block"
        assert sym.block_kind == "FUNCTION_BLOCK"
        assert sym.definition_uri == URI_A
        assert sym.definition_range_start_line == 5
        assert sym.definition_range_end_line == 25

    def test_function_block_kind_is_db(self, table):
        """DATA_BLOCK maps to block_kind 'DB'."""
        from s7_lsp.ast_nodes import BlockKind

        db = BlockDeclaration(
            kind=BlockKind.DATA_BLOCK,
            name="MyDB",
            range=_range(0, 10),
        )
        table.add_from_document(URI_A, [db])
        sym = table.lookup_block("MyDB")
        assert sym is not None
        assert sym.block_kind == "DB"

    def test_function_return_type_preserved(self, table):
        """FUNCTION's return_type is stored on BlockSymbol."""
        fc = _make_fc("Calc", return_type="DINT")
        table.add_from_document(URI_A, [fc])

        sym = table.lookup_block("Calc")
        assert sym is not None
        assert sym.return_type == "DINT"

    def test_registers_variables_for_each_var_section(self, table, fb_with_vars):
        """Every variable in every VAR section is registered."""
        table.add_from_document(URI_A, [fb_with_vars])

        vars_in_block = table.get_variables_in_block("Controller")
        var_names = {v.name for v in vars_in_block}
        assert var_names == {"setpoint", "output", "status", "integral", "tmp"}

    def test_variable_symbol_fields(self, table, fb_with_vars):
        """VariableSymbol carries correct type_name, section_kind, and block_name."""
        table.add_from_document(URI_A, [fb_with_vars])

        var = table.lookup_variable("setpoint", "Controller")
        assert var is not None
        assert isinstance(var, VariableSymbol)
        assert var.type_name == "REAL"
        assert var.section_kind == "VAR_INPUT"
        assert var.block_name == "Controller"
        assert var.definition_uri == URI_A

    def test_parameters_contains_only_input_output_in_out(self, table, fb_with_vars):
        """BlockSymbol.parameters includes only VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT."""
        table.add_from_document(URI_A, [fb_with_vars])

        sym = table.lookup_block("Controller")
        assert sym is not None
        param_names = {v.name for v in sym.parameters}
        # setpoint (VAR_INPUT), output (VAR_OUTPUT), status (VAR_IN_OUT)
        assert param_names == {"setpoint", "output", "status"}
        # integral (VAR) and tmp (VAR_TEMP) must NOT be in parameters
        assert "integral" not in param_names
        assert "tmp" not in param_names

    def test_all_variables_contains_every_section(self, table, fb_with_vars):
        """BlockSymbol.all_variables includes variables from all VAR sections."""
        table.add_from_document(URI_A, [fb_with_vars])

        sym = table.lookup_block("Controller")
        assert sym is not None
        all_names = {v.name for v in sym.all_variables}
        assert all_names == {"setpoint", "output", "status", "integral", "tmp"}

    def test_empty_blocks_list_registers_nothing(self, table):
        """add_from_document with empty list leaves table empty."""
        table.add_from_document(URI_A, [])
        assert table.get_all_blocks() == []


class TestAddFromDocumentIdempotence:
    def test_second_call_does_not_duplicate_symbols(self, table):
        """Calling add_from_document twice for the same URI keeps exactly one copy."""
        fb = _make_fb("FB1")
        table.add_from_document(URI_A, [fb])
        table.add_from_document(URI_A, [fb])

        # Should have exactly 1 block, not 2.
        assert len(table.get_all_blocks()) == 1

    def test_second_call_replaces_old_symbol(self, table):
        """Second add_from_document for the same URI replaces the old registration."""
        old_fb = _make_fb("FB1", start_line=0, end_line=10)
        new_fb = _make_fb("FB1", start_line=100, end_line=200)

        table.add_from_document(URI_A, [old_fb])
        table.add_from_document(URI_A, [new_fb])

        sym = table.lookup_block("FB1")
        assert sym is not None
        # Should reflect new_fb's range
        assert sym.definition_range_start_line == 100
        assert sym.definition_range_end_line == 200

    def test_second_call_removes_blocks_no_longer_present(self, table):
        """Blocks removed from a document are removed from the table on re-register."""
        table.add_from_document(URI_A, [_make_fb("FB1"), _make_fb("FB2")])
        # Re-register with only FB1
        table.add_from_document(URI_A, [_make_fb("FB1")])

        assert table.lookup_block("FB1") is not None
        assert table.lookup_block("FB2") is None
        assert len(table.get_all_blocks()) == 1


class TestRemoveDocument:
    def test_removes_all_blocks_from_uri(self, table):
        """remove_document removes all blocks registered from that URI."""
        table.add_from_document(URI_A, [_make_fb("FB1"), _make_fc("FC1")])
        table.remove_document(URI_A)

        assert table.lookup_block("FB1") is None
        assert table.lookup_block("FC1") is None
        assert table.get_all_blocks() == []

    def test_remove_only_affects_target_uri(self, table):
        """remove_document leaves symbols from other URIs intact."""
        table.add_from_document(URI_A, [_make_fb("FB_A")])
        table.add_from_document(URI_B, [_make_fb("FB_B")])

        table.remove_document(URI_A)

        assert table.lookup_block("FB_A") is None
        assert table.lookup_block("FB_B") is not None

    def test_remove_nonexistent_uri_is_harmless(self, table):
        """remove_document on an unknown URI raises no error."""
        table.remove_document("file:///does/not/exist.scl")  # should not raise


class TestLookup:
    def test_lookup_block_case_insensitive(self, table):
        """lookup_block matches regardless of name casing."""
        table.add_from_document(URI_A, [_make_fb("MyFunctionBlock")])

        assert table.lookup_block("myfunctionblock") is not None
        assert table.lookup_block("MYFUNCTIONBLOCK") is not None
        assert table.lookup_block("MyFunctionBlock") is not None
        assert table.lookup_block("myFUNCTIONBLOCK") is not None

    def test_lookup_block_returns_none_for_unknown(self, table):
        """lookup_block returns None when no block has the given name."""
        table.add_from_document(URI_A, [_make_fb("FB1")])
        assert table.lookup_block("FB2") is None

    def test_lookup_variable_case_insensitive_name(self, table, fb_with_vars):
        """lookup_variable matches variable name case-insensitively."""
        table.add_from_document(URI_A, [fb_with_vars])

        assert table.lookup_variable("SETPOINT", "Controller") is not None
        assert table.lookup_variable("setpoint", "Controller") is not None
        assert table.lookup_variable("Setpoint", "controller") is not None

    def test_lookup_variable_returns_none_unknown_variable(self, table, fb_with_vars):
        """lookup_variable returns None for an unknown variable name."""
        table.add_from_document(URI_A, [fb_with_vars])
        assert table.lookup_variable("nonexistent", "Controller") is None

    def test_lookup_variable_returns_none_unknown_block(self, table, fb_with_vars):
        """lookup_variable returns None when the block doesn't exist."""
        table.add_from_document(URI_A, [fb_with_vars])
        assert table.lookup_variable("setpoint", "UnknownBlock") is None


class TestGetBlockAt:
    def test_returns_block_when_line_within_range(self, table):
        """get_block_at returns the block that contains the given line."""
        fb = _make_fb("FB1", start_line=10, end_line=30)
        table.add_from_document(URI_A, [fb])

        assert table.get_block_at(URI_A, 10) is not None
        assert table.get_block_at(URI_A, 20) is not None
        assert table.get_block_at(URI_A, 30) is not None

    def test_returns_none_when_line_before_block(self, table):
        """get_block_at returns None when line is before the block's start."""
        fb = _make_fb("FB1", start_line=10, end_line=30)
        table.add_from_document(URI_A, [fb])

        assert table.get_block_at(URI_A, 9) is None

    def test_returns_none_when_line_after_block(self, table):
        """get_block_at returns None when line is after the block's end."""
        fb = _make_fb("FB1", start_line=10, end_line=30)
        table.add_from_document(URI_A, [fb])

        assert table.get_block_at(URI_A, 31) is None

    def test_returns_correct_block_among_multiple(self, table):
        """get_block_at selects the correct block when multiple blocks are registered."""
        fb1 = _make_fb("FB1", start_line=0, end_line=20)
        fb2 = _make_fb("FB2", start_line=25, end_line=50)
        table.add_from_document(URI_A, [fb1, fb2])

        result1 = table.get_block_at(URI_A, 10)
        assert result1 is not None
        assert result1.name == "FB1"

        result2 = table.get_block_at(URI_A, 35)
        assert result2 is not None
        assert result2.name == "FB2"

    def test_returns_none_for_unknown_uri(self, table):
        """get_block_at returns None when the URI has no registered blocks."""
        assert table.get_block_at("file:///unknown.scl", 5) is None

    def test_returns_none_for_line_in_gap_between_blocks(self, table):
        """get_block_at returns None when line falls between two blocks."""
        fb1 = _make_fb("FB1", start_line=0, end_line=10)
        fb2 = _make_fb("FB2", start_line=15, end_line=25)
        table.add_from_document(URI_A, [fb1, fb2])

        assert table.get_block_at(URI_A, 12) is None

    def test_does_not_cross_uri_boundaries(self, table):
        """get_block_at does not match blocks from a different URI."""
        fb = _make_fb("FB1", start_line=0, end_line=20)
        table.add_from_document(URI_A, [fb])

        assert table.get_block_at(URI_B, 5) is None


class TestGetAllBlocks:
    def test_returns_all_registered_blocks(self, table):
        """get_all_blocks returns every registered BlockSymbol."""
        table.add_from_document(URI_A, [_make_fb("FB1"), _make_fc("FC1")])
        table.add_from_document(URI_B, [_make_fb("FB2")])

        names = {b.name for b in table.get_all_blocks()}
        assert names == {"FB1", "FC1", "FB2"}

    def test_returns_empty_list_when_no_blocks(self, table):
        """get_all_blocks returns an empty list on a fresh SymbolTable."""
        assert table.get_all_blocks() == []


class TestGetVariablesInBlock:
    def test_returns_empty_list_for_unknown_block(self, table):
        """get_variables_in_block returns [] for an unregistered block."""
        assert table.get_variables_in_block("Unknown") == []

    def test_returns_all_variables_for_block(self, table, fb_with_vars):
        """get_variables_in_block returns all variables regardless of section."""
        table.add_from_document(URI_A, [fb_with_vars])
        vars_list = table.get_variables_in_block("Controller")
        assert len(vars_list) == 5
        names = {v.name for v in vars_list}
        assert names == {"setpoint", "output", "status", "integral", "tmp"}
