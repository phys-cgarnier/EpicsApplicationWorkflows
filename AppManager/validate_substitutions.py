#!/usr/bin/env python3
"""
Validate all .substitutions files under a directory using the project's ValidationEngine.

Produces a JSON summary with per-file results.
"""
import sys
import json
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Validate .substitutions files recursively')
    parser.add_argument('root', nargs='?', default='.', help='Root directory to search')
    parser.add_argument('-o', '--output', default='validation_summary.json', help='Output JSON file')
    parser.add_argument('--fail-on-issues', action='store_true', help='Exit with code 1 if any issues found')
    args = parser.parse_args()

    # Ensure AppManager modules can be imported
    appmanager_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(appmanager_dir))

    try:
        from app_validation_engine import ValidationEngine
    except Exception as e:
        print(f"Error importing ValidationEngine: {e}", file=sys.stderr)
        sys.exit(2)

    engine = ValidationEngine()

    root = Path(args.root)
    files = sorted(root.rglob('*.substitutions'))

    summary = {'files_validated': len(files), 'total_issues': 0}
    results = []

    for path in files:
        print(f"Validating {path}")
        try:
            res = engine.validate_substitution_file(str(path))
        except Exception as e:
            results.append({
                'file': str(path),
                'passed': False,
                'error': str(e),
                'issue_count': None,
                'issues': []
            })
            summary['total_issues'] += 1
            continue

        issues = [i.to_dict() for i in res.issues]
        results.append({
            'file': str(path),
            'passed': res.passed,
            'issue_count': len(issues),
            'issues': issues
        })
        summary['total_issues'] += len(issues)

    out = {'summary': summary, 'results': results}

    out_path = Path(args.output)
    with out_path.open('w') as f:
        json.dump(out, f, indent=2)

    print(f"Validated {summary['files_validated']} files. Total issues: {summary['total_issues']}")
    print(f"Summary written to: {out_path}")

    if args.fail_on_issues and summary['total_issues'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
