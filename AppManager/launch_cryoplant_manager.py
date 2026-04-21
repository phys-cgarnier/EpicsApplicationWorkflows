#!/usr/bin/env python3
"""
Launch Cryoplant Manager
========================
"""

import sys
import os
from pathlib import Path

# Add to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

def main():
    print("""
    ═══════════════════════════════════════════════════════════════
                   Cryoplant EPICS Application Manager
    ═══════════════════════════════════════════════════════════════

    This tool understands your ACTUAL structure:

    • ONE Cryoplant application
    • MULTIPLE IOC instances (30+ in iocBoot/)
    • SHARED database files organized by subsystem
    • Each IOC's st.cmd determines what it loads

    Features:
    • See all subsystems (2kcb, 4kcb, wcmp, etc.)
    • See which IOCs use which subsystems
    • Validate application-level files
    • Validate each IOC's configuration
    • Understand dependencies from st.cmd

    Starting...
    """)

    try:
        from cryoplant_manager import main as run_manager
        return run_manager()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())