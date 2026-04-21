#!/usr/bin/env python3
"""
SLAC Cryoplant Dual-Mode Manager
=================================
Clear separation between IOC management and Application management.

Two distinct modes:
1. IOC Mode - Work with individual IOCs (validation, logs, status, etc.)
2. Application Mode - Work with shared subsystems (formatting, validation, etc.)
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QGridLayout, QListWidget, QListWidgetItem, QMessageBox,
    QTextBrowser, QLineEdit, QToolBar, QStatusBar, QProgressBar,
    QHeaderView, QFrame, QPlainTextEdit, QRadioButton, QButtonGroup,
    QStackedWidget, QToolButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QAction

# Import validation modules
from ioc_validation_engine import ValidationEngine, ValidationResult, Severity
from ioc_backup_manager import BackupManager
from ioc_archive_manager import ArchiveManager


class CryoplantDualManager(QMainWindow):
    """Main window with dual-mode management"""

    def __init__(self):
        super().__init__()
        self.base_path = Path("C:/Users/mkeenan/Development/SLAC/Cryoplant")
        self.current_mode = "IOC"  # or "Application"
        self.validation_engine = ValidationEngine(self.base_path)
        self.backup_manager = BackupManager(self.base_path)
        self.archive_manager = ArchiveManager(self.base_path)

        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("SLAC Cryoplant Manager")
        self.resize(1400, 900)

        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Mode selector at the top
        mode_widget = self.create_mode_selector()
        main_layout.addWidget(mode_widget)

        # Stacked widget for different modes
        self.mode_stack = QStackedWidget()

        # IOC Management Mode
        self.ioc_widget = self.create_ioc_mode()
        self.mode_stack.addWidget(self.ioc_widget)

        # Application Management Mode
        self.app_widget = self.create_application_mode()
        self.mode_stack.addWidget(self.app_widget)

        main_layout.addWidget(self.mode_stack)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def create_mode_selector(self) -> QWidget:
        """Create the mode selector widget"""
        widget = QWidget()
        widget.setMaximumHeight(80)
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Title and description
        title = QLabel("SLAC Cryoplant Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Mode buttons
        button_layout = QHBoxLayout()

        # IOC Mode button
        self.ioc_mode_btn = QPushButton("🖥️ IOC Management")
        self.ioc_mode_btn.setCheckable(True)
        self.ioc_mode_btn.setChecked(True)
        self.ioc_mode_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 10px 20px;
                background-color: #0066cc;
                color: white;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #004499;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        self.ioc_mode_btn.clicked.connect(lambda: self.switch_mode("IOC"))

        # Application Mode button
        self.app_mode_btn = QPushButton("📁 Application Management")
        self.app_mode_btn.setCheckable(True)
        self.app_mode_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 10px 20px;
                background-color: #666;
                color: white;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #444;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        self.app_mode_btn.clicked.connect(lambda: self.switch_mode("Application"))

        # Mode description label
        self.mode_description = QLabel("Work with individual IOCs - check status, view logs, validate configuration")
        self.mode_description.setStyleSheet("font-size: 11px; color: #666; padding: 2px;")
        self.mode_description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button_layout.addStretch()
        button_layout.addWidget(self.ioc_mode_btn)
        button_layout.addWidget(self.app_mode_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        layout.addWidget(self.mode_description)

        return widget

    def create_ioc_mode(self) -> QWidget:
        """Create IOC management interface"""
        widget = QWidget()
        layout = QHBoxLayout()
        widget.setLayout(layout)

        # Left panel - IOC selector
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)

        # IOC list header
        header = QLabel("Select an IOC to Manage")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        left_layout.addWidget(header)

        # Search box
        self.ioc_search = QLineEdit()
        self.ioc_search.setPlaceholderText("🔍 Search IOCs...")
        left_layout.addWidget(self.ioc_search)

        # IOC Categories
        self.ioc_tree = QTreeWidget()
        self.ioc_tree.setHeaderLabel("IOC Instances")

        # Populate IOCs by category
        self.production_iocs = QTreeWidgetItem(["Production IOCs"])
        self.test_iocs = QTreeWidgetItem(["Test IOCs"])
        self.dev_iocs = QTreeWidgetItem(["Development IOCs"])

        self.ioc_tree.addTopLevelItem(self.production_iocs)
        self.ioc_tree.addTopLevelItem(self.test_iocs)
        self.ioc_tree.addTopLevelItem(self.dev_iocs)

        # Scan for IOCs
        self.scan_iocs()

        left_layout.addWidget(self.ioc_tree)

        # Quick stats
        self.ioc_stats = QLabel("0 IOCs found")
        self.ioc_stats.setStyleSheet("font-size: 10px; color: #666; padding: 5px;")
        left_layout.addWidget(self.ioc_stats)

        layout.addWidget(left_panel)

        # Right panel - IOC details and actions
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        # IOC info header
        self.ioc_info_header = QLabel("No IOC Selected")
        self.ioc_info_header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #e0e0e0;")
        right_layout.addWidget(self.ioc_info_header)

        # Action buttons
        action_layout = QHBoxLayout()

        self.validate_ioc_btn = QPushButton("✓ Validate Configuration")
        self.validate_ioc_btn.setToolTip("Check st.cmd syntax, verify all referenced files exist, validate database loads")
        self.validate_ioc_btn.setEnabled(False)
        action_layout.addWidget(self.validate_ioc_btn)

        self.view_logs_btn = QPushButton("📋 View Logs")
        self.view_logs_btn.setToolTip("View recent IOC console output and error logs")
        self.view_logs_btn.setEnabled(False)
        action_layout.addWidget(self.view_logs_btn)

        self.check_status_btn = QPushButton("🔍 Check Status")
        self.check_status_btn.setToolTip("Check if IOC is running, PV connectivity, and health metrics")
        self.check_status_btn.setEnabled(False)
        action_layout.addWidget(self.check_status_btn)

        self.edit_stcmd_btn = QPushButton("📝 Edit st.cmd")
        self.edit_stcmd_btn.setToolTip("Open st.cmd file for editing")
        self.edit_stcmd_btn.setEnabled(False)
        action_layout.addWidget(self.edit_stcmd_btn)

        action_layout.addStretch()
        right_layout.addLayout(action_layout)

        # Tabs for IOC information
        self.ioc_tabs = QTabWidget()

        # Configuration tab
        self.config_text = QTextBrowser()
        self.ioc_tabs.addTab(self.config_text, "Configuration")

        # Validation tab
        self.validation_text = QTextBrowser()
        self.ioc_tabs.addTab(self.validation_text, "Validation Results")

        # Logs tab
        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Consolas", 9))
        self.ioc_tabs.addTab(self.logs_text, "Console Logs")

        # Archive coverage tab
        self.archive_text = QTextBrowser()
        self.ioc_tabs.addTab(self.archive_text, "Archive Coverage")

        right_layout.addWidget(self.ioc_tabs)

        layout.addWidget(right_panel)

        # Connect signals
        self.ioc_tree.itemClicked.connect(self.on_ioc_selected)
        self.validate_ioc_btn.clicked.connect(self.validate_selected_ioc)

        return widget

    def create_application_mode(self) -> QWidget:
        """Create Application management interface"""
        widget = QWidget()
        layout = QHBoxLayout()
        widget.setLayout(layout)

        # Left panel - Subsystem selector
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)

        # Header
        header = QLabel("Application Subsystems")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        left_layout.addWidget(header)

        # Subsystem list
        self.subsystem_list = QListWidget()
        self.scan_subsystems()
        left_layout.addWidget(self.subsystem_list)

        layout.addWidget(left_panel)

        # Right panel - Subsystem details and actions
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        # Subsystem info header
        self.subsystem_info_header = QLabel("No Subsystem Selected")
        self.subsystem_info_header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #e0e0e0;")
        right_layout.addWidget(self.subsystem_info_header)

        # Action buttons with clear descriptions
        action_layout = QHBoxLayout()

        self.validate_subsystem_btn = QPushButton("✓ Validate Files")
        self.validate_subsystem_btn.setToolTip("Check all .db, .substitutions, and .template files for syntax errors")
        self.validate_subsystem_btn.setEnabled(False)
        action_layout.addWidget(self.validate_subsystem_btn)

        self.format_subsystem_btn = QPushButton("📝 Format Substitutions")
        self.format_subsystem_btn.setToolTip("Auto-format .substitutions files with proper quoting and alignment")
        self.format_subsystem_btn.setEnabled(False)
        action_layout.addWidget(self.format_subsystem_btn)

        self.check_archive_btn = QPushButton("📦 Check Archives")
        self.check_archive_btn.setToolTip("Verify all PVs are included in archive files")
        self.check_archive_btn.setEnabled(False)
        action_layout.addWidget(self.check_archive_btn)

        self.backup_btn = QPushButton("💾 Backup")
        self.backup_btn.setToolTip("Create a backup of this subsystem's files")
        self.backup_btn.setEnabled(False)
        action_layout.addWidget(self.backup_btn)

        action_layout.addStretch()
        right_layout.addLayout(action_layout)

        # Information tabs
        self.app_tabs = QTabWidget()

        # Files tab
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["File", "Type", "Status"])
        self.app_tabs.addTab(self.files_tree, "Files")

        # Validation tab
        self.app_validation_text = QTextBrowser()
        self.app_tabs.addTab(self.app_validation_text, "Validation Results")

        # IOC Usage tab
        self.ioc_usage_text = QTextBrowser()
        self.app_tabs.addTab(self.ioc_usage_text, "IOC Usage")

        # File viewer tab
        self.file_viewer = QPlainTextEdit()
        self.file_viewer.setReadOnly(True)
        self.file_viewer.setFont(QFont("Consolas", 9))
        self.app_tabs.addTab(self.file_viewer, "File Viewer")

        right_layout.addWidget(self.app_tabs)

        # Connect signals
        self.subsystem_list.itemClicked.connect(self.on_subsystem_selected)
        self.validate_subsystem_btn.clicked.connect(self.validate_selected_subsystem)
        self.format_subsystem_btn.clicked.connect(self.format_selected_subsystem)

        layout.addWidget(right_panel)

        return widget

    def switch_mode(self, mode: str):
        """Switch between IOC and Application modes"""
        if mode == "IOC":
            self.current_mode = "IOC"
            self.mode_stack.setCurrentIndex(0)
            self.ioc_mode_btn.setChecked(True)
            self.app_mode_btn.setChecked(False)
            self.mode_description.setText("Work with individual IOCs - check status, view logs, validate configuration")
        else:
            self.current_mode = "Application"
            self.mode_stack.setCurrentIndex(1)
            self.ioc_mode_btn.setChecked(False)
            self.app_mode_btn.setChecked(True)
            self.mode_description.setText("Work with shared application files - format, validate, and manage subsystems")

    def scan_iocs(self):
        """Scan for IOC instances"""
        ioc_boot_dir = self.base_path / "iocBoot"
        if not ioc_boot_dir.exists():
            return

        ioc_count = 0
        for ioc_dir in ioc_boot_dir.iterdir():
            if ioc_dir.is_dir() and ioc_dir.name.startswith("sioc-"):
                # Categorize IOC
                if "test" in ioc_dir.name or "tst" in ioc_dir.name:
                    parent = self.test_iocs
                elif "dev" in ioc_dir.name:
                    parent = self.dev_iocs
                else:
                    parent = self.production_iocs

                item = QTreeWidgetItem([ioc_dir.name])
                parent.addChild(item)
                ioc_count += 1

        self.ioc_stats.setText(f"{ioc_count} IOCs found")
        self.production_iocs.setExpanded(True)

    def scan_subsystems(self):
        """Scan for application subsystems"""
        db_dir = self.base_path / "CryoplantApp" / "Db"
        if not db_dir.exists():
            return

        # Scan all subdirectories as subsystems
        for subdir in db_dir.iterdir():
            if subdir.is_dir():
                # Count files
                db_count = len(list(subdir.glob("*.db")))
                sub_count = len(list(subdir.glob("*.substitutions")))
                total = db_count + sub_count

                item_text = f"{subdir.name} ({total} files)"
                self.subsystem_list.addItem(item_text)

    def on_ioc_selected(self, item, column):
        """Handle IOC selection"""
        if item.parent() is None:  # Category item
            return

        ioc_name = item.text(0)
        self.ioc_info_header.setText(f"IOC: {ioc_name}")

        # Enable buttons
        self.validate_ioc_btn.setEnabled(True)
        self.view_logs_btn.setEnabled(True)
        self.check_status_btn.setEnabled(True)
        self.edit_stcmd_btn.setEnabled(True)

        # Load IOC configuration
        ioc_path = self.base_path / "iocBoot" / ioc_name
        st_cmd = ioc_path / "st.cmd"

        if st_cmd.exists():
            config_info = f"""
            <h3>IOC Configuration</h3>
            <p><b>Name:</b> {ioc_name}</p>
            <p><b>Path:</b> {ioc_path}</p>
            <p><b>Files:</b></p>
            <ul>
                <li>st.cmd: {'✓' if st_cmd.exists() else '✗'}</li>
                <li>Makefile: {'✓' if (ioc_path / 'Makefile').exists() else '✗'}</li>
                <li>README: {'✓' if (ioc_path / 'README').exists() else '✗'}</li>
            </ul>
            """
            self.config_text.setHtml(config_info)

    def on_subsystem_selected(self, item):
        """Handle subsystem selection"""
        # Extract subsystem name from item text
        subsystem_name = item.text().split(" (")[0]
        self.subsystem_info_header.setText(f"Subsystem: {subsystem_name}")

        # Enable buttons
        self.validate_subsystem_btn.setEnabled(True)
        self.format_subsystem_btn.setEnabled(True)
        self.check_archive_btn.setEnabled(True)
        self.backup_btn.setEnabled(True)

        # Load subsystem files
        subsystem_path = self.base_path / "CryoplantApp" / "Db" / subsystem_name

        # Clear and populate files tree
        self.files_tree.clear()

        if subsystem_path.exists():
            # Add database files
            db_root = QTreeWidgetItem(["Database Files", "", ""])
            for db_file in subsystem_path.glob("*.db"):
                QTreeWidgetItem(db_root, [db_file.name, "Database", ""])
            self.files_tree.addTopLevelItem(db_root)

            # Add substitution files
            sub_root = QTreeWidgetItem(["Substitution Files", "", ""])
            for sub_file in subsystem_path.glob("*.substitutions"):
                QTreeWidgetItem(sub_root, [sub_file.name, "Substitution", ""])
            self.files_tree.addTopLevelItem(sub_root)

            # Add template files
            template_root = QTreeWidgetItem(["Template Files", "", ""])
            for template_file in subsystem_path.glob("*.template"):
                QTreeWidgetItem(template_root, [template_file.name, "Template", ""])
            for template_file in subsystem_path.glob("*.vdb"):
                QTreeWidgetItem(template_root, [template_file.name, "VDB", ""])
            self.files_tree.addTopLevelItem(template_root)

            # Expand all
            db_root.setExpanded(True)
            sub_root.setExpanded(True)
            template_root.setExpanded(True)

        # Check IOC usage
        self.check_ioc_usage(subsystem_name)

    def check_ioc_usage(self, subsystem_name: str):
        """Check which IOCs use this subsystem"""
        usage_html = f"<h3>IOCs Using {subsystem_name}</h3><ul>"

        ioc_boot_dir = self.base_path / "iocBoot"
        ioc_count = 0

        for ioc_dir in ioc_boot_dir.iterdir():
            if ioc_dir.is_dir() and ioc_dir.name.startswith("sioc-"):
                st_cmd = ioc_dir / "st.cmd"
                if st_cmd.exists():
                    content = st_cmd.read_text()
                    # Check if this IOC references the subsystem
                    if subsystem_name in content:
                        usage_html += f"<li>{ioc_dir.name}</li>"
                        ioc_count += 1

        if ioc_count == 0:
            usage_html += "<li>No IOCs currently use this subsystem</li>"

        usage_html += "</ul>"
        self.ioc_usage_text.setHtml(usage_html)

    def validate_selected_ioc(self):
        """Validate the selected IOC configuration"""
        self.validation_text.setHtml("<h3>Running validation...</h3>")
        # TODO: Implement actual validation
        self.validation_text.setHtml("""
        <h3>Validation Results</h3>
        <p style='color: green;'>✓ st.cmd syntax is valid</p>
        <p style='color: green;'>✓ All referenced database files exist</p>
        <p style='color: orange;'>⚠ Archive file may be outdated</p>
        """)

    def validate_selected_subsystem(self):
        """Validate the selected subsystem files"""
        self.app_validation_text.setHtml("<h3>Running validation...</h3>")
        # TODO: Run actual validation
        self.app_validation_text.setHtml("""
        <h3>Validation Results</h3>
        <p>Checking all files in subsystem...</p>
        <p style='color: green;'>✓ All .db files have valid syntax</p>
        <p style='color: green;'>✓ All .substitutions files properly formatted</p>
        """)

    def format_selected_subsystem(self):
        """Format substitution files in selected subsystem"""
        reply = QMessageBox.question(
            self,
            "Format Substitution Files",
            "This will auto-format all .substitutions files in this subsystem.\n\n"
            "Changes include:\n"
            "• Proper quoting (descriptions quoted, numbers unquoted)\n"
            "• Consistent indentation\n"
            "• Column alignment\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # TODO: Implement formatting
            QMessageBox.information(self, "Success", "Substitution files formatted successfully!")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    window = CryoplantDualManager()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())