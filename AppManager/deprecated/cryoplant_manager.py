#!/usr/bin/env python3
"""
Cryoplant EPICS Application Manager
====================================
Manages the entire Cryoplant EPICS application including:
- Application-level validation (Db files, templates, makefiles)
- IOC instance management (30+ IOCs in iocBoot/)
- Subsystem organization (2kcb, 4kcb, wcmp, etc.)
- Build validation and deployment readiness

Author: SLAC Cryoplant Team
Date: 2024
"""

import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QGridLayout, QListWidget, QListWidgetItem, QMessageBox,
    QTextBrowser, QLineEdit, QToolBar, QStatusBar, QProgressBar,
    QHeaderView, QFrame, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

# Import our validation modules
from ioc_validation_engine import ValidationEngine, ValidationResult, Severity
from ioc_backup_manager import BackupManager
from ioc_archive_manager import ArchiveManager

# Constants for the Cryoplant application structure
CRYOPLANT_ROOT = Path("C:/Users/mkeenan/Development/SLAC/Cryoplant")
IOCBOOT_DIR = CRYOPLANT_ROOT / "iocBoot"
CRYOPLANT_APP_DIR = CRYOPLANT_ROOT / "CryoplantApp"
DB_DIR = CRYOPLANT_APP_DIR / "Db"
ARCHIVE_DIR = CRYOPLANT_APP_DIR / "srcArchive"

@dataclass
class Subsystem:
    """Represents a subsystem (2kcb, 4kcb, etc.)"""
    name: str
    path: Path
    db_files: List[Path] = field(default_factory=list)
    substitution_files: List[Path] = field(default_factory=list)
    archive_files: List[Path] = field(default_factory=list)
    template_files: List[Path] = field(default_factory=list)

    # Validation results
    total_files: int = 0
    valid_files: int = 0
    issues: List[Dict] = field(default_factory=list)

    # Which IOCs use this subsystem
    used_by_iocs: Set[str] = field(default_factory=set)

@dataclass
class IOCInstance:
    """Represents a single IOC instance"""
    name: str
    path: Path
    has_st_cmd: bool = False
    has_makefile: bool = False
    has_readme: bool = False

    # What this IOC loads (parsed from st.cmd)
    loaded_dbs: List[str] = field(default_factory=list)
    loaded_substitutions: List[str] = field(default_factory=list)
    subsystems_used: Set[str] = field(default_factory=set)
    plc_connections: List[str] = field(default_factory=list)

    # Validation status
    st_cmd_valid: bool = False
    all_files_exist: bool = False
    makefile_valid: bool = False
    issues: List[str] = field(default_factory=list)

    # Runtime info
    is_test_ioc: bool = False
    is_production: bool = False
    description: str = ""

@dataclass
class CryoplantApplication:
    """The entire Cryoplant EPICS application"""
    root_path: Path = CRYOPLANT_ROOT
    subsystems: Dict[str, Subsystem] = field(default_factory=dict)
    ioc_instances: Dict[str, IOCInstance] = field(default_factory=dict)

    # Application-level info
    total_db_files: int = 0
    total_substitutions: int = 0
    total_iocs: int = 0
    build_status: str = "unknown"

    # Validation summary
    app_valid: bool = False
    app_issues: List[str] = field(default_factory=list)

class StCmdParser:
    """Parser for st.cmd files to understand IOC configuration"""

    @staticmethod
    def parse(st_cmd_path: Path) -> Dict[str, Any]:
        """Parse an st.cmd file to extract configuration"""
        result = {
            'loaded_dbs': [],
            'loaded_substitutions': [],
            'plc_connections': [],
            'environment_vars': {},
            'description': '',
            'is_test': False,
            'subsystems': set()
        }

        if not st_cmd_path.exists():
            return result

        try:
            with open(st_cmd_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            for line in lines:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#!'):
                    continue

                # Extract description from comments
                if line.startswith('#') and any(word in line.lower() for word in ['abs:', 'desc:', 'description']):
                    result['description'] = line.split(':', 1)[-1].strip()

                # Check if test IOC
                if 'test' in line.lower() and line.startswith('#'):
                    result['is_test'] = True

                # Parse dbLoadRecords
                if 'dbLoadRecords' in line:
                    match = re.search(r'dbLoadRecords\s*\(\s*"([^"]+)"', line)
                    if match:
                        db_file = match.group(1)
                        result['loaded_dbs'].append(db_file)

                        # Extract subsystem from database filename
                        # Look for patterns like c1_2kcb_*, 2kcb_*, c2_wcmp_*, etc.
                        db_name = Path(db_file).stem

                        # Extract subsystem from the database filename
                        # Files are named like c1_2kcb_AIs.db, c2_wcmp_components.db, etc.
                        # The subsystem prefix is everything before the last underscore and type

                        # Match patterns like c1_2kcb, c2_wcmp, 2kcb, wcmp, etc.
                        subsystem_patterns = [
                            r'^(c[12]_2kcb)',     # c1_2kcb, c2_2kcb
                            r'^(c[12]_4kcb)',     # c1_4kcb, c2_4kcb
                            r'^(c[12]_wcmp)',     # c1_wcmp, c2_wcmp
                            r'^(c[12]_gmg[m]?t)', # c1_gmgt, c1_gmgmt, c2_gmgt, c2_gmgmt
                            r'^(2kcb)',           # plain 2kcb
                            r'^(4kcb)',           # plain 4kcb
                            r'^(wcmp)',           # plain wcmp
                            r'^(gmg[m]?t)',       # plain gmgt/gmgmt
                            r'^(psiq)',           # psiq
                            r'^(util)',           # util
                            r'^(cas)',            # cas
                            r'^(common)',         # common
                            r'^(integration)',    # integration
                        ]

                        for pattern in subsystem_patterns:
                            match = re.search(pattern, db_name, re.IGNORECASE)
                            if match:
                                subsystem = match.group(1).lower()
                                result['subsystems'].add(subsystem)
                                break

                # Parse dbLoadTemplate
                if 'dbLoadTemplate' in line:
                    match = re.search(r'dbLoadTemplate\s*\(\s*"([^"]+)"', line)
                    if match:
                        sub_file = match.group(1)
                        result['loaded_substitutions'].append(sub_file)

                        # Extract subsystem from substitution filename
                        sub_name = Path(sub_file).stem

                        # Use same pattern list as dbLoadRecords
                        for pattern in subsystem_patterns:
                            match2 = re.search(pattern, sub_name, re.IGNORECASE)
                            if match2:
                                subsystem = match2.group(1).lower()
                                result['subsystems'].add(subsystem)
                                break

                # Parse PLC connections (EtherIP)
                if 'drvEtherIP_define_PLC' in line:
                    match = re.search(r'"([^"]+)"\s*,\s*"([^"]+)"', line)
                    if match:
                        plc_name = match.group(1)
                        plc_ip = match.group(2)
                        result['plc_connections'].append(f"{plc_name} ({plc_ip})")

                # Parse environment variables
                if 'epicsEnvSet' in line:
                    match = re.search(r'epicsEnvSet\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', line)
                    if match:
                        var_name = match.group(1)
                        var_value = match.group(2)
                        result['environment_vars'][var_name] = var_value

        except Exception as e:
            print(f"Error parsing {st_cmd_path}: {e}")

        return result

class CryoplantScanner(QThread):
    """Background thread for scanning the Cryoplant application"""
    progress = pyqtSignal(str)
    subsystem_found = pyqtSignal(dict)
    ioc_found = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        """Scan the entire Cryoplant application"""
        try:
            # Scan subsystems in CryoplantApp/Db/
            self.progress.emit("Scanning subsystems in CryoplantApp/Db/...")
            if DB_DIR.exists():
                for subdir in DB_DIR.iterdir():
                    if subdir.is_dir():
                        self.scan_subsystem(subdir)

            # Scan IOC instances in iocBoot/
            self.progress.emit("Scanning IOC instances in iocBoot/...")
            if IOCBOOT_DIR.exists():
                for ioc_dir in IOCBOOT_DIR.iterdir():
                    if ioc_dir.is_dir() and ioc_dir.name.startswith('sioc-'):
                        self.scan_ioc(ioc_dir)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def scan_subsystem(self, subdir: Path):
        """Scan a subsystem directory"""
        subsystem_data = {
            'name': subdir.name,
            'path': str(subdir),
            'db_files': [],
            'substitution_files': [],
            'template_files': []
        }

        # Count files by type
        for file in subdir.iterdir():
            if file.is_file():
                if file.suffix == '.substitutions':
                    subsystem_data['substitution_files'].append(str(file))
                elif file.suffix == '.db':
                    subsystem_data['db_files'].append(str(file))
                elif file.suffix in ['.vdb', '.template']:
                    subsystem_data['template_files'].append(str(file))

        self.subsystem_found.emit(subsystem_data)

    def scan_ioc(self, ioc_dir: Path):
        """Scan an IOC instance directory"""
        ioc_data = {
            'name': ioc_dir.name,
            'path': str(ioc_dir),
            'has_st_cmd': (ioc_dir / 'st.cmd').exists(),
            'has_makefile': (ioc_dir / 'Makefile').exists(),
            'has_readme': (ioc_dir / 'README').exists()
        }

        # Parse st.cmd if it exists
        st_cmd_path = ioc_dir / 'st.cmd'
        if st_cmd_path.exists():
            parsed = StCmdParser.parse(st_cmd_path)
            ioc_data.update(parsed)

        self.ioc_found.emit(ioc_data)

class CryoplantValidator(QThread):
    """Background thread for validation"""
    progress = pyqtSignal(str)
    validation_update = pyqtSignal(str, dict)  # name, results
    finished = pyqtSignal()

    def __init__(self, app: CryoplantApplication, validation_engine: ValidationEngine):
        super().__init__()
        self.app = app
        self.validation_engine = validation_engine

    def run(self):
        """Run complete validation"""
        # Validate subsystems
        for name, subsystem in self.app.subsystems.items():
            self.progress.emit(f"Validating subsystem {name}...")
            self.validate_subsystem(subsystem)

        # Validate IOC instances
        for name, ioc in self.app.ioc_instances.items():
            self.progress.emit(f"Validating IOC {name}...")
            self.validate_ioc(ioc)

        self.finished.emit()

    def validate_subsystem(self, subsystem: Subsystem):
        """Validate a subsystem's files"""
        results = {
            'total': 0,
            'valid': 0,
            'issues': []
        }

        # Validate substitution files
        for sub_file in subsystem.substitution_files:
            results['total'] += 1
            validation = self.validation_engine.validate_substitution_file(str(sub_file))

            if validation.passed:
                results['valid'] += 1

            for issue in validation.issues[:3]:  # First 3 issues
                results['issues'].append({
                    'file': sub_file.name,
                    'severity': issue.severity.value,
                    'line': issue.line_number,
                    'message': issue.message
                })

        subsystem.total_files = results['total']
        subsystem.valid_files = results['valid']
        subsystem.issues = results['issues']

        self.validation_update.emit(subsystem.name, results)

    def validate_ioc(self, ioc: IOCInstance):
        """Validate an IOC instance"""
        issues = []

        # Check if all loaded files exist
        for db_file in ioc.loaded_dbs:
            if 'db/' in db_file:
                # Convert to actual path
                file_path = CRYOPLANT_APP_DIR / db_file.replace('db/', 'Db/')
                if not file_path.exists():
                    issues.append(f"Missing database: {db_file}")

        # Check makefile
        makefile = ioc.path / 'Makefile'
        if makefile.exists():
            # Simple check - could be more sophisticated
            with open(makefile, 'r') as f:
                content = f.read()
                if 'TOP' not in content:
                    issues.append("Makefile missing TOP definition")

        ioc.issues = issues
        ioc.all_files_exist = len(issues) == 0

        self.validation_update.emit(ioc.name, {'issues': issues})

class CryoplantManager(QMainWindow):
    """Main window for Cryoplant Application Manager"""

    def __init__(self):
        super().__init__()
        self.app = CryoplantApplication()
        self.validation_engine = ValidationEngine()
        self.backup_manager = BackupManager()
        self.archive_manager = ArchiveManager()

        self.init_ui()
        self.scan_application()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Cryoplant EPICS Application Manager")
        self.setGeometry(100, 100, 1400, 900)

        # Apply clean style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
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
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                background-color: white;
            }
        """)

        # Create menu bar
        self.create_menu_bar()

        # Create toolbar
        self.create_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Application header
        header = self.create_header()
        main_layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Application structure
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Center panel - Details and validation
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)

        # Right panel - IOC instances
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 600, 400])
        main_layout.addWidget(splitter)

    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        refresh_action = file_menu.addAction("Refresh")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.scan_application)

        # Validation menu
        val_menu = menubar.addMenu("Validation")

        val_all = val_menu.addAction("Validate Everything")
        val_all.triggered.connect(self.validate_all)

        val_subsystems = val_menu.addAction("Validate Subsystems")
        val_subsystems.triggered.connect(self.validate_subsystems)

        val_iocs = val_menu.addAction("Validate IOCs")
        val_iocs.triggered.connect(self.validate_iocs)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        format_action = tools_menu.addAction("Format Substitutions")
        format_action.triggered.connect(self.format_substitutions)

        archive_action = tools_menu.addAction("Check Archive Coverage")
        archive_action.triggered.connect(self.check_archive_coverage)

    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Validate button
        self.validate_btn = QPushButton("✓ Validate All")
        self.validate_btn.clicked.connect(self.validate_all)
        toolbar.addWidget(self.validate_btn)

        toolbar.addSeparator()

        # Build button
        self.build_btn = QPushButton("🔧 Build")
        self.build_btn.clicked.connect(self.build_application)
        toolbar.addWidget(self.build_btn)

        toolbar.addSeparator()

        # Format button
        self.format_btn = QPushButton("📝 Format")
        self.format_btn.clicked.connect(self.format_substitutions)
        toolbar.addWidget(self.format_btn)

        # Archive button
        self.archive_btn = QPushButton("📦 Archives")
        self.archive_btn.clicked.connect(self.check_archive_coverage)
        toolbar.addWidget(self.archive_btn)

    def create_header(self) -> QWidget:
        """Create compact application header with summary"""
        header = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)  # Reduce margins

        # Summary label - single line, compact
        self.summary_label = QLabel("Subsystems: 0 | IOCs: 0 | Files: 0 | Status: Scanning...")
        self.summary_label.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(self.summary_label)

        layout.addStretch()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setMaximumHeight(16)  # Make it smaller
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        header.setLayout(layout)
        header.setMaximumHeight(40)  # Limit the height
        return header

    def create_left_panel(self) -> QWidget:
        """Create left panel showing application structure"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Title
        title = QLabel("Application Structure")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Tree view
        self.app_tree = QTreeWidget()
        self.app_tree.setHeaderLabels(["Component", "Files", "Status"])
        self.app_tree.itemClicked.connect(self.on_tree_item_clicked)

        # Add root items
        self.subsystems_root = QTreeWidgetItem(["Subsystems", "", ""])
        self.app_tree.addTopLevelItem(self.subsystems_root)

        self.config_root = QTreeWidgetItem(["Configuration", "", ""])
        self.app_tree.addTopLevelItem(self.config_root)

        # Add config items
        QTreeWidgetItem(self.config_root, ["Makefile", "", ""])
        QTreeWidgetItem(self.config_root, ["configure/", "", ""])

        layout.addWidget(self.app_tree)

        panel.setLayout(layout)
        return panel

    def create_center_panel(self) -> QWidget:
        """Create center panel with details and validation"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Tabs
        self.center_tabs = QTabWidget()

        # Details tab
        self.details_text = QTextBrowser()
        self.center_tabs.addTab(self.details_text, "Details")

        # Validation tab
        self.validation_text = QTextBrowser()
        self.center_tabs.addTab(self.validation_text, "Validation")

        # Console tab
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        self.center_tabs.addTab(self.console, "Console")

        # File viewer tab
        self.file_viewer = QPlainTextEdit()
        self.file_viewer.setReadOnly(True)
        self.file_viewer.setFont(QFont("Consolas", 9))
        self.center_tabs.addTab(self.file_viewer, "File Viewer")

        layout.addWidget(self.center_tabs)

        panel.setLayout(layout)
        return panel

    def create_right_panel(self) -> QWidget:
        """Create right panel showing IOC instances"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Title
        title = QLabel("IOC Instances")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Filter container
        filter_container = QWidget()
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)

        # Filter status label
        self.filter_label = QLabel("Showing: All IOCs")
        self.filter_label.setStyleSheet("font-size: 10px; color: #666; padding: 2px;")
        filter_layout.addWidget(self.filter_label)

        # Clear filter button
        self.clear_filter_btn = QPushButton("Clear")
        self.clear_filter_btn.setMaximumHeight(20)
        self.clear_filter_btn.setMaximumWidth(50)
        self.clear_filter_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                padding: 2px 5px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.clear_filter_btn.clicked.connect(lambda: self.filter_ioc_list(None))
        self.clear_filter_btn.setVisible(False)  # Hidden by default
        filter_layout.addWidget(self.clear_filter_btn)

        filter_layout.addStretch()
        filter_container.setLayout(filter_layout)
        layout.addWidget(filter_container)

        # Search
        self.ioc_search = QLineEdit()
        self.ioc_search.setPlaceholderText("Search IOCs...")
        self.ioc_search.textChanged.connect(self.filter_iocs)
        layout.addWidget(self.ioc_search)

        # IOC list
        self.ioc_list = QListWidget()
        self.ioc_list.itemClicked.connect(self.on_ioc_selected)
        layout.addWidget(self.ioc_list)

        # IOC details
        self.ioc_details = QTextBrowser()
        self.ioc_details.setMaximumHeight(300)
        layout.addWidget(self.ioc_details)

        panel.setLayout(layout)
        return panel

    def scan_application(self):
        """Scan the Cryoplant application"""
        self.console.appendPlainText("Scanning Cryoplant application...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Clear current data
        self.app = CryoplantApplication()
        self.subsystems_root.takeChildren()
        self.ioc_list.clear()

        # Start scanner
        self.scanner = CryoplantScanner()
        self.scanner.progress.connect(lambda msg: self.console.appendPlainText(msg))
        self.scanner.subsystem_found.connect(self.on_subsystem_found)
        self.scanner.ioc_found.connect(self.on_ioc_found)
        self.scanner.finished.connect(self.on_scan_complete)
        self.scanner.start()

    def on_subsystem_found(self, data: Dict):
        """Handle subsystem discovery"""
        subsystem = Subsystem(
            name=data['name'],
            path=Path(data['path']),
            db_files=[Path(f) for f in data['db_files']],
            substitution_files=[Path(f) for f in data['substitution_files']],
            template_files=[Path(f) for f in data['template_files']]
        )

        subsystem.total_files = (len(subsystem.db_files) +
                                len(subsystem.substitution_files) +
                                len(subsystem.template_files))

        self.app.subsystems[subsystem.name] = subsystem

        # Add to tree
        item = QTreeWidgetItem([
            subsystem.name,
            str(subsystem.total_files),
            "?"
        ])
        self.subsystems_root.addChild(item)

    def on_ioc_found(self, data: Dict):
        """Handle IOC discovery"""
        ioc = IOCInstance(
            name=data['name'],
            path=Path(data['path']),
            has_st_cmd=data['has_st_cmd'],
            has_makefile=data['has_makefile'],
            has_readme=data['has_readme']
        )

        # Update from parsed st.cmd
        if 'loaded_dbs' in data:
            ioc.loaded_dbs = data['loaded_dbs']
            ioc.subsystems_used = data.get('subsystems', set())
            ioc.description = data.get('description', '')
            ioc.is_test_ioc = data.get('is_test', False)
            ioc.plc_connections = data.get('plc_connections', [])

        self.app.ioc_instances[ioc.name] = ioc

        # Add to list
        display_text = f"{ioc.name}"
        if ioc.is_test_ioc:
            display_text += " [TEST]"
        if ioc.subsystems_used:
            display_text += f" ({', '.join(ioc.subsystems_used)})"

        self.ioc_list.addItem(display_text)

        # Update subsystem usage
        for subsystem_name in ioc.subsystems_used:
            if subsystem_name in self.app.subsystems:
                self.app.subsystems[subsystem_name].used_by_iocs.add(ioc.name)

    def on_scan_complete(self):
        """Handle scan completion"""
        self.progress_bar.setVisible(False)

        # Update summary - compact single line
        total_files = sum(s.total_files for s in self.app.subsystems.values())
        self.summary_label.setText(
            f"Subsystems: {len(self.app.subsystems)} | "
            f"IOCs: {len(self.app.ioc_instances)} | "
            f"Files: {total_files} | "
            f"Status: Ready"
        )

        # Expand tree
        self.subsystems_root.setExpanded(True)

        self.console.appendPlainText(f"Scan complete: {len(self.app.subsystems)} subsystems, {len(self.app.ioc_instances)} IOCs")
        self.status_bar.showMessage("Scan complete", 3000)

    def on_tree_item_clicked(self, item, column):
        """Handle tree item click"""
        if item.parent() == self.subsystems_root:
            # Subsystem clicked
            subsystem_name = item.text(0)
            if subsystem_name in self.app.subsystems:
                self.show_subsystem_details(self.app.subsystems[subsystem_name])
                # Filter IOC list to show only IOCs using this subsystem
                self.filter_ioc_list(subsystem_name)
        elif item == self.subsystems_root:
            # Root clicked - show all IOCs
            self.filter_ioc_list(None)

    def on_ioc_selected(self, item):
        """Handle IOC selection"""
        # Extract IOC name from display text
        text = item.text()
        ioc_name = text.split()[0]  # First word is the IOC name

        if ioc_name in self.app.ioc_instances:
            self.show_ioc_details(self.app.ioc_instances[ioc_name])

    def show_subsystem_details(self, subsystem: Subsystem):
        """Show subsystem details"""
        html = f"""
        <h3>Subsystem: {subsystem.name}</h3>
        <p><b>Path:</b> {subsystem.path}</p>
        <p><b>Database Files:</b> {len(subsystem.db_files)}</p>
        <p><b>Substitution Files:</b> {len(subsystem.substitution_files)}</p>
        <p><b>Template Files:</b> {len(subsystem.template_files)}</p>

        <h4>Used by IOCs:</h4>
        <ul>
        """

        for ioc_name in sorted(subsystem.used_by_iocs):
            html += f"<li>{ioc_name}</li>"

        html += "</ul>"

        if subsystem.issues:
            html += "<h4>Issues:</h4><ul>"
            for issue in subsystem.issues[:10]:
                html += f"<li>{issue.get('file', '')}: {issue.get('message', '')}</li>"
            html += "</ul>"

        self.details_text.setHtml(html)

    def show_ioc_details(self, ioc: IOCInstance):
        """Show IOC details"""
        html = f"""
        <h3>IOC: {ioc.name}</h3>
        <p><b>Path:</b> {ioc.path}</p>
        <p><b>Description:</b> {ioc.description or 'None'}</p>
        <p><b>Type:</b> {'Test IOC' if ioc.is_test_ioc else 'Production'}</p>

        <h4>Configuration:</h4>
        <ul>
        <li>st.cmd: {'✓' if ioc.has_st_cmd else '✗'}</li>
        <li>Makefile: {'✓' if ioc.has_makefile else '✗'}</li>
        <li>README: {'✓' if ioc.has_readme else '✗'}</li>
        </ul>

        <h4>Subsystems Used:</h4>
        <ul>
        """

        for subsystem in sorted(ioc.subsystems_used):
            html += f"<li>{subsystem}</li>"

        html += "</ul>"

        if ioc.plc_connections:
            html += "<h4>PLC Connections:</h4><ul>"
            for plc in ioc.plc_connections:
                html += f"<li>{plc}</li>"
            html += "</ul>"

        if ioc.loaded_dbs:
            html += f"<h4>Loaded Databases ({len(ioc.loaded_dbs)}):</h4><ul>"
            for db in ioc.loaded_dbs[:10]:
                html += f"<li>{db}</li>"
            if len(ioc.loaded_dbs) > 10:
                html += f"<li>... and {len(ioc.loaded_dbs) - 10} more</li>"
            html += "</ul>"

        self.ioc_details.setHtml(html)

    def validate_all(self):
        """Run complete validation"""
        self.console.appendPlainText("Starting complete validation...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.validator = CryoplantValidator(self.app, self.validation_engine)
        self.validator.progress.connect(lambda msg: self.console.appendPlainText(msg))
        self.validator.validation_update.connect(self.on_validation_update)
        self.validator.finished.connect(self.on_validation_complete)
        self.validator.start()

    def on_validation_update(self, name: str, results: Dict):
        """Handle validation update"""
        # Update tree items with validation status
        for i in range(self.subsystems_root.childCount()):
            item = self.subsystems_root.child(i)
            if item.text(0) == name:
                if 'valid' in results and 'total' in results:
                    if results['valid'] == results['total']:
                        item.setText(2, "✓")
                        item.setBackground(2, QColor(200, 255, 200))
                    else:
                        item.setText(2, f"⚠ {results['valid']}/{results['total']}")
                        item.setBackground(2, QColor(255, 255, 200))
                break

    def on_validation_complete(self):
        """Handle validation completion"""
        self.progress_bar.setVisible(False)

        # Generate validation report
        html = "<h2>Validation Report</h2>"

        # Subsystem validation
        html += "<h3>Subsystems:</h3><ul>"
        for name, subsystem in self.app.subsystems.items():
            status = "✓" if subsystem.valid_files == subsystem.total_files else f"⚠ {subsystem.valid_files}/{subsystem.total_files}"
            html += f"<li><b>{name}:</b> {status}</li>"

            if subsystem.issues:
                html += "<ul>"
                for issue in subsystem.issues[:3]:
                    html += f"<li>{issue.get('file', '')}: {issue.get('message', '')}</li>"
                html += "</ul>"

        html += "</ul>"

        # IOC validation
        html += f"<h3>IOC Instances ({len(self.app.ioc_instances)}):</h3><ul>"
        for name, ioc in self.app.ioc_instances.items():
            status = "✓" if not ioc.issues else f"⚠ {len(ioc.issues)} issues"
            html += f"<li><b>{name}:</b> {status}</li>"

        html += "</ul>"

        self.validation_text.setHtml(html)
        self.center_tabs.setCurrentIndex(1)  # Switch to validation tab

        self.console.appendPlainText("Validation complete!")

    def filter_iocs(self, text: str):
        """Filter IOC list by search text"""
        for i in range(self.ioc_list.count()):
            item = self.ioc_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def filter_ioc_list(self, subsystem_name: Optional[str] = None):
        """Filter IOC list to show only IOCs using the given subsystem"""
        if subsystem_name is None:
            # Show all IOCs
            for i in range(self.ioc_list.count()):
                self.ioc_list.item(i).setHidden(False)
            self.filter_label.setText("Showing: All IOCs")
            self.filter_label.setStyleSheet("font-size: 10px; color: #666; padding: 2px;")
            self.clear_filter_btn.setVisible(False)
        else:
            # Show only IOCs that use this subsystem
            count = 0
            for i in range(self.ioc_list.count()):
                item = self.ioc_list.item(i)
                # Extract IOC name from display text
                ioc_name = item.text().split()[0]
                if ioc_name in self.app.ioc_instances:
                    ioc = self.app.ioc_instances[ioc_name]
                    if subsystem_name in ioc.subsystems_used:
                        item.setHidden(False)
                        count += 1
                    else:
                        item.setHidden(True)

            self.filter_label.setText(f"Showing: IOCs using {subsystem_name} ({count} found)")
            self.filter_label.setStyleSheet("font-size: 10px; color: #0066cc; padding: 2px; font-weight: bold;")
            self.clear_filter_btn.setVisible(True)

    # Placeholder methods
    def validate_subsystems(self): self.console.appendPlainText("Validating subsystems...")
    def validate_iocs(self): self.console.appendPlainText("Validating IOCs...")
    def format_substitutions(self): self.console.appendPlainText("Formatting substitution files...")
    def check_archive_coverage(self): self.console.appendPlainText("Checking archive coverage...")
    def build_application(self): self.console.appendPlainText("Building application...")

def main():
    """Main entry point"""
    import sys
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    manager = CryoplantManager()
    manager.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()