# AppManager Tools

This directory contains helper scripts and lightweight wrappers used by the AppManager utilities. These tools provide convenient command-line entry points for common tasks such as validating substitution files, splitting/formatting substitutions, analyzing templates, and basic archive/backup helpers.

Available scripts
- `archive_manager.py` — Helpers for managing archive configuration files and validating archive entries.
- `backup_manager.py` — Small utilities for creating and rotating backups of generated/processed files.
- `sub_manager.py` — A lightweight wrapper around the substitution manager functionality (format/validate/search) for quick CLI usage.
- `template_analyzer.py` — Directory-level analyzer for `.db`, `.vdb`, and `.template` files (duplicate detection, diffs).
- `template_consolidator.py` — Helpers to identify consolidation candidates and produce initial consolidated templates.
- `validation_engine.py` — Entry point to the richer `ValidationEngine` used to generate `ValidationResult` objects and JSON reports.

Quick usage examples

1) Validate all substitution files under an application directory and write a JSON summary (example):

```bash
python3 AppManager/tools/validation_engine.py /path/to/app --output validation_summary.json
```

2) Format a single substitution file using the lightweight wrapper:

```bash
python3 AppManager/tools/sub_manager.py format path/to/file.substitutions
```

3) Analyze templates in a directory and write a report:

```bash
python3 AppManager/tools/template_analyzer.py analyze /path/to/db --output report.txt
```

4) Run a bulk validation from the repository root (bash):

```bash
find . -type f -name '*.substitutions' -print0 \
  | xargs -0 -n1 -P4 -I{} python3 AppManager/tools/validation_engine.py "{}" --json
```

Recommendations
- Use `validation_engine.py` for structured, machine-readable validation output (JSON). Fail CI on `Severity.CRITICAL` issues.
- Use `sub_manager.py` for quick local formatting or spot-checking when editing substitution files.
- Use `template_analyzer.py` and `template_consolidator.py` for repository audits to find duplication and consolidation opportunities.

If you want, I can add a small aggregator script `validate_substitutions.py` that walks an application directory, runs the validation engine for each `.substitutions` file, and produces a single `validation_summary.json` file. Would you like me to add that now?
# IOC Manager Suite

A comprehensive toolkit for managing EPICS IOC substitution files and database templates.

## Directory Structure

```
ioc_manager/
├── README.md                    # This file
├── ioc_sub_manager.py          # Main substitution file manager
├── template_analyzer.py        # Analyze and compare .db/.vdb templates
├── template_consolidator.py    # Find and consolidate duplicate templates
├── docs/
│   └── usage_guide.md          # Detailed usage documentation
└── examples/
    └── sample_workflow.sh      # Example workflow scripts
```

## Tools Overview

### 1. IOC Substitution Manager (`ioc_sub_manager.py`)
- Format, validate, and analyze substitution files
- Merge and split substitution files
- Search and statistics reporting
- JSON export for external processing

### 2. Template Analyzer (`template_analyzer.py`)
- Compare .db and .vdb files for similarities
- Identify duplicate record definitions
- Generate difference reports
- Track macro usage across templates

### 3. Template Consolidator (`template_consolidator.py`)
- Find candidates for consolidation
- Generate unified templates from similar .db files
- Create migration scripts
- Validate consolidation safety

## Quick Start

```bash
# Analyze templates for duplication
python template_analyzer.py compare /path/to/db/dir

# Find consolidation opportunities
python template_consolidator.py analyze /path/to/db/dir

# Format substitution files
python ioc_sub_manager.py format input.substitutions
```

## Problem Solved

This suite addresses the common EPICS IOC management challenges:

1. **Template Duplication**: Multiple .db files with slight variations that could be consolidated
2. **Format Inconsistency**: Substitution files with inconsistent formatting
3. **Maintenance Overhead**: Difficulty tracking which templates are actually different
4. **Migration Complexity**: No clear path to consolidate similar templates

## Installation

No special installation required. Python 3.6+ needed.

```bash
cd tools/ioc_manager
chmod +x *.py  # On Linux/Unix
```