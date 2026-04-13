"""Tests for s7_lsp.features.definition.get_definition().

Covers every acceptance criterion from task_007:
- #localVar jumps to its VAR declaration in the current block
- Quoted block name jumps to the FUNCTION_BLOCK/FUNCTION/DB/TYPE declaration
- Plain identifier resolves first as local variable, then as block name
- Type name in declaration position (after ':') resolves to TYPE declaration
- Member access 'DB.field' resolves to the field declaration
- Unknown symbols return None
- Cross-file definition works (symbol defined in a different URI)
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import (
    BlockDeclaration,
    BlockKind,
    ParsedDocument,
    Position,
    Range,
    VarDeclaration,
    VarSection,
    VarSectionKind,
)
from s7_lsp.features.definition import get_definition
from s7_lsp.semantic.symbol_table import SymbolTable

_TEST_URI = "file:///test/sample.scl"
_OTHER_URI = "file:///test/other.scl"


# ─── Helpers ─────────────────────────────────────────────────


def _pos(line: int, char: int = 0) -> Position:
    return Position(line=line, character=char)


def _range(start_line: int, start_char: int, end_line: int, end_char: int) -> Range:
    return Range(start=_pos(start_line, start_char), end=_pos(end_line, end_char))


def _make_var_decl(
    name: str,
    type_name: str,
    kind: VarSectionKind = VarSectionKind.VAR,
    line: int = 5,
) -> VarDeclaration:
    return VarDeclaration(
        name=name,
        type_name=type_name,
        section_kind=kind,
        range=_range(line, 4, line, 4 + len(name)),
    )


def _make_var_section(kind: VarSectionKind, decls: list) -> VarSection:
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
        range=_range(start_line, 0, end_line, 0),
    )


def _make_doc(uri: str = _TEST_URI) -> ParsedDocument:
    return ParsedDocument(uri=uri, blocks=[])


def _lsp_pos(line: int, character: int) -> lsp.Position:
    return lsp.Position(line=line, character=character)


# ─── Tests using conftest fixtures ───────────────────────────


class TestHashLocalVar:
    """#localVar jumps to its VAR declaration in the current block."""

    def test_hash_prefix_enable_jumps_to_var_input(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """#Enable at line 13 resolves to the VAR_INPUT Enable declaration (line 3)."""
        # Line 13: "    IF #Enable THEN"
        # '#' is at col 7, 'Enable' starts at col 8
        doc = parsed_document
        position = _lsp_pos(line=13, character=8)  # on 'Enable' after '#'
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, "Expected definition for #Enable"
        assert isinstance(result, lsp.Location)
        assert result.uri == _TEST_URI
        # Enable is declared at line 3
        assert result.range.start.line == 3

    def test_hash_prefix_running_jumps_to_var_output(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """#Running at line 14 resolves to the VAR_OUTPUT Running declaration (line 7)."""
        # Line 14: "        #Running := TRUE;"
        # '#' is at col 8, 'Running' starts at col 9
        doc = parsed_document
        position = _lsp_pos(line=14, character=9)  # on 'R' of '#Running'
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, "Expected definition for #Running"
        assert isinstance(result, lsp.Location)
        assert result.uri == _TEST_URI
        # Running is declared at line 7
        assert result.range.start.line == 7

    def test_hash_prefix_input_value_jumps_to_declaration(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """#InputValue at line 24 resolves to VAR_INPUT InputValue (line 21)."""
        # Line 24: '    "FC_Calculate" := INT_TO_DINT(#InputValue);'
        # '#' is at col 34, 'InputValue' starts at col 35
        doc = parsed_document
        position = _lsp_pos(line=24, character=35)
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, "Expected definition for #InputValue"
        assert result.range.start.line == 21

    def test_hash_prefix_unknown_returns_none(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """#NonExistent returns None."""
        source = 'FUNCTION_BLOCK "TestFB"\nVAR_TEMP\n    x : INT;\nEND_VAR\n    #NonExistent := 1;\nEND_FUNCTION_BLOCK\n'
        st = SymbolTable()
        doc = ParsedDocument(uri=_TEST_URI, blocks=[])
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st.add_from_document(_TEST_URI, doc.blocks)
        position = _lsp_pos(line=4, character=5)  # on 'N' of '#NonExistent'
        result = get_definition(doc, position, source, st)
        assert result is None


class TestQuotedBlockName:
    """Quoted block name jumps to the FUNCTION_BLOCK/FUNCTION/DB/TYPE declaration."""

    def test_quoted_fc_calculate_in_body(self, parsed_document, symbol_table, sample_scl_source):
        """\"FC_Calculate\" at line 24 resolves to FC_Calculate's FUNCTION declaration (line 19)."""
        # Line 24: '    "FC_Calculate" := INT_TO_DINT(#InputValue);'
        # '"' starts at col 4
        doc = parsed_document
        position = _lsp_pos(line=24, character=4)  # on opening '"'
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, 'Expected definition for "FC_Calculate"'
        assert isinstance(result, lsp.Location)
        assert result.uri == _TEST_URI
        # FC_Calculate FUNCTION starts at line 19
        assert result.range.start.line == 19

    def test_quoted_motor_control_in_header(self, parsed_document, symbol_table, sample_scl_source):
        """\"MotorControl\" at line 0 resolves to the FUNCTION_BLOCK declaration."""
        doc = parsed_document
        position = _lsp_pos(line=0, character=16)  # inside "MotorControl"
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, 'Expected definition for "MotorControl"'
        assert result.range.start.line == 0

    def test_quoted_db_motor_resolves(self, parsed_document, symbol_table, sample_scl_source):
        """\"DB_Motor\" resolves to the DATA_BLOCK declaration (line 35)."""
        doc = parsed_document
        # Construct a synthetic source to test from outside — use a position inside a line
        # that contains "DB_Motor" as a quoted identifier.
        # We'll use the header line 35: 'DATA_BLOCK "DB_Motor"'
        position = _lsp_pos(line=35, character=12)  # inside "DB_Motor"
        result = get_definition(doc, position, sample_scl_source, symbol_table)
        assert result is not None, 'Expected definition for "DB_Motor"'
        assert result.range.start.line == 35

    def test_quoted_unknown_block_returns_none(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """\"NoSuchBlock\" returns None."""
        # We need a source line containing "NoSuchBlock"
        source = sample_scl_source + '\n// test "NoSuchBlock"\n'
        lines = source.split("\n")
        target_line = len(lines) - 2  # the comment line
        doc = parsed_document
        position = _lsp_pos(line=target_line, character=9)  # inside "NoSuchBlock"
        result = get_definition(doc, position, source, symbol_table)
        assert result is None


class TestPlainIdentifier:
    """Plain identifier resolves first as local variable, then as block name."""

    def test_plain_local_variable_priority_over_block(self):
        """A plain identifier matching a local var takes priority over a block of the same name."""
        # Block 'CallerFB' at 0-20, has var 'MotorDB' of type DINT
        # Block 'MotorDB' at 30-50 as DATA_BLOCK
        source = (
            "FUNCTION_BLOCK CallerFB\n"  # line 0
            "VAR\n"  # line 1
            "    MotorDB : DINT;\n"  # line 2
            "END_VAR\n"  # line 3
            "    MotorDB := 1;\n"  # line 4
            "END_FUNCTION_BLOCK\n"  # line 5
            "DATA_BLOCK MotorDB\n"  # line 6
            "VAR\n"  # line 7
            "    speed : INT;\n"  # line 8
            "END_VAR\n"  # line 9
            "END_DATA_BLOCK\n"  # line 10
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        # Cursor on 'MotorDB' at line 4, col 4
        position = _lsp_pos(line=4, character=4)
        result = get_definition(doc, position, source, st)
        assert result is not None
        # Should resolve to the variable declaration at line 2 (local var priority)
        assert result.range.start.line == 2

    def test_plain_identifier_falls_back_to_block(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """A plain identifier not matching any local var resolves to a block if one exists."""
        # Create a custom source and doc with a usage of MotorControl outside any block
        source = "MotorControl();\n"
        doc = ParsedDocument(uri=_TEST_URI)
        position = _lsp_pos(line=0, character=0)
        result = get_definition(doc, position, source, symbol_table)
        assert result is not None
        # MotorControl is a FUNCTION_BLOCK at line 0 of _TEST_URI
        assert result.range.start.line == 0

    def test_plain_unknown_returns_none(self, parsed_document, symbol_table, sample_scl_source):
        """Unknown plain identifier returns None."""
        source = "XYZTotallyUnknown := 1;\n"
        doc = ParsedDocument(uri=_TEST_URI)
        position = _lsp_pos(line=0, character=0)
        result = get_definition(doc, position, source, symbol_table)
        assert result is None


class TestTypePosition:
    """Type name in declaration position (after ':') resolves to TYPE declaration."""

    def test_type_name_after_colon_resolves_to_type_block(self):
        """'MyUDT' after ':' in a VAR declaration resolves to the TYPE block."""
        source = (
            "TYPE MyUDT\n"  # line 0
            "STRUCT\n"  # line 1
            "    Val : INT;\n"  # line 2
            "END_STRUCT;\n"  # line 3
            "END_TYPE\n"  # line 4
            "\n"  # line 5
            "FUNCTION_BLOCK UseFB\n"  # line 6
            "VAR\n"  # line 7
            "    myVar : MyUDT;\n"  # line 8
            "END_VAR\n"  # line 9
            "END_FUNCTION_BLOCK\n"  # line 10
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        # Cursor on 'MyUDT' at line 8, after ': '
        # "    myVar : MyUDT;"
        #  0123456789012345678
        # 'M' is at col 12
        position = _lsp_pos(line=8, character=12)
        result = get_definition(doc, position, source, st)
        assert result is not None, "Expected definition for MyUDT type in type position"
        assert result.range.start.line == 0

    def test_type_name_motor_data_resolves(self, parsed_document, symbol_table, sample_scl_source):
        """MotorData in a type position (if present) resolves to the TYPE declaration."""
        # Build a source line referencing MotorData as a type
        source = (
            sample_scl_source
            + "\nFUNCTION_BLOCK TestTypeRef\nVAR\n    data : MotorData;\nEND_VAR\nEND_FUNCTION_BLOCK\n"
        )
        lines = sample_scl_source.split("\n")
        base_lines = len(lines)
        # "    data : MotorData;" is at base_lines + 2 (0-based)
        target_line = base_lines + 2
        # 'M' of 'MotorData' is at col 11
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        position = _lsp_pos(line=target_line, character=11)
        result = get_definition(doc, position, source, st)
        assert result is not None, "Expected definition for MotorData type"
        # MotorData TYPE starts at line 28 in sample_scl_source
        assert result.range.start.line == 28


class TestMemberAccess:
    """Member access 'DB.field' resolves to the field declaration."""

    def test_db_dot_field_resolves_to_field_declaration(self):
        """\"DB_Motor\".Speed resolves to the Speed field in DB_Motor."""
        source = (
            "DATA_BLOCK DB_Motor\n"  # line 0
            "VAR\n"  # line 1
            "    Speed : INT;\n"  # line 2
            "    Active : BOOL;\n"  # line 3
            "END_VAR\n"  # line 4
            "END_DATA_BLOCK\n"  # line 5
            "\n"  # line 6
            "FUNCTION_BLOCK TestFB\n"  # line 7
            "VAR_TEMP\n"  # line 8
            "    tmp : INT;\n"  # line 9
            "END_VAR\n"  # line 10
            "    DB_Motor.Speed := 1;\n"  # line 11
            "END_FUNCTION_BLOCK\n"  # line 12
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        # "    DB_Motor.Speed := 1;"
        #  0         1         2
        #  0123456789012345678901234
        # 'Speed' starts at col 13
        position = _lsp_pos(line=11, character=13)
        result = get_definition(doc, position, source, st)
        assert result is not None, "Expected definition for DB_Motor.Speed"
        assert isinstance(result, lsp.Location)
        # Speed field is at line 2
        assert result.range.start.line == 2

    def test_member_chain_via_local_var_type(self):
        """A local variable typed as a block allows member resolution."""
        source = (
            "DATA_BLOCK MyDB\n"  # line 0
            "VAR\n"  # line 1
            "    field1 : INT;\n"  # line 2
            "END_VAR\n"  # line 3
            "END_DATA_BLOCK\n"  # line 4
            "\n"  # line 5
            "FUNCTION_BLOCK UseFB\n"  # line 6
            "VAR\n"  # line 7
            "    ref : MyDB;\n"  # line 8 — local var of type MyDB
            "END_VAR\n"  # line 9
            "    ref.field1 := 0;\n"  # line 10
            "END_FUNCTION_BLOCK\n"  # line 11
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        # "    ref.field1 := 0;"
        #  0123456789012345
        # 'f' of 'field1' is at col 8
        position = _lsp_pos(line=10, character=8)
        result = get_definition(doc, position, source, st)
        assert result is not None, "Expected definition for ref.field1"
        assert result.range.start.line == 2

    def test_unknown_member_returns_none(self):
        """A member access for an unknown field returns None."""
        source = (
            "DATA_BLOCK MyDB\n"  # line 0
            "VAR\n"  # line 1
            "    field1 : INT;\n"  # line 2
            "END_VAR\n"  # line 3
            "END_DATA_BLOCK\n"  # line 4
            "\n"  # line 5
            "FUNCTION_BLOCK TestFB\n"  # line 6
            "VAR_TEMP\n"  # line 7
            "    tmp : INT;\n"  # line 8
            "END_VAR\n"  # line 9
            "    MyDB.noSuchField := 0;\n"  # line 10
            "END_FUNCTION_BLOCK\n"  # line 11
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)
        # "    MyDB.noSuchField := 0;"
        #  01234567890123456789
        # 'n' of 'noSuchField' is at col 9
        position = _lsp_pos(line=10, character=9)
        result = get_definition(doc, position, source, st)
        assert result is None


class TestUnknownSymbols:
    """Unknown symbols return None."""

    def test_no_symbol_table_returns_none(self, parsed_document, sample_scl_source):
        """When symbol_table is None, get_definition returns None unconditionally."""
        position = _lsp_pos(line=13, character=8)
        result = get_definition(parsed_document, position, sample_scl_source, None)
        assert result is None

    def test_whitespace_position_returns_none(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """Cursor on whitespace returns None (no word at position)."""
        # Line 12 is blank
        position = _lsp_pos(line=12, character=0)
        result = get_definition(parsed_document, position, sample_scl_source, symbol_table)
        assert result is None

    def test_unknown_hash_var_returns_none(self, parsed_document, symbol_table, sample_scl_source):
        """#ZZZGarbage returns None (not declared in any block)."""
        source = sample_scl_source + "\n    #ZZZGarbage := 1;\n"
        position = _lsp_pos(line=sample_scl_source.count("\n") + 1, character=5)
        result = get_definition(parsed_document, position, source, symbol_table)
        assert result is None


class TestCrossFileDefinition:
    """Cross-file definition: symbol defined in a different URI."""

    def test_cross_file_block_definition(self):
        """A block declared in other.scl is resolvable from test.scl via the symbol table."""
        # Set up other.scl block
        other_source = "FUNCTION_BLOCK RemoteFB\nVAR\n    val : INT;\nEND_VAR\nEND_FUNCTION_BLOCK\n"
        # Set up test.scl that calls RemoteFB
        test_source = "FUNCTION_BLOCK LocalFB\nVAR_TEMP\n    tmp : INT;\nEND_VAR\n    RemoteFB();\nEND_FUNCTION_BLOCK\n"

        from s7_lsp.parsers.scl_parser import parse_scl

        other_doc = parse_scl(other_source, _OTHER_URI)
        test_doc = parse_scl(test_source, _TEST_URI)

        st = SymbolTable()
        st.add_from_document(_OTHER_URI, other_doc.blocks)
        st.add_from_document(_TEST_URI, test_doc.blocks)

        # Cursor on 'RemoteFB' at line 4 in test_source
        position = _lsp_pos(line=4, character=4)
        result = get_definition(test_doc, position, test_source, st)
        assert result is not None, "Expected cross-file definition for RemoteFB"
        assert result.uri == _OTHER_URI
        assert result.range.start.line == 0

    def test_cross_file_variable_stays_local(self):
        """A local variable defined in test.scl resolves within that file."""
        source = (
            "FUNCTION_BLOCK LocalFB\n"
            "VAR_INPUT\n"
            "    crossVar : INT;\n"
            "END_VAR\n"
            "    #crossVar := 0;\n"
            "END_FUNCTION_BLOCK\n"
        )
        from s7_lsp.parsers.scl_parser import parse_scl

        doc = parse_scl(source, _TEST_URI)
        st = SymbolTable()
        st.add_from_document(_TEST_URI, doc.blocks)

        position = _lsp_pos(line=4, character=5)  # on 'crossVar' after '#'
        result = get_definition(doc, position, source, st)
        assert result is not None
        assert result.uri == _TEST_URI
        assert result.range.start.line == 2
