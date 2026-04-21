#!/usr/bin/env python3
"""
Launch Dual-Mode Manager
========================
Clear IOC vs Application management interface
"""

import sys
import os
from pathlib import Path

# Add to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║              SLAC Cryoplant Dual-Mode Manager                ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  Two Clear Modes:                                            ║
    ║                                                              ║
    ║  🖥️  IOC Management Mode:                                    ║
    ║     • Select an individual IOC to manage                    ║
    ║     • Validate IOC configuration (st.cmd, databases)        ║
    ║     • View console logs and error messages                  ║
    ║     • Check running status and PV connectivity              ║
    ║     • Edit st.cmd and other IOC-specific files             ║
    ║                                                              ║
    ║  📁 Application Management Mode:                             ║
    ║     • Work with shared subsystem files (2kcb, c1_2kcb...)  ║
    ║     • Validate all .db and .substitutions files            ║
    ║     • Auto-format substitution files with proper quoting   ║
    ║     • Check archive coverage for PVs                       ║
    ║     • See which IOCs use each subsystem                    ║
    ║     • Backup subsystem files                               ║
    ║                                                              ║
    ║  Clear separation - choose your task and go!                ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝

    Starting application...
    """)

    try:
        from dual_mode_manager import main as run_manager
        return run_manager()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())