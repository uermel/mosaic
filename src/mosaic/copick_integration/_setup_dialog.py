"""Dialog for creating new copick project configurations."""

import json
import os

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from ..widgets import DialogFooter
from ..stylesheets import (
    QGroupBox_style,
    QPushButton_style,
    QLineEdit_style,
    Colors,
)


class CopickSetupDialog(QDialog):
    """Dialog for creating a new copick project configuration.

    Supports two project types:

    * **CZ CryoET Data Portal** -- reads tomograms and annotations from the
      portal, writes user data to a local overlay directory.
    * **Local Filesystem** -- all data lives on the local filesystem with an
      optional read-only static directory.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Copick Project")
        self.resize(560, 340)
        self._setup_ui()
        self.setStyleSheet(
            QGroupBox_style + QPushButton_style + QLineEdit_style
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 10)
        content_layout.setSpacing(12)

        # -- Project type --------------------------------------------------
        type_group = QGroupBox("Project Type")
        type_layout = QHBoxLayout(type_group)
        self._type_combo = QComboBox()
        self._type_combo.addItems(
            ["CZ CryoET Data Portal", "Local Filesystem"]
        )
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self._type_combo)
        content_layout.addWidget(type_group)

        # -- Common fields -------------------------------------------------
        common_group = QGroupBox("Project Settings")
        common_layout = QVBoxLayout(common_group)
        common_layout.setSpacing(8)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Project Name:"))
        self._name_input = QLineEdit("My Copick Project")
        name_row.addWidget(self._name_input, 1)
        common_layout.addLayout(name_row)

        overlay_row = QHBoxLayout()
        overlay_row.addWidget(QLabel("Overlay Directory:"))
        self._overlay_input = QLineEdit()
        self._overlay_input.setPlaceholderText("Local path for annotations...")
        overlay_browse = QPushButton(
            qta.icon("ph.folder-open", color=Colors.ICON), ""
        )
        overlay_browse.setFixedWidth(36)
        overlay_browse.setAutoDefault(False)
        overlay_browse.clicked.connect(
            lambda: self._browse_directory(self._overlay_input)
        )
        overlay_row.addWidget(self._overlay_input, 1)
        overlay_row.addWidget(overlay_browse)
        common_layout.addLayout(overlay_row)

        content_layout.addWidget(common_group)

        # -- Data Portal fields --------------------------------------------
        self._portal_group = QGroupBox("Data Portal Settings")
        portal_layout = QVBoxLayout(self._portal_group)
        portal_layout.setSpacing(8)

        ds_row = QHBoxLayout()
        ds_row.addWidget(QLabel("Dataset IDs:"))
        self._dataset_input = QLineEdit()
        self._dataset_input.setPlaceholderText("Comma-separated, e.g. 10301, 10302")
        ds_row.addWidget(self._dataset_input, 1)
        portal_layout.addLayout(ds_row)

        content_layout.addWidget(self._portal_group)

        # -- Local fields --------------------------------------------------
        self._local_group = QGroupBox("Static Data (optional)")
        local_layout = QVBoxLayout(self._local_group)
        local_layout.setSpacing(8)

        static_row = QHBoxLayout()
        static_row.addWidget(QLabel("Static Directory:"))
        self._static_input = QLineEdit()
        self._static_input.setPlaceholderText(
            "Read-only reference data (leave empty to use overlay only)"
        )
        static_browse = QPushButton(
            qta.icon("ph.folder-open", color=Colors.ICON), ""
        )
        static_browse.setFixedWidth(36)
        static_browse.setAutoDefault(False)
        static_browse.clicked.connect(
            lambda: self._browse_directory(self._static_input)
        )
        static_row.addWidget(self._static_input, 1)
        static_row.addWidget(static_browse)
        local_layout.addLayout(static_row)

        content_layout.addWidget(self._local_group)
        self._local_group.setVisible(False)

        # -- Save location -------------------------------------------------
        save_group = QGroupBox("Config File")
        save_layout = QHBoxLayout(save_group)
        self._save_input = QLineEdit()
        self._save_input.setPlaceholderText("Where to save the config JSON...")
        save_browse = QPushButton(
            qta.icon("ph.folder-open", color=Colors.ICON), ""
        )
        save_browse.setFixedWidth(36)
        save_browse.setAutoDefault(False)
        save_browse.clicked.connect(self._browse_save_path)
        save_layout.addWidget(self._save_input, 1)
        save_layout.addWidget(save_browse)
        content_layout.addWidget(save_group)

        content_layout.addStretch()
        main_layout.addWidget(content, 1)

        # -- Footer --------------------------------------------------------
        footer = DialogFooter(dialog=self, margin=(20, 10, 20, 10))
        self._action_button = footer.accept_button
        self._action_button.setText("Create")
        self._action_button.setIcon(
            qta.icon("ph.plus-circle", color=Colors.PRIMARY)
        )
        self._action_button.setAutoDefault(False)
        footer.reject_button.setAutoDefault(False)
        main_layout.addWidget(footer)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_type_changed(self, index):
        is_portal = index == 0
        self._portal_group.setVisible(is_portal)
        self._local_group.setVisible(not is_portal)

    def _browse_directory(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            line_edit.setText(path)

    def _browse_save_path(self):
        start_dir = ""
        overlay = self._overlay_input.text().strip()
        if overlay:
            start_dir = os.path.dirname(overlay)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Config File",
            start_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            self._save_input.setText(path)

    # ------------------------------------------------------------------
    # Validation & creation
    # ------------------------------------------------------------------

    def accept(self):
        """Validate inputs, create the config, and connect the session."""
        overlay = self._overlay_input.text().strip()
        save_path = self._save_input.text().strip()

        if not overlay:
            QMessageBox.warning(self, "Error", "Overlay directory is required.")
            return
        if not save_path:
            QMessageBox.warning(self, "Error", "Config save path is required.")
            return

        is_portal = self._type_combo.currentIndex() == 0

        try:
            if is_portal:
                self._create_portal_project(overlay, save_path)
            else:
                self._create_local_project(overlay, save_path)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to create project:\n{e}"
            )
            return

        from ._session import CopickSession

        CopickSession.get().connect(save_path)
        super().accept()

    def _create_portal_project(self, overlay, save_path):
        raw = self._dataset_input.text().strip()
        if not raw:
            raise ValueError("At least one dataset ID is required.")

        dataset_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        if not dataset_ids:
            raise ValueError("At least one dataset ID is required.")

        from copick import from_czcdp_datasets

        from_czcdp_datasets(
            dataset_ids=dataset_ids,
            overlay_root=f"local://{overlay}",
            overlay_fs_args={"auto_mkdir": True},
            output_path=save_path,
        )

    def _create_local_project(self, overlay, save_path):
        name = self._name_input.text().strip() or "My Copick Project"
        static = self._static_input.text().strip()

        import copick

        config_data = {
            "config_type": "filesystem",
            "name": name,
            "description": "",
            "version": copick.__version__,
            "pickable_objects": [],
            "overlay_root": f"local://{overlay}",
            "overlay_fs_args": {"auto_mkdir": True},
        }

        if static:
            config_data["static_root"] = f"local://{static}"
            config_data["static_fs_args"] = {}

        directory = os.path.dirname(save_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(save_path, "w") as f:
            json.dump(config_data, f, indent=4)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def get_config_path(self):
        """Return the path to the created config file."""
        return self._save_input.text().strip()
