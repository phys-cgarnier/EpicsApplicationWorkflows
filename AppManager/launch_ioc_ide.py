#!/usr/bin/env python3
"""
Launch script for IOC IDE
==========================
"""

import sys
import os
from pathlib import Path

# Add the parent directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

def check_requirements():
    """Check if required packages are installed"""
    required = ['PyQt6']
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

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
    ╔══════════════════════════════════════════════════════════════╗
    ║                IOC IDE - SLAC Cryoplant                     ║
    ║            Integrated Development Environment                ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  Your IOC-Centric Management System:                        ║
    ║                                                              ║
    ║  • One IOC at a time focus                                  ║
    ║  • Complete health monitoring                               ║
    ║  • Configuration validation                                 ║
    ║  • Archive coverage analysis                                ║
    ║  • Template management                                      ║
    ║  • Error log monitoring                                     ║
    ║  • Makefile compliance                                      ║
    ║  • Build and deployment tools                               ║
    ║                                                              ║
    ║  Everything you need for confidence in your IOCs!           ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    print("Checking requirements...")
    if not check_requirements():
        return 1

    print("Starting IOC IDE...")

    try:
        from ioc_ide import main as run_ide
        return run_ide()
    except Exception as e:
        print(f"\nError launching IDE: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())