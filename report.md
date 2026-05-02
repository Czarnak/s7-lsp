# S7-LSP Code Analysis Report

Generated on 2026-05-02.

## Scope

This report covers:

- Graphify output for the repository.
- Static review of the Python source, tests, CI, and project metadata.
- Local verification attempts without changing source code.
- Missing capabilities and suggested additions.

No source files were changed as part of this analysis. Generated artifacts are limited to `graphify-out/` and this `report.md`.

## Graphify Report

Graphify was run with:

```bash
graphify update .
```

Generated files:

- `graphify-out/graph.json`
- `graphify-out/graph.html`
- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/manifest.json`
- `graphify-out/.graphify_root`

Graphify summary:

- 931 nodes
- 4084 edges
- 26 communities detected in `GRAPH_REPORT.md`
- Extraction mix: 32% extracted, 68% inferred
- Token cost: 0 input, 0 output

Core graph hubs:

- `SymbolTable` - 325 edges
- `ParsedDocument` - 282 edges
- `BlockDeclaration` - 224 edges
- `VarSectionKind` - 209 edges
- `BlockKind` - 206 edges

Graphify correctly highlights the repository's main coupling points: parser AST dataclasses, workspace state, the symbol table, and feature providers. The largest risk sign from the graph is that `SymbolTable` and `ParsedDocument` bridge many communities, so changes to parsing or symbol registration can affect diagnostics, hover, completion, definition, references, and symbols at once.

## Project Shape

`s7-lsp` is a Python package for a Siemens S7 language server. The main runtime stack is:

- `pygls` / `lsprotocol` for LSP server support, declared in `pyproject.toml`.
- `lark` for SCL and resource parsing.
- `pytest`, `ruff`, and `mypy` in the optional `dev` dependency group.

Main modules:

- `src/s7_lsp/server.py`: LSP capability registration and request handlers.
- `src/s7_lsp/workspace.py`: document state, parser routing, symbol table rebuilds.
- `src/s7_lsp/parsers/`: SCL, resource, and AWL parser entry points.
- `src/s7_lsp/semantic/`: symbol table, scope resolution, diagnostics, type metadata.
- `src/s7_lsp/features/`: diagnostics, symbols, completion, hover, definition, references.

## Key Findings

### 1. AWL is routed as supported but currently parses to an empty document

`workspace.py` maps `.awl` files to `siemens-awl` and registers `parse_awl` as the parser (`src/s7_lsp/workspace.py:37`, `src/s7_lsp/workspace.py:45`). The AWL parser is explicitly a stub and returns `ParsedDocument(uri=uri)` without source, blocks, tree, or diagnostics (`src/s7_lsp/parsers/awl_parser.py:1`, `src/s7_lsp/parsers/awl_parser.py:13`). README says AWL is deferred (`README.md:16`, `README.md:35`).

Impact: editors can open AWL files through the language server and receive empty results rather than an explicit "not supported yet" diagnostic. This can look like success while silently providing no real code intelligence.

Suggested fix later: either remove `.awl` routing until implemented or return a clear informational diagnostic for AWL files.

### 2. Parser internals can leak raw exception text to the client

Both SCL and resource parsing catch unexpected exceptions, log them, and also publish the exception string in a diagnostic (`src/s7_lsp/parsers/scl_parser.py:104`, `src/s7_lsp/parsers/scl_parser.py:109`, `src/s7_lsp/parsers/resource_parser.py:95`, `src/s7_lsp/parsers/resource_parser.py:99`).

Impact: as a local LSP this is not a severe security issue, but it can expose internal paths or implementation details in editor diagnostics and produce noisy user-facing messages.

Suggested fix later: publish a generic "Internal parser error" diagnostic with a stable code, and keep exception detail only in logs.

### 3. Reparse-on-every-change plus Earley parsing is a performance risk

The server advertises full document sync (`src/s7_lsp/server.py:65`, `src/s7_lsp/server.py:67`) and reparses on every change (`src/s7_lsp/server.py:118`). The workspace notes this is expected to be acceptable below typical PLC file sizes but may need debouncing or incremental parsing (`src/s7_lsp/workspace.py:10`). SCL uses Lark Earley parsing (`src/s7_lsp/parsers/scl_parser.py:8`, `src/s7_lsp/parsers/scl_parser.py:61`).

Impact: larger real-world SCL files can cause editor latency because every keystroke can trigger a full parse, symbol table invalidation, semantic diagnostics, and diagnostic publish.

Suggested fix later: add debounce, parse cancellation/coalescing, and a parser performance benchmark corpus before switching parsing strategy.

### 4. References and semantic diagnostics are regex-over-source in important paths

Semantic diagnostics detect hash variables with regexes over source text (`src/s7_lsp/semantic/semantic_diagnostics.py:28`, `src/s7_lsp/semantic/semantic_diagnostics.py:31`) and run those checks over source lines (`src/s7_lsp/semantic/semantic_diagnostics.py:76`, `src/s7_lsp/semantic/semantic_diagnostics.py:82`). Find-references builds regexes and scans each line directly (`src/s7_lsp/features/references.py:74`, `src/s7_lsp/features/references.py:91`, `src/s7_lsp/features/references.py:111`, `src/s7_lsp/features/references.py:116`).

Impact: comments, strings, attribute text, or declaration contexts can be counted as real usages. This can produce false undeclared-variable diagnostics and false reference locations.

Suggested fix later: add token-aware or parse-tree-aware source ranges for executable bodies, comments, strings, declarations, and call sites.

### 5. Duplicate block names are resolved by "last registered wins"

`SymbolTable.add_from_document` appends block symbols by lowercased name (`src/s7_lsp/semantic/symbol_table.py:124`, `src/s7_lsp/semantic/symbol_table.py:127`). `lookup_block` returns the last match (`src/s7_lsp/semantic/symbol_table.py:149`, `src/s7_lsp/semantic/symbol_table.py:152`).

Impact: if two open files define the same block/type name, go-to-definition, hover, completion, and semantic type checks can resolve to whichever one was registered last. There is no project-level duplicate block diagnostic.

Suggested fix later: detect duplicate block/type names across open documents and make lookup ambiguity explicit.

### 6. Inter-file diagnostics are disabled while inter-file features exist

The server capability sets `inter_file_dependencies=False` and `workspace_diagnostics=False` (`src/s7_lsp/server.py:71`, `src/s7_lsp/server.py:73`). At the same time, semantic diagnostics use the workspace symbol table for type/block references, and references/definition operate across open documents.

Impact: when one file changes, dependent open files may keep stale diagnostics until individually reopened or edited. This matters for UDT and FB references across files.

Suggested fix later: track dependency edges in the workspace and republish diagnostics for affected open documents after symbol table changes.

### 7. Type checking is still mostly a stub

`type_checker.py` explicitly says expression inference, assignment compatibility, function parameter validation, and implicit conversion warnings are future work (`src/s7_lsp/semantic/type_checker.py:1`, `src/s7_lsp/semantic/type_checker.py:3`). The current public behavior is mainly `is_builtin_type` (`src/s7_lsp/semantic/type_checker.py:52`).

Impact: README promises "invalid assignments" in semantic diagnostics (`README.md:23`), but the implementation does not yet provide a real assignment type checker. This creates a documentation/behavior mismatch.

Suggested fix later: implement expression typing and assignment compatibility, then add tests for numeric narrowing, string/time families, UDTs, arrays, and block parameters.

## Verification Results

Commands attempted:

- `graphify update .`: passed and generated `graphify-out`.
- `python -m ruff check src tests`: passed.
- `python -m pytest -q -p no:cacheprovider --basetemp /tmp/s7-lsp-pytest`: blocked because the package was not installed in the current environment.
- `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp /tmp/s7-lsp-pytest`: blocked because `lark` is not installed in the current environment.
- `python -m mypy src tests`: ran, but reported missing imports for `lark`, `lsprotocol`, and `pygls`, plus a few `no-any-return` findings in tests.

The CI workflow should install dependencies in GitHub Actions via `pip install -e ".[dev]"` (`.github/workflows/ci.yml:28`), so the local pytest failure appears environment-related rather than necessarily a repository test failure.

## What Is Missing

Recommended additions:

- A clear AWL unsupported diagnostic, or complete AWL parser implementation.
- A parser performance benchmark suite with representative real-world SCL files.
- Dependency-aware workspace diagnostics for cross-file UDT, FB, DB, and resource references.
- Duplicate top-level block/type/resource diagnostics across all open documents.
- Token-aware reference scanning to avoid comments and strings.
- A real type checker for expressions, assignments, function calls, implicit conversions, arrays, structs, and UDT fields.
- Tests for parser recovery and fallback behavior on malformed but partially valid SCL.
- Tests for false positives in strings/comments for diagnostics and references.
- Local developer setup docs that install `.[dev]` in one step, matching CI more closely.
- Coverage reporting in CI, preferably with thresholds for parser/semantic/feature modules.
- Release checklist or packaging verification docs for the published `s7-lsp` command.

## Suggested Priority

1. Make unsupported AWL explicit, because silent empty behavior is the easiest user-facing confusion to remove.
2. Add duplicate block/type diagnostics, because it protects every symbol-backed feature.
3. Replace regex-only reference/semantic scans with token-aware filtering.
4. Add parse debounce/coalescing and performance tests before larger grammar hardening.
5. Implement the promised assignment/type checker behavior and align README wording with actual behavior.
