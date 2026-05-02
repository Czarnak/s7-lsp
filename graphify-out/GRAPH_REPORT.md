# Graph Report - s7-lsp  (2026-05-02)

## Corpus Check
- 37 files · ~28,839 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 931 nodes · 4084 edges · 26 communities detected
- Extraction: 32% EXTRACTED · 68% INFERRED · 0% AMBIGUOUS · INFERRED: 2797 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]

## God Nodes (most connected - your core abstractions)
1. `SymbolTable` - 325 edges
2. `ParsedDocument` - 282 edges
3. `BlockDeclaration` - 224 edges
4. `VarSectionKind` - 209 edges
5. `BlockKind` - 206 edges
6. `Range` - 205 edges
7. `Position` - 195 edges
8. `VarSection` - 189 edges
9. `VarDeclaration` - 180 edges
10. `VariableSymbol` - 180 edges

## Surprising Connections (you probably didn't know these)
- `_make_var_section()` --calls--> `VarSection`  [INFERRED]
  tests\test_definition.py → src\s7_lsp\ast_nodes.py
- `Tests for the get_hover() feature function.  Covers: - Hash-prefixed variable` --uses--> `ParsedDocument`  [INFERRED]
  tests\test_hover.py → src\s7_lsp\ast_nodes.py
- `Extract the markdown string from an lsp.Hover.` --uses--> `ParsedDocument`  [INFERRED]
  tests\test_hover.py → src\s7_lsp\ast_nodes.py
- `Hovering over #-prefixed identifiers should show type and section.` --uses--> `ParsedDocument`  [INFERRED]
  tests\test_hover.py → src\s7_lsp\ast_nodes.py
- `#Enable is VAR_INPUT BOOL in MotorControl (line 13, col 7).` --uses--> `ParsedDocument`  [INFERRED]
  tests\test_hover.py → src\s7_lsp\ast_nodes.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (207): _block_name_completions(), _builtin_type_completions(), _count_unmatched(), _find_call_name(), get_completions(), _get_identifier_before_dot(), _keyword_completions(), _make_plain_item() (+199 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (113): Document and workspace symbol providers.  Provides the file outline (document, Convert a VAR section to a DocumentSymbol containing its declarations., Convert a variable declaration to a DocumentSymbol., Search for symbols across the workspace matching a query string.      LSP clie, Convert our AST Range to LSP Range., Return True when the block represents an MLC_ resource entry., Return hierarchical document symbols for a parsed document.      Each block be, Convert a block declaration to an LSP DocumentSymbol with children. (+105 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (33): Enum, _collect_chain_left(), get_context(), _get_line(), _ident_end(), _ident_start(), Shared feature utilities for S7-LSP.  Provides: - word_at_position(): extract, Extract the SCL word (identifier) at the given 0-based line/character.      Ha (+25 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (47): _format_block_hover(), _format_variable_hover(), get_hover(), _make_hover(), _hover_value(), _pos(), Tests for the get_hover() feature function.  Covers: - Hash-prefixed variable, Hovering on "MotorControl" at line 0 shows FB signature. (+39 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (65): Shared helpers for parser source ranges and diagnostics., Extract a zero-based source range from a Lark tree node., Convert Lark UnexpectedCharacters to a parser diagnostic., Convert Lark UnexpectedToken to a parser diagnostic., Convert Lark UnexpectedInput to a parser diagnostic., tree_range(), Lazily compile and cache the lark parser., Parse a .s7res resource file and return a ParsedDocument.      Always returns (+57 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (24): get_definition(), _strip_sigil(), _symbol_to_location(), generic_parse_diagnostic(), unexpected_char_diagnostic(), unexpected_token_diagnostic(), _get_parser(), parse_resource() (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (32): get_diagnostics(), Diagnostics provider — converts parsed diagnostics to LSP protocol format.  Ph, Convert all diagnostics from a parsed document to LSP format.      This is the, Convert a single AST diagnostic to LSP format., _to_lsp_diagnostic(), main(), Entry point for the S7-LSP language server.  This module is invoked when runni, create_server() (+24 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (15): fb_with_vars(), _make_fb(), _make_fc(), _pos(), _range(), table(), TestAddFromDocument, TestAddFromDocumentIdempotence (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (13): db_block(), fb_with_vars(), _make_block(), _pos(), _range(), scope(), table(), TestGetBlockAtPosition (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (31): _find_occurrences(), get_references(), _symbol_location(), _lines(), parsed_doc_a(), parsed_doc_b(), _pos(), Tests for the find-references feature (features/references.py).  Covers: - Va (+23 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (16): get_semantic_diagnostics(), _empty_doc(), _error_doc(), _make_range(), _make_var_decl(), A variable typed as a registered block (e.g. FB instance) → no Warning., Assigning to a VAR_INPUT variable inside a FUNCTION_BLOCK → Error., Assigning to a VAR_OUTPUT variable inside a FB is allowed — no Error. (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (26): get_type_hover_text(), Built-in S7 type descriptions for hover and completion.  Provides a static dic, Metadata for a single S7 built-in type., Return a formatted markdown hover string for a built-in S7 type.      Lookup i, TypeDescription, Tests for semantic/type_info.py.  Covers every acceptance criterion for task_0, The type_info module must not import from lsprotocol.      We check the actual, String/char types have no numeric range. (+18 more)

### Community 12 - "Community 12"
Cohesion: 0.24
Nodes (14): _clean_expected_tokens(), _extract_attribute(), _extract_block(), _extract_blocks(), _extract_name(), _extract_return_type(), _extract_single_var_decl(), _extract_var_decls() (+6 more)

### Community 13 - "Community 13"
Cohesion: 0.23
Nodes (11): _extract_blocks(), _extract_entry_block(), _extract_property_line(), _extract_string_value(), _is_lang_code(), Resource file parser — Phase 4.  Handles .s7res files containing multilingual, Check if a property key matches the BCP-47 language code pattern.      Languag, Walk the parse tree and extract resource entry block declarations. (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.2
Nodes (5): Case-insensitive block name lookup.          Returns ``None`` if no block with, Find a variable by name within a specific block.          Comparison is case-i, Return all variables declared in the named block.          Returns an empty li, Return the block/type referenced by a variable's type name., Look up any symbol by name (blocks only for now).

### Community 15 - "Community 15"
Cohesion: 0.57
Nodes (7): _block_to_symbol(), get_document_symbols(), _is_resource_entry(), search_workspace_symbols(), _to_lsp_range(), _var_decl_to_symbol(), _var_section_to_symbol()

### Community 16 - "Community 16"
Cohesion: 0.29
Nodes (4): A #variable in the body not declared in any VAR section → Error., A #variable that IS declared produces no undeclared error., Undeclared variable usage is reported as Error (severity 1), not Warning., TestUndeclaredVariableUsage

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (3): Register all symbols from a parsed document.          If the URI already has s, Remove all symbols that were registered from *uri*., Construct a :class:`BlockSymbol` from a :class:`BlockDeclaration`.

### Community 18 - "Community 18"
Cohesion: 0.4
Nodes (3): get_variables_in_block returns [] for an unregistered block., get_variables_in_block returns all variables regardless of section., TestGetVariablesInBlock

### Community 19 - "Community 19"
Cohesion: 0.4
Nodes (4): _check_undeclared_type_references(), is_builtin_type(), Type checking and inference for SCL — STUB (Phase 2).  Will provide: - Expres, Check if a type name is a built-in S7 type.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): S7-LSP: Language Server Protocol for Siemens S7 PLC languages.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): LSP feature implementations for S7-LSP.  Phase 1 (active): diagnostics, symbol

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Parsers for S7 PLC languages.  Active parsers: - scl_parser: SCL / Structured

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Remove all symbols from all documents.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Return all registered :class:`BlockSymbol` objects.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Semantic analysis for S7 PLC languages.  Active modules: - symbol_table: work

## Knowledge Gaps
- **35 isolated node(s):** `AST node definitions for S7 SCL parsed structures.  These dataclasses represen`, `Zero-based line and character offset in source text.`, `Start-end span in source text.`, `A single variable declaration within a VAR section.`, `A VAR_* ... END_VAR section.` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 20`** (2 nodes): `S7-LSP: Language Server Protocol for Siemens S7 PLC languages.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `LSP feature implementations for S7-LSP.  Phase 1 (active): diagnostics, symbol`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `Parsers for S7 PLC languages.  Active parsers: - scl_parser: SCL / Structured`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `Remove all symbols from all documents.`, `.clear()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `Return all registered :class:`BlockSymbol` objects.`, `.get_all_blocks()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `Semantic analysis for S7 PLC languages.  Active modules: - symbol_table: work`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ParsedDocument` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 10`, `Community 13`, `Community 16`?**
  _High betweenness centrality (0.261) - this node is a cross-community bridge._
- **Why does `SymbolTable` connect `Community 0` to `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 14`, `Community 16`, `Community 17`, `Community 18`, `Community 23`, `Community 24`?**
  _High betweenness centrality (0.243) - this node is a cross-community bridge._
- **Why does `ScopeManager` connect `Community 0` to `Community 1`, `Community 3`, `Community 5`, `Community 8`, `Community 9`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 309 inferred relationships involving `SymbolTable` (e.g. with `Workspace` and `Workspace document manager.  Tracks open documents, routes files to the correc`) actually correct?**
  _`SymbolTable` has 309 INFERRED edges - model-reasoned connections that need verification._
- **Are the 280 inferred relationships involving `ParsedDocument` (e.g. with `S7-LSP server — pygls-based Language Server Protocol implementation.  This mod` and `Create and configure the S7-LSP language server.      Returns a fully configur`) actually correct?**
  _`ParsedDocument` has 280 INFERRED edges - model-reasoned connections that need verification._
- **Are the 222 inferred relationships involving `BlockDeclaration` (e.g. with `Document and workspace symbol providers.  Provides the file outline (document` and `Return True when the block represents an MLC_ resource entry.`) actually correct?**
  _`BlockDeclaration` has 222 INFERRED edges - model-reasoned connections that need verification._
- **Are the 207 inferred relationships involving `VarSectionKind` (e.g. with `Document and workspace symbol providers.  Provides the file outline (document` and `Return True when the block represents an MLC_ resource entry.`) actually correct?**
  _`VarSectionKind` has 207 INFERRED edges - model-reasoned connections that need verification._