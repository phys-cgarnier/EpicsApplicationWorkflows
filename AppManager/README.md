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