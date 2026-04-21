#!/usr/bin/env python3
"""
Launch script for the Enhanced IOC Dashboard
============================================
Author: SLAC Cryoplant Team
Date: 2024
"""

import sys
import os
from pathlib import Path

# Add the parent directory to path so we can import our modules
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir.parent))

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = {
        'PyQt6': 'PyQt6',
        'dataclasses': None,  # Built-in for Python 3.7+
        'pathlib': None,      # Built-in
    }

    missing = []
    for package, pip_name in required_packages.items():
        if pip_name:  # Only check non-builtin packages
            try:
                __import__(package)
            except ImportError:
                missing.append(pip_name)

    if missing:
        print("Missing required packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstall with:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True

def main():
    """Main entry point"""
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║     IOC Manager v2.0 - Enhanced Edition               ║
    ║     SLAC Cryoplant Control System                     ║
    ╔════════════════════════════════════════════════════════╗
    ║                                                        ║
    ║  Features:                                             ║
    ║  • Intelligent Validation Engine                      ║
    ║  • Preview & Approval Workflows                       ║
    ║  • Automatic Backup Management                        ║
    ║  • Archive Synchronization                            ║
    ║  • Quote Rule Enforcement                             ║
    ║  • Multi-stage Validation                             ║
    ║                                                        ║
    ╚════════════════════════════════════════════════════════╝
    """)

    print("Checking requirements...")
    if not check_requirements():
        return 1

    print("Starting Enhanced IOC Dashboard...")

    try:
        from ioc_dashboard_enhanced import main as run_dashboard
        return run_dashboard()
    except Exception as e:
        print(f"\nError launching dashboard: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())