"""CopickBrowserDialog for importing from and exporting to copick projects."""

import os

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QWidget,
    QSizePolicy,
)
import qtawesome as qta

from ..widgets import DialogFooter
from ..stylesheets import (
    QGroupBox_style,
    QPushButton_style,
    QLineEdit_style,
    QCheckBox_style,
    Colors,
)


class CopickBrowserDialog(QDialog):
    """Dialog for browsing and selecting copick data for import/export.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.
    mode : str
        Either "import" or "export".
    geometry_types : dict, optional
        For export mode, dict of {type: bool} indicating which types are available.
    """

    def __init__(self, parent=None, mode="import", geometry_types=None):
        super().__init__(parent)

        self._mode = mode
        self._geometry_types = geometry_types or {}
        self._root = None
        self._runs = []
        self._selected_run = None

        # Import mode state
        self._available_picks = []
        self._available_meshes = []
        self._available_segmentations = []
        self._pick_checkboxes = []
        self._mesh_checkboxes = []
        self._seg_checkboxes = []

        title = "Import from Copick" if mode == "import" else "Export to Copick"
        self.setWindowTitle(title)
        self.resize(600, 500)

        self._setup_ui()
        self.setStyleSheet(
            QGroupBox_style + QPushButton_style + QLineEdit_style + QCheckBox_style
        )

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 10)
        content_layout.setSpacing(12)

        # Config panel
        config_group = QGroupBox("Copick Configuration")
        config_layout = QHBoxLayout(config_group)

        self._config_input = QLineEdit()
        self._config_input.setPlaceholderText("Path to copick config JSON...")
        default_config = os.environ.get("COPICK_CONFIG", "")
        if default_config:
            self._config_input.setText(default_config)

        browse_button = QPushButton(qta.icon("ph.folder-open", color=Colors.ICON), "")
        browse_button.setFixedWidth(36)
        browse_button.clicked.connect(self._browse_config)

        self._connect_button = QPushButton("Connect")
        self._connect_button.clicked.connect(self._connect)

        config_layout.addWidget(self._config_input, 1)
        config_layout.addWidget(browse_button)
        config_layout.addWidget(self._connect_button)
        content_layout.addWidget(config_group)

        # Run selection
        run_group = QGroupBox("Run")
        run_layout = QHBoxLayout(run_group)
        self._run_combo = QComboBox()
        self._run_combo.setEnabled(False)
        self._run_combo.currentIndexChanged.connect(self._on_run_changed)
        run_layout.addWidget(self._run_combo)
        content_layout.addWidget(run_group)

        if self._mode == "import":
            self._setup_import_panel(content_layout)
        else:
            self._setup_export_panel(content_layout)

        main_layout.addWidget(content, 1)

        # Footer
        footer = DialogFooter(dialog=self, margin=(20, 10, 20, 10))
        action_text = "Import" if self._mode == "import" else "Export"
        self._action_button = footer.accept_button
        self._action_button.setText(action_text)
        icon_name = "ph.upload" if self._mode == "import" else "ph.download"
        self._action_button.setIcon(qta.icon(icon_name, color=Colors.PRIMARY))
        self._action_button.setEnabled(False)
        main_layout.addWidget(footer)

    def _setup_import_panel(self, parent_layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        scroll_content = QWidget()
        self._data_layout = QVBoxLayout(scroll_content)
        self._data_layout.setContentsMargins(0, 0, 0, 0)
        self._data_layout.setSpacing(8)

        # Picks section
        self._picks_group = QGroupBox("Picks (Point Clouds)")
        self._picks_layout = QVBoxLayout(self._picks_group)
        self._picks_select_all = QCheckBox("Select All")
        self._picks_select_all.toggled.connect(
            lambda checked: self._toggle_all(self._pick_checkboxes, checked)
        )
        self._picks_layout.addWidget(self._picks_select_all)
        self._data_layout.addWidget(self._picks_group)

        # Meshes section
        self._meshes_group = QGroupBox("Meshes")
        self._meshes_layout = QVBoxLayout(self._meshes_group)
        self._meshes_select_all = QCheckBox("Select All")
        self._meshes_select_all.toggled.connect(
            lambda checked: self._toggle_all(self._mesh_checkboxes, checked)
        )
        self._meshes_layout.addWidget(self._meshes_select_all)
        self._data_layout.addWidget(self._meshes_group)

        # Segmentations section
        self._segs_group = QGroupBox("Segmentations")
        self._segs_layout = QVBoxLayout(self._segs_group)
        self._segs_select_all = QCheckBox("Select All")
        self._segs_select_all.toggled.connect(
            lambda checked: self._toggle_all(self._seg_checkboxes, checked)
        )
        self._segs_layout.addWidget(self._segs_select_all)
        self._data_layout.addWidget(self._segs_group)

        self._data_layout.addStretch()
        scroll.setWidget(scroll_content)
        parent_layout.addWidget(scroll, 1)

    def _setup_export_panel(self, parent_layout):
        export_group = QGroupBox("Export Settings")
        layout = QVBoxLayout(export_group)
        layout.setSpacing(8)

        # Data type selection
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Data Type:"))
        self._type_combo = QComboBox()
        available_types = []
        if self._geometry_types.get("picks", True):
            available_types.append("Picks")
        if self._geometry_types.get("mesh", False):
            available_types.append("Mesh")
        if self._geometry_types.get("segmentation", False):
            available_types.append("Segmentation")
        if not available_types:
            available_types.append("Picks")
        self._type_combo.addItems(available_types)
        self._type_combo.currentTextChanged.connect(self._on_export_type_changed)
        type_row.addWidget(self._type_combo, 1)
        layout.addLayout(type_row)

        # Object name
        obj_row = QHBoxLayout()
        obj_row.addWidget(QLabel("Object Name:"))
        self._object_combo = QComboBox()
        self._object_combo.setEditable(True)
        self._object_combo.setEnabled(False)
        obj_row.addWidget(self._object_combo, 1)
        layout.addLayout(obj_row)

        # User ID
        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("User ID:"))
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("User identifier")
        user_row.addWidget(self._user_input, 1)
        layout.addLayout(user_row)

        # Session ID
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session ID:"))
        self._session_input = QLineEdit()
        self._session_input.setPlaceholderText("Session identifier")
        session_row.addWidget(self._session_input, 1)
        layout.addLayout(session_row)

        # Segmentation-specific settings
        self._seg_settings = QWidget()
        seg_layout = QVBoxLayout(self._seg_settings)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(8)

        voxel_row = QHBoxLayout()
        voxel_row.addWidget(QLabel("Voxel Size (\u00c5):"))
        self._voxel_spin = QDoubleSpinBox()
        self._voxel_spin.setRange(0.01, 10000)
        self._voxel_spin.setDecimals(2)
        self._voxel_spin.setValue(10.0)
        voxel_row.addWidget(self._voxel_spin, 1)
        seg_layout.addLayout(voxel_row)

        self._multilabel_check = QCheckBox("Multilabel segmentation")
        seg_layout.addWidget(self._multilabel_check)

        layout.addWidget(self._seg_settings)
        self._seg_settings.setVisible(
            self._type_combo.currentText() == "Segmentation"
        )

        # URI display
        self._uri_label = QLabel("URI:")
        self._uri_display = QLineEdit()
        self._uri_display.setReadOnly(True)
        self._uri_display.setPlaceholderText("URI will be shown after connect...")
        uri_row = QHBoxLayout()
        uri_row.addWidget(self._uri_label)
        uri_row.addWidget(self._uri_display, 1)
        layout.addLayout(uri_row)
        self._uri_label.setVisible(
            self._type_combo.currentText() == "Segmentation"
        )
        self._uri_display.setVisible(
            self._type_combo.currentText() == "Segmentation"
        )

        parent_layout.addWidget(export_group, 1)

    def _browse_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Copick Config", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self._config_input.setText(path)

    def _connect(self):
        config_path = self._config_input.text().strip()
        if not config_path:
            QMessageBox.warning(self, "Error", "Please specify a copick config path.")
            return

        try:
            from copick import from_file

            self._root = from_file(config_path)
        except ImportError:
            QMessageBox.warning(
                self,
                "Missing Dependency",
                "copick is not installed. Install with: pip install mosaic-gui[copick]",
            )
            return
        except Exception as e:
            QMessageBox.warning(
                self, "Connection Error", f"Failed to load copick config:\n{e}"
            )
            return

        # Populate runs
        self._runs = list(self._root.runs)
        self._run_combo.setEnabled(True)
        self._run_combo.clear()
        for run in self._runs:
            self._run_combo.addItem(run.name)

        # Populate object names for export
        if self._mode == "export":
            self._object_combo.setEnabled(True)
            self._object_combo.clear()
            for obj in self._root.pickable_objects:
                self._object_combo.addItem(obj.name)

            if self._root.config.user_id:
                self._user_input.setText(self._root.config.user_id)
            if self._root.config.session_id:
                self._session_input.setText(self._root.config.session_id)

        self._action_button.setEnabled(len(self._runs) > 0)

        if self._runs:
            self._on_run_changed(0)

    def _on_run_changed(self, index):
        if index < 0 or index >= len(self._runs):
            return

        self._selected_run = self._runs[index]

        if self._mode == "import":
            self._populate_import_data()
        else:
            self._update_uri()

    def _populate_import_data(self):
        run = self._selected_run
        if run is None:
            return

        # Clear existing checkboxes
        self._clear_checkboxes(self._picks_layout, self._pick_checkboxes)
        self._clear_checkboxes(self._meshes_layout, self._mesh_checkboxes)
        self._clear_checkboxes(self._segs_layout, self._seg_checkboxes)

        # Populate picks
        self._available_picks = list(run.picks)
        for picks in self._available_picks:
            label = f"{picks.pickable_object_name} ({picks.user_id}, session {picks.session_id})"
            cb = QCheckBox(label)
            cb.setChecked(True)
            self._pick_checkboxes.append(cb)
            self._picks_layout.addWidget(cb)

        # Populate meshes
        self._available_meshes = list(run.meshes)
        for mesh in self._available_meshes:
            label = f"{mesh.pickable_object_name} ({mesh.user_id}, session {mesh.session_id})"
            cb = QCheckBox(label)
            cb.setChecked(True)
            self._mesh_checkboxes.append(cb)
            self._meshes_layout.addWidget(cb)

        # Populate segmentations
        self._available_segmentations = list(run.segmentations)
        for seg in self._available_segmentations:
            label = (
                f"{seg.name} (voxel_size={seg.voxel_size}, "
                f"{seg.user_id}, session {seg.session_id})"
            )
            cb = QCheckBox(label)
            cb.setChecked(True)
            self._seg_checkboxes.append(cb)
            self._segs_layout.addWidget(cb)

    def _clear_checkboxes(self, layout, checkbox_list):
        for cb in checkbox_list:
            layout.removeWidget(cb)
            cb.deleteLater()
        checkbox_list.clear()

    def _toggle_all(self, checkboxes, checked):
        for cb in checkboxes:
            cb.setChecked(checked)

    def _on_export_type_changed(self, type_text):
        is_seg = type_text == "Segmentation"
        self._seg_settings.setVisible(is_seg)
        self._uri_label.setVisible(is_seg)
        self._uri_display.setVisible(is_seg)
        if is_seg:
            self._update_uri()

    def _update_uri(self):
        if not hasattr(self, "_uri_display"):
            return

        from ._uri import build_segmentation_uri

        config_path = self._config_input.text().strip()
        run_name = self._run_combo.currentText()
        user_id = self._user_input.text().strip() or "unknown"
        session_id = self._session_input.text().strip() or "0"
        name = self._object_combo.currentText() or "segmentation"
        voxel_size = self._voxel_spin.value()

        uri = build_segmentation_uri(
            config_path, run_name, voxel_size, user_id, session_id, name
        )
        self._uri_display.setText(uri)

    def get_result(self):
        """Return the dialog result as a structured dictionary.

        Returns
        -------
        dict
            For import mode: {"root", "run", "picks", "meshes", "segmentations"}
            For export mode: {"root", "run", "object_name", "user_id", "session_id",
                             "data_type", "voxel_size", "is_multilabel", "uri"}
        """
        if self._mode == "import":
            picks = [
                self._available_picks[i]
                for i, cb in enumerate(self._pick_checkboxes)
                if cb.isChecked()
            ]
            meshes = [
                self._available_meshes[i]
                for i, cb in enumerate(self._mesh_checkboxes)
                if cb.isChecked()
            ]
            segmentations = [
                self._available_segmentations[i]
                for i, cb in enumerate(self._seg_checkboxes)
                if cb.isChecked()
            ]
            return {
                "root": self._root,
                "run": self._selected_run,
                "picks": picks,
                "meshes": meshes,
                "segmentations": segmentations,
            }
        else:
            data_type = self._type_combo.currentText().lower()
            result = {
                "root": self._root,
                "run": self._selected_run,
                "object_name": self._object_combo.currentText(),
                "user_id": self._user_input.text().strip(),
                "session_id": self._session_input.text().strip(),
                "data_type": data_type,
            }
            if data_type == "segmentation":
                result["voxel_size"] = self._voxel_spin.value()
                result["is_multilabel"] = self._multilabel_check.isChecked()
                result["uri"] = self._uri_display.text()
            return result
