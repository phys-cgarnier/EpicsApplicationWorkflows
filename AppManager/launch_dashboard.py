#!/usr/bin/env python3
"""
Launch script for IOC Dashboard
"""

import sys
import os
from pathlib import Path

# Add the ioc_manager directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Check for PyQt6
try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:
    print("Error: PyQt6 is required but not installed.")
    print("Please install it using: pip install PyQt6")
    sys.exit(1)

# Import and launch the dashboard
try:
    from ioc_dashboard import IOCDashboard

    app = QApplication(sys.argv)
    app.setApplicationName("EPICS IOC Manager")

    # Set default path if running from Cryoplant directory
    dashboard = IOCDashboard()

    # Auto-open if in Cryoplant directory
    cryoplant_path = Path(__file__).parent.parent.parent / "CryoplantApp"
    if cryoplant_path.exists():
        dashboard.current_path = cryoplant_path
        dashboard.path_label.setText(f"Path: {cryoplant_path}")
        dashboard.scan_system()

    dashboard.show()
    sys.exit(app.exec())

except Exception as e:
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Launch Error", f"Failed to launch dashboard:\n{str(e)}")
    sys.exit(1)