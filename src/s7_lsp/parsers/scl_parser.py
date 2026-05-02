"""SCL parser — wraps lark grammar and transforms parse trees into AST nodes.

Architecture:
    1. Lark parses raw text → produces a parse tree (lark.Tree)
    2. SCLTransformer converts the tree → our AST dataclasses
    3. Parse errors become Diagnostic objects with source positions

We use Earley parser for Phase 1 because:
    - It handles ambiguous grammars gracefully (SCL has some)
    - Better error messages than LALR on parse failures
    - Performance is acceptable for typical PLC files (< 10k lines)
    - We can switch to LALR later if profiling shows a need
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from lark import Lark, Token, Tree, UnexpectedCharacters, UnexpectedToken
from lark.exceptions import UnexpectedInput

from s7_lsp.ast_nodes import (
    BlockDeclaration,
    BlockKind,
    Diagnostic,
    ParsedDocument,
    Position,
    Range,
    VarDeclaration,
    VarSection,
    VarSectionKind,
)
from s7_lsp.parsers.parser_utils import (
    generic_parse_diagnostic,
    unexpected_char_diagnostic,
    unexpected_token_diagnostic,
)
from s7_lsp.parsers.parser_utils import (
    tree_range as _tree_range,
)

logger = logging.getLogger(__name__)

# ─── Grammar Loading ──────────────────────────────────────────

_GRAMMAR_PATH = Path(__file__).parent / "scl_grammar.lark"

# Singleton parser — grammar compilation is expensive, do it once.
_parser: Lark | None = None


def _get_parser() -> Lark:
    """Lazily compile and cache the lark parser."""
    global _parser
    if _parser is None:
        grammar_text = _GRAMMAR_PATH.read_text(encoding="utf-8")
        _parser = Lark(
            grammar_text,
            parser="earley",
            start="start",
            propagate_positions=True,  # Attach line/col to every Tree node
            maybe_placeholders=False,
        )
    return _parser


# ─── Public API ───────────────────────────────────────────────


def parse_scl(source: str, uri: str = "") -> ParsedDocument:
    """Parse SCL source text and return a ParsedDocument.

    Always returns a document — on parse failure, the document will have
    diagnostics but may have partial block information from the fallback
    regex scanner.

    Args:
        source: Raw SCL source text.
        uri: Document URI (for tracking which file this belongs to).

    Returns:
        ParsedDocument with blocks and/or diagnostics.
    """
    parser = _get_parser()
    doc = ParsedDocument(uri=uri, source=source)

    try:
        tree = parser.parse(source)
        doc.tree = tree
        doc.blocks = _extract_blocks(tree)
    except UnexpectedCharacters as e:
        doc.diagnostics.append(unexpected_char_diagnostic(e))
        doc.blocks = _fallback_extract_blocks(source)
    except UnexpectedToken as e:
        doc.diagnostics.append(
            unexpected_token_diagnostic(e, clean_expected=_clean_expected_tokens)
        )
        doc.blocks = _fallback_extract_blocks(source)
    except UnexpectedInput as e:
        doc.diagnostics.append(generic_parse_diagnostic(e))
        doc.blocks = _fallback_extract_blocks(source)
    except Exception as e:
        # Catch-all for unexpected parser failures — don't crash the LSP
        logger.exception("Unexpected parser error")
        doc.diagnostics.append(
            Diagnostic(
                message="Internal parser error (see language server logs for details).",
                range=Range(Position(0, 0), Position(0, 0)),
                severity=1,
                source="s7-lsp",
            )
        )

    return doc


# ─── Tree → AST Extraction ───────────────────────────────────


def _extract_blocks(tree: Tree) -> list[BlockDeclaration]:
    """Walk the parse tree and extract block declarations."""
    blocks: list[BlockDeclaration] = []

    for child in tree.children:
        if not isinstance(child, Tree):
            continue

        block = _extract_block(child)
        if block is not None:
            blocks.append(block)

    return blocks


def _extract_block(node: Tree) -> BlockDeclaration | None:
    """Extract a single block declaration from a parse tree node."""
    kind_map: dict[str, BlockKind] = {
        "function_block": BlockKind.FUNCTION_BLOCK,
        "function_decl": BlockKind.FUNCTION,
        "organization_block": BlockKind.ORGANIZATION_BLOCK,
        "data_block": BlockKind.DATA_BLOCK,
        "type_decl": BlockKind.TYPE,
    }

    kind = kind_map.get(node.data)
    if kind is None:
        return None

    name = _extract_name(node)
    return_type = _extract_return_type(node) if kind == BlockKind.FUNCTION else None
    version = _extract_version(node)
    var_sections = _extract_var_sections(node)
    block_range = _tree_range(node)
    attribute = _extract_attribute(node)

    return BlockDeclaration(
        kind=kind,
        name=name,
        return_type=return_type,
        version=version,
        var_sections=var_sections,
        range=block_range,
        attribute=attribute,
    )


def _extract_name(node: Tree) -> str:
    """Extract the block name from a declaration node."""
    for child in node.children:
        if isinstance(child, Tree) and child.data in ("quoted_name", "plain_name"):
            token = child.children[0]
            if isinstance(token, Token):
                # Strip quotes from quoted identifiers
                value = str(token)
                return value.strip('"') if value.startswith('"') else value
    return "<unknown>"


def _extract_return_type(node: Tree) -> str | None:
    """Extract the return type from a FUNCTION declaration."""
    for child in node.children:
        if isinstance(child, Tree) and child.data == "builtin_type":
            return str(child.children[0]).upper()
        if isinstance(child, Tree) and child.data in ("quoted_name", "plain_name"):
            # Skip the function name itself — return type comes after ':'
            continue
    # Check for type_ref after the ':'
    found_name = False
    for child in node.children:
        if isinstance(child, Tree) and child.data in ("quoted_name", "plain_name"):
            if found_name:
                # Second name_ref is the return type (user-defined)
                token = child.children[0]
                value = str(token)
                return value.strip('"') if value.startswith('"') else value
            found_name = True
        elif isinstance(child, Tree) and child.data == "builtin_type":
            if found_name:
                return str(child.children[0]).upper()
    return None


def _extract_version(node: Tree) -> str | None:
    """Extract VERSION : x.y from a block."""
    for child in node.children:
        if isinstance(child, Tree) and child.data == "version":
            for token in child.children:
                if isinstance(token, Token) and token.type == "VERSION_NUM":
                    return str(token)
    return None


def _extract_attribute(node: Tree) -> str | None:
    """Extract the attribute block { ... } if present."""
    for child in node.children:
        if isinstance(child, Token) and child.type == "ATTRIBUTE":
            return str(child)
    return None


def _extract_var_sections(node: Tree) -> list[VarSection]:
    """Extract all VAR sections from a block."""
    sections: list[VarSection] = []

    for child in node.children:
        if isinstance(child, Tree) and child.data == "var_section":
            section = _extract_var_section(child)
            if section is not None:
                sections.append(section)

    return sections


def _extract_var_section(node: Tree) -> VarSection | None:
    """Extract a single VAR section with its declarations."""
    kind = VarSectionKind.VAR
    is_constant = False
    is_retain = False

    # Determine section kind from var_keyword child
    for child in node.children:
        if isinstance(child, Tree):
            kind_map: dict[str, VarSectionKind] = {
                "var_input": VarSectionKind.VAR_INPUT,
                "var_output": VarSectionKind.VAR_OUTPUT,
                "var_in_out": VarSectionKind.VAR_IN_OUT,
                "var_temp": VarSectionKind.VAR_TEMP,
                "var_global": VarSectionKind.VAR_GLOBAL,
                "var_external": VarSectionKind.VAR_EXTERNAL,
                "var_local": VarSectionKind.VAR,
            }
            if child.data in kind_map:
                kind = kind_map[child.data]
            elif child.data == "constant_flag":
                is_constant = True
            elif child.data == "retain_flag":
                is_retain = True

    if is_constant:
        kind = VarSectionKind.VAR_CONSTANT

    declarations = _extract_var_decls(node, kind)

    return VarSection(
        kind=kind,
        declarations=declarations,
        range=_tree_range(node),
        is_constant=is_constant,
        is_retain=is_retain,
    )


def _extract_var_decls(section_node: Tree, section_kind: VarSectionKind) -> list[VarDeclaration]:
    """Extract variable declarations from a VAR section."""
    decls: list[VarDeclaration] = []

    for child in section_node.children:
        if isinstance(child, Tree) and child.data == "var_decl":
            decls.extend(_extract_single_var_decl(child, section_kind))

    return decls


def _extract_single_var_decl(node: Tree, section_kind: VarSectionKind) -> list[VarDeclaration]:
    """Extract one or more variable declarations from a var_decl node.

    A var_decl can declare multiple variables: `a, b, c : INT;`
    Each gets its own VarDeclaration with the same type.
    """
    names: list[str] = []
    type_name = "<unknown>"
    has_default = False
    attribute: str | None = None

    for child in node.children:
        if isinstance(child, Token):
            if child.type == "ATTRIBUTE":
                attribute = str(child)
        elif isinstance(child, Tree):
            if child.data == "ident_list":
                names = [str(t) for t in child.children if isinstance(t, Token)]
            elif child.data in ("builtin_type", "string_type", "array_type", "struct_decl"):
                type_name = _type_to_string(child)
            elif child.data in ("quoted_name", "plain_name"):
                type_name = _name_to_string(child)
            elif child.data == "var_init":
                has_default = True

    decl_range = _tree_range(node)
    return [
        VarDeclaration(
            name=name,
            type_name=type_name,
            section_kind=section_kind,
            range=decl_range,
            has_default=has_default,
            attribute=attribute,
        )
        for name in names
    ]


# ─── Type Stringification ────────────────────────────────────


def _type_to_string(node: Tree) -> str:
    """Convert a type AST node back to a human-readable string."""
    if node.data == "builtin_type":
        for child in node.children:
            if isinstance(child, Token):
                return str(child).upper()
        return "<unknown>"

    if node.data == "string_type":
        for child in node.children:
            if isinstance(child, Token) and child.type == "STRING_TYPE_KW":
                base = str(child).upper()
                # Check for length specification [n]
                for c2 in node.children:
                    if isinstance(c2, Tree):
                        return f"{base}[...]"
                return base
        return "STRING"

    if node.data == "array_type":
        # Find the element type
        for child in node.children:
            if isinstance(child, Tree) and child.data not in ("array_range",):
                elem_type = _type_to_string(child) if isinstance(child, Tree) else str(child)
                return f"ARRAY OF {elem_type}"
        return "ARRAY"

    if node.data == "struct_decl":
        return "STRUCT"

    return "<unknown>"


def _name_to_string(node: Tree) -> str:
    """Extract name string from a name node."""
    token = node.children[0]
    value = str(token)
    return value.strip('"') if value.startswith('"') else value


def _clean_expected_tokens(expected: set[str]) -> list[str]:
    """Make lark's expected token names human-readable.

    Lark reports expected tokens as internal names like '__ANON_0',
    'IDENT', 'SEMICOLON'. We translate the useful ones.
    """
    result: list[str] = []
    for token in expected:
        if token.startswith("__ANON_"):
            continue  # Skip anonymous tokens
        if token.startswith("$"):
            continue  # Skip internal rules
        # Map common terminal names to readable forms
        readable = {
            "SEMICOLON": "';'",
            "IDENT": "identifier",
            "QUOTED_IDENT": "quoted identifier",
            "HASH_IDENT": "variable (#name)",
            "INTEGER": "number",
            "STRING": "string",
        }.get(token, token)
        result.append(readable)
    return result


# ─── Fallback Regex Scanner ──────────────────────────────────

# Patterns for block declarations — used when full parse fails
_BLOCK_PATTERNS = [
    (
        BlockKind.FUNCTION_BLOCK,
        re.compile(
            r'(?i)^\s*FUNCTION_BLOCK\s+("([^"]+)"|([A-Za-z_]\w*))',
            re.MULTILINE,
        ),
    ),
    (
        BlockKind.FUNCTION,
        re.compile(
            r'(?i)^\s*FUNCTION\s+("([^"]+)"|([A-Za-z_]\w*))\s*:\s*(\w+)',
            re.MULTILINE,
        ),
    ),
    (
        BlockKind.ORGANIZATION_BLOCK,
        re.compile(
            r'(?i)^\s*ORGANIZATION_BLOCK\s+("([^"]+)"|([A-Za-z_]\w*))',
            re.MULTILINE,
        ),
    ),
    (
        BlockKind.DATA_BLOCK,
        re.compile(
            r'(?i)^\s*DATA_BLOCK\s+("([^"]+)"|([A-Za-z_]\w*))',
            re.MULTILINE,
        ),
    ),
    (
        BlockKind.TYPE,
        re.compile(
            r'(?i)^\s*TYPE\s+("([^"]+)"|([A-Za-z_]\w*))',
            re.MULTILINE,
        ),
    ),
]

# Pattern for variable declarations inside VAR sections
_VAR_SECTION_PATTERN = re.compile(
    r"(?i)\b(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_GLOBAL|VAR_EXTERNAL|VAR)\b",
)

_VAR_DECL_PATTERN = re.compile(
    r"^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*:\s*(\w[\w\[\]., #]*?)\s*(?::=|;)",
    re.MULTILINE,
)


def _fallback_extract_blocks(source: str) -> list[BlockDeclaration]:
    """Regex-based block extraction for files that fail full parsing.

    This provides document symbols even when the parser can't handle
    the full file. It's intentionally simple — just identifies block
    boundaries and names.
    """
    blocks: list[BlockDeclaration] = []

    for kind, pattern in _BLOCK_PATTERNS:
        for match in pattern.finditer(source):
            # Group 2 is quoted name, group 3 is plain name
            name = match.group(2) or match.group(3) or "<unknown>"
            line = source[: match.start()].count("\n")
            col = match.start() - source.rfind("\n", 0, match.start()) - 1

            return_type = None
            if kind == BlockKind.FUNCTION and match.lastindex and match.lastindex >= 4:
                return_type = match.group(4)

            blocks.append(
                BlockDeclaration(
                    kind=kind,
                    name=name,
                    return_type=return_type,
                    range=Range(
                        start=Position(line=line, character=max(0, col)),
                        end=Position(line=line, character=max(0, col) + len(match.group(0))),
                    ),
                )
            )

    return blocks
