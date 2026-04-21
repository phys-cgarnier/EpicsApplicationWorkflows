AppManager — IOC Manager Suite

A concise toolkit for managing EPICS IOC substitution files and database templates.

## Directory Structure (inside this workspace)

```
AppManager/
├── APP_MANAGER_COMPREHENSIVE.md
├── README.md                     # This file
├── validate_substitutions.py
├── validate_templates.py
├── app/
│   ├── app_ide.py
│   ├── app_master.py
│   └── app_workflow_manager.py
├── tools/
│   ├── archive_manager.py
│   ├── backup_manager.py
│   ├── sub_manager.py
│   ├── template_analyzer.py
│   ├── template_consolidator.py
│   └── validation_engine.py
└── deprecated/
        ├── app_report.txt
        └── IMPLEMENTATION_SUMMARY.md
```

## Tools Overview

- **Substitution & Validation** (`tools/sub_manager.py`, `validate_substitutions.py`):
    - Format, validate, split and merge substitution files
    - Produce reports and exports for downstream tools

- **Template Analyzer** (`tools/template_analyzer.py`):
    - Compare `.db` and `.vdb` templates
    - Identify duplicate or similar record definitions
    - Generate difference and macro-usage reports

- **Template Consolidator** (`tools/template_consolidator.py`):
    - Suggest consolidation candidates
    - Assist generating unified templates and migration steps
    - Validate consolidation safety before changes

## Quick Start

Run the tools from the repository root. Examples:

```bash
# Analyze templates for duplication
python AppManager/tools/template_analyzer.py compare /path/to/db/dir

# Find consolidation opportunities
python AppManager/tools/template_consolidator.py analyze /path/to/db/dir

# Validate or format substitution files
python AppManager/tools/sub_manager.py format input.substitutions
python AppManager/validate_substitutions.py input.substitutions
```

## Problems Addressed

This toolkit helps with common EPICS IOC maintenance tasks:

- Template duplication and drift
- Inconsistent substitution formatting
- Difficulty tracking template differences
- Safe consolidation and migration planning

## Requirements

- Python 3.6+

## Notes

- Scripts live under `AppManager/tools/` and the top-level `AppManager/` folder.
- See `APP_MANAGER_COMPREHENSIVE.md` for a detailed usage guide and workflow examples.