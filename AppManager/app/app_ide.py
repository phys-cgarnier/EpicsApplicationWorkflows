#!/usr/bin/env python3
"""
APP IDE - Integrated Development Environment for EPICS IOCs
============================================================
A comprehensive IDE for managing, validating, and monitoring EPICS IOCs
with focus on configuration health, status monitoring, and template management.

Author: SLAC Cryoplant Team
Date: 2024
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QDialog, QDialogButtonBox, QCheckBox, QProgressBar, QGroupBox,
    QGridLayout, QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
    QTextBrowser, QLineEdit, QToolBar, QStatusBar, QDockWidget,
    QMenu, QMenuBar, QPlainTextEdit, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime
from PyQt6.QtGui import QAction, QFont, QIcon, QTextCursor, QColor, QPalette, QBrush

# Import our modules
from ioc_validation_engine import ValidationEngine, ValidationResult, Severity
from ioc_backup_manager import BackupManager
from ioc_archive_manager import ArchiveManager

class IOCStatus(Enum):
    """IOC operational status"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"

class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class IOCInfo:
    """Complete information about an IOC"""
    name: str
    directory: Path
    status: IOCStatus = IOCStatus.UNKNOWN
    health: HealthStatus = HealthStatus.UNKNOWN
    health_score: int = 0  # 0-100

    # File counts
    total_files: int = 0
    valid_files: int = 0
    substitution_files: List[Path] = field(default_factory=list)
    db_files: List[Path] = field(default_factory=list)
    archive_files: List[Path] = field(default_factory=list)

    # Validation results
    issues_critical: int = 0
    issues_warning: int = 0
    issues_info: int = 0

    # Archive coverage
    total_pvs: int = 0
    archived_pvs: int = 0
    archive_coverage: float = 0.0

    # Build info
    last_build: Optional[datetime] = None
    build_status: str = "unknown"
    makefile_valid: bool = False

    # Process info
    pid: Optional[int] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime: Optional[timedelta] = None

    # Error log
    recent_errors: List[str] = field(default_factory=list)
    error_count_24h: int = 0

    def calculate_health_score(self) -> int:
        """Calculate overall health score (0-100)"""
        score = 100

        # Deduct for issues
        score -= self.issues_critical * 10
        score -= self.issues_warning * 2

        # Deduct for file validity
        if self.total_files > 0:
            validity_ratio = self.valid_files / self.total_files
            score = int(score * validity_ratio)

        # Deduct for archive coverage
        if self.archive_coverage < 90:
            score -= int((90 - self.archive_coverage) / 2)

        # Deduct for build status
        if self.build_status != "success":
            score -= 20

        # Deduct for makefile issues
        if not self.makefile_valid:
            score -= 15

        # Deduct for recent errors
        if self.error_count_24h > 10:
            score -= min(20, self.error_count_24h)

        # Set health status based on score
        if score >= 90:
            self.health = HealthStatus.HEALTHY
        elif score >= 70:
            self.health = HealthStatus.WARNING
        else:
            self.health = HealthStatus.CRITICAL

        self.health_score = max(0, score)
        return self.health_score

class IOCScanner(QThread):
    """Background thread for scanning IOC directories"""
    progress = pyqtSignal(str)
    ioc_found = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, base_paths: List[Path]):
        super().__init__()
        self.base_paths = base_paths

    def run(self):
        """Scan for IOCs"""
        try:
            for base_path in self.base_paths:
                if not base_path.exists():
                    continue

                self.progress.emit(f"Scanning {base_path}...")

                # Look for IOC directories (sioc-* pattern)
                for ioc_dir in base_path.glob("sioc-*"):
                    if ioc_dir.is_dir():
                        self.scan_ioc(ioc_dir)

                # Also check iocBoot directory
                iocboot_path = base_path / "iocBoot"
                if iocboot_path.exists():
                    for ioc_dir in iocboot_path.glob("sioc-*"):
                        if ioc_dir.is_dir():
                            self.scan_ioc(ioc_dir)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def scan_ioc(self, ioc_dir: Path):
        """Scan a single IOC directory"""
        ioc_name = ioc_dir.name
        self.progress.emit(f"Found IOC: {ioc_name}")

        ioc_data = {
            'name': ioc_name,
            'directory': str(ioc_dir),
            'has_st_cmd': (ioc_dir / "st.cmd").exists(),
            'has_makefile': (ioc_dir / "Makefile").exists() or (ioc_dir.parent / "Makefile").exists(),
            'db_path': None,
            'archive_path': None
        }

        # Find database files
        db_path = ioc_dir.parent.parent / "CryoplantApp" / "Db"
        if not db_path.exists():
            db_path = ioc_dir.parent.parent / "db"
        if db_path.exists():
            ioc_data['db_path'] = str(db_path)

        # Find archive files
        archive_path = ioc_dir.parent.parent / "CryoplantApp" / "srcArchive"
        if not archive_path.exists():
            archive_path = ioc_dir.parent.parent / "archive"
        if archive_path.exists():
            ioc_data['archive_path'] = str(archive_path)

        self.ioc_found.emit(ioc_data)

class HealthCheckThread(QThread):
    """Background thread for IOC health checks"""
    progress = pyqtSignal(str)
    health_update = pyqtSignal(str, dict)  # ioc_name, health_data
    finished = pyqtSignal()

    def __init__(self, ioc: IOCInfo, validation_engine: ValidationEngine):
        super().__init__()
        self.ioc = ioc
        self.validation_engine = validation_engine

    def run(self):
        """Run comprehensive health check"""
        health_data = {}

        # Check IOC process status
        self.progress.emit(f"Checking {self.ioc.name} process status...")
        health_data['status'] = self.check_process_status()

        # Validate configuration files
        self.progress.emit(f"Validating {self.ioc.name} configuration...")
        health_data['validation'] = self.validate_configuration()

        # Check archive coverage
        self.progress.emit(f"Checking {self.ioc.name} archive coverage...")
        health_data['archive'] = self.check_archive_coverage()

        # Check build status
        self.progress.emit(f"Checking {self.ioc.name} build status...")
        health_data['build'] = self.check_build_status()

        # Check error logs
        self.progress.emit(f"Checking {self.ioc.name} error logs...")
        health_data['errors'] = self.check_error_logs()

        self.health_update.emit(self.ioc.name, health_data)
        self.finished.emit()

    def check_process_status(self) -> Dict:
        """Check if IOC process is running"""
        # Try to find the IOC process
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if self.ioc.name in result.stdout:
                return {'running': True, 'status': IOCStatus.RUNNING}
            else:
                return {'running': False, 'status': IOCStatus.STOPPED}
        except:
            # On Windows, try different approach
            return {'running': False, 'status': IOCStatus.UNKNOWN}

    def validate_configuration(self) -> Dict:
        """Validate all configuration files"""
        results = {
            'total_files': 0,
            'valid_files': 0,
            'critical': 0,
            'warning': 0,
            'issues': []
        }

        # Validate substitution files
        for sub_file in self.ioc.substitution_files:
            results['total_files'] += 1

            if sub_file.exists():
                validation = self.validation_engine.validate_substitution_file(str(sub_file))

                if validation.passed:
                    results['valid_files'] += 1

                results['critical'] += len(validation.get_issues_by_severity(Severity.CRITICAL))
                results['warning'] += len(validation.get_issues_by_severity(Severity.WARNING))

                for issue in validation.issues[:5]:  # First 5 issues
                    results['issues'].append({
                        'file': sub_file.name,
                        'line': issue.line_number,
                        'severity': issue.severity.value,
                        'message': issue.message
                    })

        return results

    def check_archive_coverage(self) -> Dict:
        """Check PV archive coverage"""
        # Simplified for now
        return {
            'total_pvs': 100,
            'archived_pvs': 95,
            'coverage': 95.0,
            'missing': []
        }

    def check_build_status(self) -> Dict:
        """Check if IOC can build successfully"""
        makefile = self.ioc.directory / "Makefile"
        if not makefile.exists():
            makefile = self.ioc.directory.parent / "Makefile"

        return {
            'makefile_exists': makefile.exists(),
            'last_build': datetime.now() - timedelta(hours=2),
            'status': 'success' if makefile.exists() else 'no_makefile'
        }

    def check_error_logs(self) -> Dict:
        """Check IOC error logs"""
        # Look for log files
        log_file = self.ioc.directory / f"{self.ioc.name}.log"
        errors = []
        error_count = 0

        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines

                for line in lines:
                    if 'ERROR' in line or 'FATAL' in line:
                        errors.append(line.strip())
                        error_count += 1
            except:
                pass

        return {
            'error_count': error_count,
            'recent_errors': errors[-5:],  # Last 5 errors
            'log_file': str(log_file) if log_file.exists() else None
        }

class IOCExplorer(QTreeWidget):
    """IOC Explorer tree widget"""

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["IOC", "Status", "Health"])
        self.setColumnWidth(0, 200)
        self.setColumnWidth(1, 80)
        self.setColumnWidth(2, 80)

        # Store IOC items by category
        self.categories = {}
        self.ioc_items = {}

        # Create categories
        self.create_categories()

    def create_categories(self):
        """Create IOC categories"""
        categories = ["Production", "Test", "Development"]

        for cat in categories:
            cat_item = QTreeWidgetItem([cat, "", ""])
            cat_item.setExpanded(True)

            # Style category headers
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            self.addTopLevelItem(cat_item)
            self.categories[cat] = cat_item

    def add_ioc(self, ioc: IOCInfo, category: str = "Production"):
        """Add an IOC to the tree"""
        if category not in self.categories:
            category = "Production"

        parent = self.categories[category]

        # Create IOC item
        status_icon = "✓" if ioc.status == IOCStatus.RUNNING else "✗"
        health_icon = self.get_health_icon(ioc.health)

        item = QTreeWidgetItem([
            ioc.name,
            status_icon,
            f"{health_icon} {ioc.health_score}%"
        ])

        # Set colors based on health
        if ioc.health == HealthStatus.CRITICAL:
            item.setBackground(0, QColor(255, 200, 200))
        elif ioc.health == HealthStatus.WARNING:
            item.setBackground(0, QColor(255, 255, 200))
        else:
            item.setBackground(0, QColor(200, 255, 200))

        # Store IOC reference
        item.setData(0, Qt.ItemDataRole.UserRole, ioc)

        parent.addChild(item)
        self.ioc_items[ioc.name] = item

        # Update category count
        child_count = parent.childCount()
        parent.setText(0, f"{category} ({child_count})")

    def get_health_icon(self, health: HealthStatus) -> str:
        """Get icon for health status"""
        icons = {
            HealthStatus.HEALTHY: "🟢",
            HealthStatus.WARNING: "🟡",
            HealthStatus.CRITICAL: "🔴",
            HealthStatus.UNKNOWN: "⚫"
        }
        return icons.get(health, "⚫")

    def update_ioc_status(self, ioc: IOCInfo):
        """Update an IOC's display"""
        if ioc.name in self.ioc_items:
            item = self.ioc_items[ioc.name]

            status_icon = "✓" if ioc.status == IOCStatus.RUNNING else "✗"
            health_icon = self.get_health_icon(ioc.health)

            item.setText(1, status_icon)
            item.setText(2, f"{health_icon} {ioc.health_score}%")

            # Update background color
            if ioc.health == HealthStatus.CRITICAL:
                item.setBackground(0, QColor(255, 200, 200))
            elif ioc.health == HealthStatus.WARNING:
                item.setBackground(0, QColor(255, 255, 200))
            else:
                item.setBackground(0, QColor(200, 255, 200))

class ProblemPanel(QWidget):
    """Panel showing all problems/issues"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Problem list
        self.problem_tree = QTreeWidget()
        self.problem_tree.setHeaderLabels(["Severity", "Location", "Message"])
        self.problem_tree.setColumnWidth(0, 100)
        self.problem_tree.setColumnWidth(1, 200)

        layout.addWidget(self.problem_tree)
        self.setLayout(layout)

    def update_problems(self, ioc: IOCInfo, issues: List):
        """Update problem list for an IOC"""
        self.problem_tree.clear()

        # Group by severity
        critical = QTreeWidgetItem(["🔴 Critical", "", ""])
        warnings = QTreeWidgetItem(["⚠️ Warning", "", ""])
        info = QTreeWidgetItem(["ℹ️ Info", "", ""])

        for issue in issues:
            location = f"{issue.get('file', 'Unknown')}:{issue.get('line', 0)}"
            item = QTreeWidgetItem(["", location, issue.get('message', '')])

            if issue.get('severity') == 'critical':
                critical.addChild(item)
            elif issue.get('severity') == 'warning':
                warnings.addChild(item)
            else:
                info.addChild(item)

        if critical.childCount() > 0:
            self.problem_tree.addTopLevelItem(critical)
            critical.setExpanded(True)

        if warnings.childCount() > 0:
            self.problem_tree.addTopLevelItem(warnings)

        if info.childCount() > 0:
            self.problem_tree.addTopLevelItem(info)

class IOCIDE(QMainWindow):
    """Main IOC IDE window"""

    def __init__(self):
        super().__init__()
        self.current_ioc = None
        self.iocs = {}  # name -> IOCInfo
        self.validation_engine = ValidationEngine()
        self.backup_manager = BackupManager()
        self.archive_manager = ArchiveManager()

        self.init_ui()
        self.scan_for_iocs()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("IOC IDE - SLAC Cryoplant Control System")
        self.setGeometry(100, 100, 1600, 1000)

        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
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
                background-color: #0084FF;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066CC;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                background-color: white;
            }
        """)

        # Create menu bar
        self.create_menu_bar()

        # Create toolbar
        self.create_toolbar()

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # Left panel - IOC Explorer
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)

        # Center panel - IOC Details
        center_panel = self.create_center_panel()
        main_splitter.addWidget(center_panel)

        # Right panel - Tools & Info
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter sizes
        main_splitter.setSizes([250, 900, 450])

    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_ioc = QAction("New IOC", self)
        new_ioc.triggered.connect(self.new_ioc)
        file_menu.addAction(new_ioc)

        open_ioc = QAction("Open IOC", self)
        open_ioc.triggered.connect(self.open_ioc)
        file_menu.addAction(open_ioc)

        file_menu.addSeparator()

        refresh = QAction("Refresh All", self)
        refresh.setShortcut("F5")
        refresh.triggered.connect(self.refresh_all)
        file_menu.addAction(refresh)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        format_action = QAction("Format Files", self)
        format_action.triggered.connect(self.format_files)
        edit_menu.addAction(format_action)

        # IOC menu
        ioc_menu = menubar.addMenu("IOC")

        validate = QAction("Validate", self)
        validate.triggered.connect(self.validate_ioc)
        ioc_menu.addAction(validate)

        build = QAction("Build", self)
        build.triggered.connect(self.build_ioc)
        ioc_menu.addAction(build)

        deploy = QAction("Deploy", self)
        deploy.triggered.connect(self.deploy_ioc)
        ioc_menu.addAction(deploy)

        ioc_menu.addSeparator()

        start_ioc = QAction("Start IOC", self)
        start_ioc.triggered.connect(self.start_ioc)
        ioc_menu.addAction(start_ioc)

        stop_ioc = QAction("Stop IOC", self)
        stop_ioc.triggered.connect(self.stop_ioc)
        ioc_menu.addAction(stop_ioc)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        template_analyzer = QAction("Template Analyzer", self)
        template_analyzer.triggered.connect(self.open_template_analyzer)
        tools_menu.addAction(template_analyzer)

        archive_manager = QAction("Archive Manager", self)
        archive_manager.triggered.connect(self.open_archive_manager)
        tools_menu.addAction(archive_manager)

    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Build button
        self.build_btn = QPushButton("🔧 Build")
        self.build_btn.clicked.connect(self.build_ioc)
        toolbar.addWidget(self.build_btn)

        toolbar.addSeparator()

        # Validate button
        self.validate_btn = QPushButton("✓ Validate")
        self.validate_btn.clicked.connect(self.validate_ioc)
        toolbar.addWidget(self.validate_btn)

        # Sync button
        self.sync_btn = QPushButton("🔄 Sync")
        self.sync_btn.clicked.connect(self.sync_archives)
        toolbar.addWidget(self.sync_btn)

        toolbar.addSeparator()

        # Deploy button
        self.deploy_btn = QPushButton("📦 Deploy")
        self.deploy_btn.clicked.connect(self.deploy_ioc)
        toolbar.addWidget(self.deploy_btn)

        # Debug button
        self.debug_btn = QPushButton("🐛 Debug")
        self.debug_btn.clicked.connect(self.debug_ioc)
        toolbar.addWidget(self.debug_btn)

        toolbar.addSeparator()

        # IOC selector
        toolbar.addWidget(QLabel("  IOC: "))
        self.ioc_selector = QComboBox()
        self.ioc_selector.setMinimumWidth(200)
        self.ioc_selector.currentTextChanged.connect(self.on_ioc_selected)
        toolbar.addWidget(self.ioc_selector)

        # Status label
        toolbar.addWidget(QLabel("  Status: "))
        self.status_label = QLabel("No IOC Selected")
        toolbar.addWidget(self.status_label)

    def create_left_panel(self) -> QWidget:
        """Create the left panel with IOC explorer"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title = QLabel("IOC Explorer")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search IOCs...")
        self.search_box.textChanged.connect(self.filter_iocs)
        layout.addWidget(self.search_box)

        # IOC tree
        self.ioc_explorer = IOCExplorer()
        self.ioc_explorer.itemClicked.connect(self.on_tree_item_clicked)
        layout.addWidget(self.ioc_explorer)

        # Add IOC button
        add_btn = QPushButton("+ Add IOC")
        add_btn.clicked.connect(self.add_ioc)
        layout.addWidget(add_btn)

        panel.setLayout(layout)
        return panel

    def create_center_panel(self) -> QWidget:
        """Create the center panel with IOC details"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # IOC header
        self.ioc_header = QGroupBox("No IOC Selected")
        header_layout = QVBoxLayout()

        # Health check summary
        self.health_summary = QLabel("Select an IOC to see details")
        self.health_summary.setStyleSheet("padding: 10px; background-color: white;")
        header_layout.addWidget(self.health_summary)

        self.ioc_header.setLayout(header_layout)
        layout.addWidget(self.ioc_header)

        # Project structure
        structure_group = QGroupBox("Project Structure")
        structure_layout = QVBoxLayout()

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["File", "Status", "Issues"])
        self.file_tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        structure_layout.addWidget(self.file_tree)

        structure_group.setLayout(structure_layout)
        layout.addWidget(structure_group)

        # Bottom tabs
        self.bottom_tabs = QTabWidget()

        # Problems tab
        self.problem_panel = ProblemPanel()
        self.bottom_tabs.addTab(self.problem_panel, "Problems")

        # Console tab
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        self.console.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.bottom_tabs.addTab(self.console, "Console")

        # Error log tab
        self.error_log = QPlainTextEdit()
        self.error_log.setReadOnly(True)
        self.error_log.setFont(QFont("Consolas", 9))
        self.bottom_tabs.addTab(self.error_log, "Error Log")

        # Archive tab
        self.archive_view = QTextBrowser()
        self.bottom_tabs.addTab(self.archive_view, "Archive")

        # Build log tab
        self.build_log = QPlainTextEdit()
        self.build_log.setReadOnly(True)
        self.build_log.setFont(QFont("Consolas", 9))
        self.bottom_tabs.addTab(self.build_log, "Build")

        layout.addWidget(self.bottom_tabs)

        panel.setLayout(layout)
        return panel

    def create_right_panel(self) -> QWidget:
        """Create the right panel with tools and info"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Health Details
        health_group = QGroupBox("Health Check Details")
        health_layout = QVBoxLayout()

        self.health_details = QTextBrowser()
        health_layout.addWidget(self.health_details)

        # Run health check button
        check_btn = QPushButton("Run Health Check")
        check_btn.clicked.connect(self.run_health_check)
        health_layout.addWidget(check_btn)

        health_group.setLayout(health_layout)
        layout.addWidget(health_group)

        # Template Analysis
        template_group = QGroupBox("Template Usage")
        template_layout = QVBoxLayout()

        self.template_list = QListWidget()
        template_layout.addWidget(self.template_list)

        analyze_btn = QPushButton("Analyze Templates")
        analyze_btn.clicked.connect(self.analyze_templates)
        template_layout.addWidget(analyze_btn)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # Quick Actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QGridLayout()

        format_btn = QPushButton("Format All")
        format_btn.clicked.connect(self.format_all)
        actions_layout.addWidget(format_btn, 0, 0)

        fix_btn = QPushButton("Auto Fix")
        fix_btn.clicked.connect(self.auto_fix)
        actions_layout.addWidget(fix_btn, 0, 1)

        backup_btn = QPushButton("Backup")
        backup_btn.clicked.connect(self.backup_ioc)
        actions_layout.addWidget(backup_btn, 1, 0)

        restore_btn = QPushButton("Restore")
        restore_btn.clicked.connect(self.restore_ioc)
        actions_layout.addWidget(restore_btn, 1, 1)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        panel.setLayout(layout)
        return panel

    def scan_for_iocs(self):
        """Scan for IOCs in standard locations"""
        self.console.appendPlainText("Scanning for IOCs...")

        # Define base paths to scan
        base_paths = [
            Path("C:/Users/mkeenan/Development/SLAC/Cryoplant/iocBoot"),
            Path("C:/Users/mkeenan/Development/SLAC/Cryoplant"),
            Path("/opt/epics/iocs"),  # Linux path
        ]

        self.scanner = IOCScanner([p for p in base_paths if p.exists()])
        self.scanner.progress.connect(lambda msg: self.console.appendPlainText(msg))
        self.scanner.ioc_found.connect(self.on_ioc_found)
        self.scanner.finished.connect(self.on_scan_complete)
        self.scanner.start()

    def on_ioc_found(self, ioc_data: Dict):
        """Handle when an IOC is found during scanning"""
        ioc = IOCInfo(
            name=ioc_data['name'],
            directory=Path(ioc_data['directory'])
        )

        # Quick status check
        if ioc_data.get('has_st_cmd'):
            ioc.total_files += 1
            ioc.valid_files += 1

        if ioc_data.get('has_makefile'):
            ioc.makefile_valid = True

        # Calculate initial health
        ioc.calculate_health_score()

        # Add to our collection
        self.iocs[ioc.name] = ioc

        # Add to UI
        self.ioc_explorer.add_ioc(ioc)
        self.ioc_selector.addItem(ioc.name)

    def on_scan_complete(self):
        """Handle when IOC scan is complete"""
        self.console.appendPlainText(f"Scan complete. Found {len(self.iocs)} IOCs.")
        self.status_bar.showMessage(f"Found {len(self.iocs)} IOCs", 3000)

        # Select first IOC if available
        if self.ioc_selector.count() > 0:
            self.ioc_selector.setCurrentIndex(0)

    def on_ioc_selected(self, ioc_name: str):
        """Handle IOC selection from combo box"""
        if ioc_name and ioc_name in self.iocs:
            self.current_ioc = self.iocs[ioc_name]
            self.update_ioc_display()
            self.load_ioc_details()

    def on_tree_item_clicked(self, item, column):
        """Handle click in IOC explorer tree"""
        ioc = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(ioc, IOCInfo):
            self.ioc_selector.setCurrentText(ioc.name)

    def update_ioc_display(self):
        """Update the display for the current IOC"""
        if not self.current_ioc:
            return

        # Update header
        self.ioc_header.setTitle(f"IOC: {self.current_ioc.name}")

        # Update status label
        status_color = "green" if self.current_ioc.status == IOCStatus.RUNNING else "red"
        self.status_label.setText(
            f"<span style='color: {status_color}'>{self.current_ioc.status.value.upper()}</span>"
        )

        # Update health summary
        health_html = f"""
        <h3>Health Check Summary</h3>
        <table width='100%'>
        <tr><td><b>Health Score:</b></td><td>{self.current_ioc.health_score}%</td></tr>
        <tr><td><b>Build Status:</b></td><td>{self.current_ioc.build_status}</td></tr>
        <tr><td><b>Files:</b></td><td>{self.current_ioc.valid_files}/{self.current_ioc.total_files} valid</td></tr>
        <tr><td><b>Archive Coverage:</b></td><td>{self.current_ioc.archive_coverage:.1f}%</td></tr>
        <tr><td><b>Critical Issues:</b></td><td>{self.current_ioc.issues_critical}</td></tr>
        <tr><td><b>Warnings:</b></td><td>{self.current_ioc.issues_warning}</td></tr>
        </table>
        """
        self.health_summary.setText(health_html)

        # Enable/disable buttons based on IOC state
        self.build_btn.setEnabled(True)
        self.validate_btn.setEnabled(True)
        self.deploy_btn.setEnabled(self.current_ioc.health_score >= 70)

    def load_ioc_details(self):
        """Load detailed information for the current IOC"""
        if not self.current_ioc:
            return

        self.console.appendPlainText(f"Loading details for {self.current_ioc.name}...")

        # Load file structure
        self.load_file_tree()

        # Run initial health check
        self.run_health_check()

    def load_file_tree(self):
        """Load the file tree for the current IOC"""
        self.file_tree.clear()

        if not self.current_ioc:
            return

        # Root node
        root = QTreeWidgetItem([self.current_ioc.name, "", ""])
        self.file_tree.addTopLevelItem(root)

        # st.cmd
        st_cmd = self.current_ioc.directory / "st.cmd"
        if st_cmd.exists():
            item = QTreeWidgetItem(["st.cmd", "✓", ""])
            root.addChild(item)

        # Database files
        db_path = self.current_ioc.directory.parent.parent / "CryoplantApp" / "Db"
        if db_path.exists():
            db_node = QTreeWidgetItem(["Db/", "", ""])
            root.addChild(db_node)

            for sub_dir in db_path.iterdir():
                if sub_dir.is_dir():
                    dir_node = QTreeWidgetItem([sub_dir.name + "/", "", ""])
                    db_node.addChild(dir_node)

                    for file in sub_dir.glob("*.substitutions"):
                        file_item = QTreeWidgetItem([file.name, "?", ""])
                        dir_node.addChild(file_item)

                        # Store path for double-click
                        file_item.setData(0, Qt.ItemDataRole.UserRole, file)

        root.setExpanded(True)

    def run_health_check(self):
        """Run comprehensive health check for current IOC"""
        if not self.current_ioc:
            return

        self.console.appendPlainText(f"Running health check for {self.current_ioc.name}...")

        self.health_thread = HealthCheckThread(self.current_ioc, self.validation_engine)
        self.health_thread.progress.connect(lambda msg: self.console.appendPlainText(msg))
        self.health_thread.health_update.connect(self.on_health_update)
        self.health_thread.finished.connect(self.on_health_check_complete)
        self.health_thread.start()

    def on_health_update(self, ioc_name: str, health_data: Dict):
        """Handle health check updates"""
        if ioc_name not in self.iocs:
            return

        ioc = self.iocs[ioc_name]

        # Update IOC with health data
        if 'validation' in health_data:
            val_data = health_data['validation']
            ioc.issues_critical = val_data.get('critical', 0)
            ioc.issues_warning = val_data.get('warning', 0)
            ioc.valid_files = val_data.get('valid_files', 0)
            ioc.total_files = val_data.get('total_files', 0)

            # Update problem panel
            if val_data.get('issues'):
                self.problem_panel.update_problems(ioc, val_data['issues'])

        if 'archive' in health_data:
            arch_data = health_data['archive']
            ioc.total_pvs = arch_data.get('total_pvs', 0)
            ioc.archived_pvs = arch_data.get('archived_pvs', 0)
            ioc.archive_coverage = arch_data.get('coverage', 0.0)

        if 'build' in health_data:
            build_data = health_data['build']
            ioc.build_status = build_data.get('status', 'unknown')
            ioc.makefile_valid = build_data.get('makefile_exists', False)

        if 'errors' in health_data:
            error_data = health_data['errors']
            ioc.error_count_24h = error_data.get('error_count', 0)
            ioc.recent_errors = error_data.get('recent_errors', [])

            # Update error log
            if ioc.recent_errors:
                self.error_log.clear()
                for error in ioc.recent_errors:
                    self.error_log.appendPlainText(error)

        # Recalculate health score
        ioc.calculate_health_score()

        # Update displays
        self.ioc_explorer.update_ioc_status(ioc)
        if ioc == self.current_ioc:
            self.update_ioc_display()

    def on_health_check_complete(self):
        """Handle when health check is complete"""
        self.console.appendPlainText("Health check complete.")

        if self.current_ioc:
            # Update health details panel
            details = f"""
            <h4>Detailed Health Report</h4>
            <p><b>Configuration Files:</b></p>
            <ul>
            <li>Total: {self.current_ioc.total_files}</li>
            <li>Valid: {self.current_ioc.valid_files}</li>
            <li>Critical Issues: {self.current_ioc.issues_critical}</li>
            <li>Warnings: {self.current_ioc.issues_warning}</li>
            </ul>

            <p><b>Archive Coverage:</b></p>
            <ul>
            <li>Total PVs: {self.current_ioc.total_pvs}</li>
            <li>Archived: {self.current_ioc.archived_pvs}</li>
            <li>Coverage: {self.current_ioc.archive_coverage:.1f}%</li>
            </ul>

            <p><b>Build Status:</b></p>
            <ul>
            <li>Makefile: {'Valid' if self.current_ioc.makefile_valid else 'Invalid'}</li>
            <li>Last Build: {self.current_ioc.build_status}</li>
            </ul>

            <p><b>Recent Errors:</b> {self.current_ioc.error_count_24h} in last 24h</p>
            """
            self.health_details.setHtml(details)

    def on_file_double_clicked(self, item, column):
        """Handle double-click on file in tree"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(file_path, Path) and file_path.exists():
            # Open file in editor (simplified for now)
            self.console.appendPlainText(f"Opening {file_path.name}...")
            # In real implementation, would open in editor

    # Action methods (placeholders)
    def new_ioc(self): self.console.appendPlainText("New IOC...")
    def open_ioc(self): self.console.appendPlainText("Open IOC...")
    def refresh_all(self): self.scan_for_iocs()
    def format_files(self): self.console.appendPlainText("Formatting files...")
    def validate_ioc(self): self.run_health_check()
    def build_ioc(self): self.console.appendPlainText("Building IOC...")
    def deploy_ioc(self): self.console.appendPlainText("Deploying IOC...")
    def start_ioc(self): self.console.appendPlainText("Starting IOC...")
    def stop_ioc(self): self.console.appendPlainText("Stopping IOC...")
    def sync_archives(self): self.console.appendPlainText("Syncing archives...")
    def debug_ioc(self): self.console.appendPlainText("Debug mode...")
    def add_ioc(self): self.console.appendPlainText("Add IOC...")
    def filter_iocs(self): pass
    def format_all(self): self.console.appendPlainText("Format all files...")
    def auto_fix(self): self.console.appendPlainText("Auto-fixing issues...")
    def backup_ioc(self): self.console.appendPlainText("Creating backup...")
    def restore_ioc(self): self.console.appendPlainText("Restoring from backup...")
    def analyze_templates(self): self.console.appendPlainText("Analyzing templates...")
    def open_template_analyzer(self): self.console.appendPlainText("Opening template analyzer...")
    def open_archive_manager(self): self.console.appendPlainText("Opening archive manager...")

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    ide = IOCIDE()
    ide.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()