"""Resource file parser — Phase 4.

Handles .s7res files containing multilingual text definitions (MLC_ entries)
and configuration key-value properties in YAML-like format.

Architecture mirrors scl_parser.py:
    1. Lark parses raw text → produces a parse tree (lark.Tree)
    2. _extract_blocks walks the tree → our AST dataclasses
    3. Parse errors become Diagnostic objects with source positions
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

logger = logging.getLogger(__name__)

# ─── Grammar Loading ──────────────────────────────────────────

_GRAMMAR_PATH = Path(__file__).parent / "resource_grammar.lark"

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
            propagate_positions=True,
            maybe_placeholders=False,
        )
    return _parser


# ─── Public API ───────────────────────────────────────────────


def parse_resource(source: str, uri: str = "") -> ParsedDocument:
    """Parse a .s7res resource file and return a ParsedDocument.

    Always returns a document — on parse failure the document will have
    diagnostics but no blocks (no fallback scanner for resource files).

    Args:
        source: Raw resource file source text.
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
        doc.diagnostics.append(_unexpected_char_diagnostic(e))
    except UnexpectedToken as e:
        doc.diagnostics.append(_unexpected_token_diagnostic(e))
    except UnexpectedInput as e:
        doc.diagnostics.append(_generic_parse_diagnostic(e))
    except Exception as e:
        logger.exception("Unexpected resource parser error")
        doc.diagnostics.append(
            Diagnostic(
                message=f"Internal parser error: {e}",
                range=Range(Position(0, 0), Position(0, 0)),
                severity=1,
            )
        )

    return doc


# ─── Classification Helpers ───────────────────────────────────


def _is_lang_code(key: str) -> bool:
    """Check if a property key matches the BCP-47 language code pattern.

    Language codes require a region: 2 lowercase letters + hyphen + 2 uppercase letters.
    Examples: en-US, de-DE, fr-FR, zh-CN
    Plain 2-letter codes (en, de, fr) are treated as regular properties.
    """
    return re.fullmatch(r"[a-z]{2}-[A-Z]{2}", key) is not None


# ─── Tree → AST Extraction ───────────────────────────────────


def _extract_blocks(tree: Tree) -> list[BlockDeclaration]:
    """Walk the parse tree and extract resource entry block declarations."""
    blocks: list[BlockDeclaration] = []

    for child in tree.children:
        if isinstance(child, Tree) and child.data == "entry":
            block = _extract_entry_block(child)
            if block is not None:
                blocks.append(block)

    return blocks


def _extract_entry_block(node: Tree) -> BlockDeclaration | None:
    """Convert a single resource entry parse tree node into a BlockDeclaration.

    Each MLC_ entry maps to a DATA_BLOCK with:
      - VAR section for language entries (keys matching ISO language code pattern)
      - VAR_CONSTANT section for property key-value pairs (all other keys)
    Only non-empty sections are included.
    """
    mlc_name: str | None = None
    lang_decls: list[VarDeclaration] = []
    prop_decls: list[VarDeclaration] = []

    for child in node.children:
        if not isinstance(child, Tree):
            continue

        if child.data == "entry_id":
            # entry_id contains the MLC_ID token
            for token in child.children:
                if isinstance(token, Token) and token.type == "MLC_ID":
                    mlc_name = str(token)

        elif child.data == "property_line":
            # property_line contains a PROPERTY_KEY token and a string_value tree
            # Classify as language entry or property based on key pattern
            decl = _extract_property_line(child)
            if decl is not None:
                if _is_lang_code(decl.name):
                    decl.type_name = "STRING"
                    decl.section_kind = VarSectionKind.VAR
                    lang_decls.append(decl)
                else:
                    decl.section_kind = VarSectionKind.VAR_CONSTANT
                    prop_decls.append(decl)

    if mlc_name is None:
        return None

    var_sections: list[VarSection] = []

    if lang_decls:
        var_sections.append(
            VarSection(
                kind=VarSectionKind.VAR,
                declarations=lang_decls,
                range=_tree_range(node),
            )
        )

    if prop_decls:
        var_sections.append(
            VarSection(
                kind=VarSectionKind.VAR_CONSTANT,
                declarations=prop_decls,
                range=_tree_range(node),
                is_constant=True,
            )
        )

    return BlockDeclaration(
        kind=BlockKind.DATA_BLOCK,
        name=mlc_name,
        var_sections=var_sections,
        range=_tree_range(node),
    )


def _extract_property_line(node: Tree) -> VarDeclaration | None:
    """Extract a property_line (key: value) into a VarDeclaration.

    The key is extracted as PROPERTY_KEY token.
    The value is extracted from the string_value subtree.
    Classification as language entry vs property key is done in _extract_entry_block.
    """
    key: str | None = None
    value: str | None = None

    for child in node.children:
        if isinstance(child, Token) and child.type == "PROPERTY_KEY":
            key = str(child)
        elif isinstance(child, Tree) and child.data == "string_value":
            value = _extract_string_value(child)

    if key is None:
        return None

    return VarDeclaration(
        name=key,
        type_name=value or "",  # type_name is overwritten if this is a language entry
        section_kind=VarSectionKind.VAR_CONSTANT,  # section_kind is overwritten if language
        range=_tree_range(node),
        attribute=value,  # attribute holds the actual value for language entries
    )


def _extract_string_value(node: Tree) -> str:
    """Extract the string content from a string_value parse node.

    - SINGLE_QUOTED_STRING: strip surrounding single quotes
    - BARE_VALUE: strip leading/trailing whitespace
    """
    for child in node.children:
        if isinstance(child, Token):
            value = str(child)
            if child.type == "SINGLE_QUOTED_STRING":
                return value[1:-1]
            elif child.type == "BARE_VALUE":
                return value.strip()
    return ""


# ─── Position Helpers ─────────────────────────────────────────


def _tree_range(node: Tree) -> Range:
    """Extract source range from a lark Tree node.

    Lark populates line/column on nodes when propagate_positions=True.
    Line is 1-based in lark, we convert to 0-based for LSP.
    """
    start_line = getattr(node.meta, "line", 1) - 1
    start_col = getattr(node.meta, "column", 1) - 1
    end_line = getattr(node.meta, "end_line", start_line + 1) - 1
    end_col = getattr(node.meta, "end_column", start_col + 1) - 1

    return Range(
        start=Position(line=max(0, start_line), character=max(0, start_col)),
        end=Position(line=max(0, end_line), character=max(0, end_col)),
    )


# ─── Error → Diagnostic Conversion ───────────────────────────


def _unexpected_char_diagnostic(e: UnexpectedCharacters) -> Diagnostic:
    """Convert lark UnexpectedCharacters to a Diagnostic."""
    line = (e.line or 1) - 1
    col = (e.column or 1) - 1
    char = e.char if hasattr(e, "char") and e.char else "?"

    return Diagnostic(
        message=f"Unexpected character: '{char}'",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + 1),
        ),
        severity=1,
    )


def _unexpected_token_diagnostic(e: UnexpectedToken) -> Diagnostic:
    """Convert lark UnexpectedToken to a Diagnostic."""
    line = (e.line or 1) - 1
    col = (e.column or 1) - 1
    token = str(e.token) if e.token else "?"

    return Diagnostic(
        message=f"Unexpected token: '{token}'",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + len(token)),
        ),
        severity=1,
    )


def _generic_parse_diagnostic(e: UnexpectedInput) -> Diagnostic:
    """Convert any UnexpectedInput to a Diagnostic."""
    line = (getattr(e, "line", 1) or 1) - 1
    col = (getattr(e, "column", 1) or 1) - 1

    return Diagnostic(
        message=f"Syntax error: {e}",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + 1),
        ),
        severity=1,
    )
