"""Semantic analysis for S7 PLC languages.

Active modules:
- symbol_table: workspace-wide symbol registry
- scope: lexical scope management
- semantic_diagnostics: SCL semantic checks (undeclared vars, type refs, etc.)
- resource_diagnostics: .s7res resource file checks (duplicate IDs, missing langs)
"""
