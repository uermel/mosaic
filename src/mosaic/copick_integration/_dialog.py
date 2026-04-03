"""CopickBrowserDialog for importing from and exporting to copick projects."""

import os

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QIcon, QPixmap
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
from ._session import CopickSession


def _color_icon(rgba, size=12):
    """Create a small square QIcon from a copick RGBA color tuple."""
    if rgba is None:
        rgba = (128, 128, 128, 255)
    pm = QPixmap(size, size)
    pm.fill(QColor(*rgba[:4]))
    return QIcon(pm)


def _setup_config_panel(dialog, content_layout):
    """Add the copick configuration group (config input + browse + connect)."""
    config_group = QGroupBox("Copick Configuration")
    config_layout = QHBoxLayout(config_group)

    dialog._config_input = QLineEdit()
    dialog._config_input.setPlaceholderText("Path to copick config JSON...")

    session = CopickSession.get()
    if session.config_path:
        dialog._config_input.setText(session.config_path)
    else:
        default_config = os.environ.get("COPICK_CONFIG", "")
        if default_config:
            dialog._config_input.setText(default_config)

    browse_button = QPushButton(qta.icon("ph.folder-open", color=Colors.ICON), "")
    browse_button.setFixedWidth(36)
    browse_button.setAutoDefault(False)
    browse_button.clicked.connect(dialog._browse_config)

    dialog._connect_button = QPushButton("Connect")
    dialog._connect_button.setAutoDefault(False)
    dialog._connect_button.clicked.connect(dialog._connect)

    config_layout.addWidget(dialog._config_input, 1)
    config_layout.addWidget(browse_button)
    config_layout.addWidget(dialog._connect_button)
    content_layout.addWidget(config_group)


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

    def __init__(self, parent=None, mode="import", geometry_types=None, default_voxel_size=10.0):
        super().__init__(parent)

        self._mode = mode
        self._geometry_types = geometry_types or {}
        self._default_voxel_size = default_voxel_size
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

        # Auto-populate if session is already connected
        session = CopickSession.get()
        if session.is_connected:
            self._apply_session(session)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 10)
        content_layout.setSpacing(12)

        _setup_config_panel(self, content_layout)

        # Run selection
        run_group = QGroupBox("Run")
        run_layout = QHBoxLayout(run_group)
        self._run_combo = QComboBox()
        self._run_combo.setEditable(True)
        self._run_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._run_combo.completer().setFilterMode(Qt.MatchContains)
        self._run_combo.lineEdit().returnPressed.connect(
            self._run_combo.lineEdit().clearFocus
        )
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
        self._action_button.setAutoDefault(False)
        footer.reject_button.setAutoDefault(False)
        main_layout.addWidget(footer)

    def _setup_import_panel(self, parent_layout):
        # Object type filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by object:"))
        self._object_filter = QComboBox()
        self._object_filter.addItem("All Objects")
        self._object_filter.setEnabled(False)
        self._object_filter.currentTextChanged.connect(self._apply_object_filter)
        filter_row.addWidget(self._object_filter, 1)
        parent_layout.addLayout(filter_row)

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

        # Default to Mesh if mesh data is available
        if "Mesh" in available_types and self._geometry_types.get("mesh", False):
            self._type_combo.setCurrentText("Mesh")

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

        # User ID — default "mosaic"
        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("User ID:"))
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("User identifier")
        self._user_input.setText("mosaic")
        user_row.addWidget(self._user_input, 1)
        layout.addLayout(user_row)

        # Session ID — default "pipeline"
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session ID:"))
        self._session_input = QLineEdit()
        self._session_input.setPlaceholderText("Session identifier")
        self._session_input.setText("pipeline")
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
        self._voxel_spin.setValue(self._default_voxel_size)
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

        session = CopickSession.get()
        try:
            session.connect(config_path)
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

        self._apply_session(session)

    def _apply_session(self, session):
        """Populate the dialog from an already-connected session."""
        self._root = session.root
        self._runs = session.runs

        self._run_combo.setEnabled(True)
        self._run_combo.blockSignals(True)
        self._run_combo.clear()
        for run in self._runs:
            self._run_combo.addItem(run.name)
        self._run_combo.blockSignals(False)

        if self._mode == "import":
            # Populate object filter
            self._object_filter.blockSignals(True)
            self._object_filter.clear()
            self._object_filter.addItem("All Objects")
            for obj in sorted(self._root.pickable_objects, key=lambda o: o.name):
                self._object_filter.addItem(_color_icon(obj.color), obj.name)
            self._object_filter.setEnabled(True)
            self._object_filter.blockSignals(False)

        if self._mode == "export":
            self._object_combo.setEnabled(True)
            self._object_combo.clear()
            for obj in sorted(self._root.pickable_objects, key=lambda o: o.name):
                self._object_combo.addItem(_color_icon(obj.color), obj.name)

            # Default to "membrane" if available
            membrane_idx = self._object_combo.findText("membrane")
            if membrane_idx >= 0:
                self._object_combo.setCurrentIndex(membrane_idx)

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

        # Populate picks — sorted by object name then user_id, unchecked
        self._available_picks = sorted(
            run.picks,
            key=lambda p: (p.pickable_object_name.lower(), p.user_id.lower()),
        )
        for picks in self._available_picks:
            label = f"{picks.pickable_object_name} ({picks.user_id}, session {picks.session_id})"
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.setProperty("object_name", picks.pickable_object_name)
            self._pick_checkboxes.append(cb)
            self._picks_layout.addWidget(cb)

        # Populate meshes — sorted by object name then user_id, unchecked
        self._available_meshes = sorted(
            run.meshes,
            key=lambda m: (m.pickable_object_name.lower(), m.user_id.lower()),
        )
        for mesh in self._available_meshes:
            label = f"{mesh.pickable_object_name} ({mesh.user_id}, session {mesh.session_id})"
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.setProperty("object_name", mesh.pickable_object_name)
            self._mesh_checkboxes.append(cb)
            self._meshes_layout.addWidget(cb)

        # Populate segmentations — sorted by name then user_id, unchecked
        self._available_segmentations = sorted(
            run.segmentations,
            key=lambda s: (s.name.lower(), s.user_id.lower()),
        )
        for seg in self._available_segmentations:
            label = (
                f"{seg.name} (voxel_size={seg.voxel_size}, "
                f"{seg.user_id}, session {seg.session_id})"
            )
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.setProperty("object_name", seg.name)
            self._seg_checkboxes.append(cb)
            self._segs_layout.addWidget(cb)

        # Re-apply current filter
        self._apply_object_filter(self._object_filter.currentText())

    def _clear_checkboxes(self, layout, checkbox_list):
        for cb in checkbox_list:
            layout.removeWidget(cb)
            cb.deleteLater()
        checkbox_list.clear()

    def _toggle_all(self, checkboxes, checked):
        for cb in checkboxes:
            if not cb.isHidden():
                cb.setChecked(checked)

    def _apply_object_filter(self, filter_text):
        """Show/hide checkboxes based on the selected object type filter."""
        show_all = filter_text == "All Objects"
        for cb in self._pick_checkboxes:
            cb.setVisible(show_all or cb.property("object_name") == filter_text)
        for cb in self._mesh_checkboxes:
            cb.setVisible(show_all or cb.property("object_name") == filter_text)
        for cb in self._seg_checkboxes:
            cb.setVisible(show_all or cb.property("object_name") == filter_text)

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


class CopickTomogramDialog(QDialog):
    """Dialog for selecting a copick tomogram to load into the volume viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Tomogram from Copick")
        self.resize(500, 300)

        self._root = None
        self._runs = []
        self._voxel_spacings = []
        self._tomograms = []

        self._setup_ui()
        self.setStyleSheet(
            QGroupBox_style + QPushButton_style + QLineEdit_style + QCheckBox_style
        )

        session = CopickSession.get()
        if session.is_connected:
            self._apply_session(session)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 10)
        content_layout.setSpacing(12)

        _setup_config_panel(self, content_layout)

        # Run selection
        run_group = QGroupBox("Run")
        run_layout = QHBoxLayout(run_group)
        self._run_combo = QComboBox()
        self._run_combo.setEditable(True)
        self._run_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._run_combo.completer().setFilterMode(Qt.MatchContains)
        self._run_combo.lineEdit().returnPressed.connect(
            self._run_combo.lineEdit().clearFocus
        )
        self._run_combo.setEnabled(False)
        self._run_combo.currentIndexChanged.connect(self._on_run_changed)
        run_layout.addWidget(self._run_combo)
        content_layout.addWidget(run_group)

        # Voxel spacing selection
        settings_group = QGroupBox("Tomogram Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(8)

        vs_row = QHBoxLayout()
        vs_row.addWidget(QLabel("Voxel Spacing (\u00c5):"))
        self._vs_combo = QComboBox()
        self._vs_combo.setEnabled(False)
        self._vs_combo.currentIndexChanged.connect(self._on_vs_changed)
        vs_row.addWidget(self._vs_combo, 1)
        settings_layout.addLayout(vs_row)

        # Tomogram type selection
        tomo_row = QHBoxLayout()
        tomo_row.addWidget(QLabel("Tomogram Type:"))
        self._tomo_combo = QComboBox()
        self._tomo_combo.setEnabled(False)
        self._tomo_combo.currentIndexChanged.connect(self._on_tomo_changed)
        tomo_row.addWidget(self._tomo_combo, 1)
        settings_layout.addLayout(tomo_row)

        # Zarr binning level
        bin_row = QHBoxLayout()
        bin_row.addWidget(QLabel("Binning Level:"))
        self._bin_combo = QComboBox()
        self._bin_combo.setEnabled(False)
        self._bin_combo.setToolTip(
            "OME-Zarr resolution level (0 = full, higher = more binned)"
        )
        bin_row.addWidget(self._bin_combo, 1)
        settings_layout.addLayout(bin_row)

        content_layout.addWidget(settings_group)
        content_layout.addStretch()
        main_layout.addWidget(content, 1)

        # Footer
        footer = DialogFooter(dialog=self, margin=(20, 10, 20, 10))
        self._action_button = footer.accept_button
        self._action_button.setText("Load")
        self._action_button.setIcon(
            qta.icon("ph.upload", color=Colors.PRIMARY)
        )
        self._action_button.setEnabled(False)
        self._action_button.setAutoDefault(False)
        footer.reject_button.setAutoDefault(False)
        main_layout.addWidget(footer)

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

        session = CopickSession.get()
        try:
            session.connect(config_path)
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

        self._apply_session(session)

    def _apply_session(self, session):
        self._root = session.root
        self._runs = session.runs

        self._run_combo.setEnabled(True)
        self._run_combo.blockSignals(True)
        self._run_combo.clear()
        for run in self._runs:
            self._run_combo.addItem(run.name)
        self._run_combo.blockSignals(False)

        if self._runs:
            self._on_run_changed(0)

    def _on_run_changed(self, index):
        if index < 0 or index >= len(self._runs):
            return

        run = self._runs[index]
        self._voxel_spacings = sorted(
            run.voxel_spacings, key=lambda vs: vs.voxel_size
        )

        self._vs_combo.setEnabled(True)
        self._vs_combo.blockSignals(True)
        self._vs_combo.clear()
        for vs in self._voxel_spacings:
            self._vs_combo.addItem(str(vs.voxel_size))
        self._vs_combo.blockSignals(False)

        if self._voxel_spacings:
            self._on_vs_changed(0)

    def _on_vs_changed(self, index):
        if index < 0 or index >= len(self._voxel_spacings):
            return

        vs = self._voxel_spacings[index]
        self._tomograms = list(vs.tomograms)

        self._tomo_combo.blockSignals(True)
        self._tomo_combo.setEnabled(True)
        self._tomo_combo.clear()
        for tomo in self._tomograms:
            self._tomo_combo.addItem(tomo.tomo_type)
        self._tomo_combo.blockSignals(False)

        self._action_button.setEnabled(len(self._tomograms) > 0)

        if self._tomograms:
            self._on_tomo_changed(0)

    def _on_tomo_changed(self, index):
        if index < 0 or index >= len(self._tomograms):
            return

        import zarr

        tomo = self._tomograms[index]
        self._bin_combo.clear()
        try:
            group = zarr.open(tomo.zarr(), mode="r")
            levels = sorted(int(k) for k in group.keys() if k.isdigit())
            for lvl in levels:
                self._bin_combo.addItem(str(lvl))
            # Default to the highest available level
            self._bin_combo.setCurrentIndex(self._bin_combo.count() - 1)
        except Exception:
            # Fallback if we cannot probe the store
            for lvl in range(3):
                self._bin_combo.addItem(str(lvl))
            self._bin_combo.setCurrentIndex(2)
        self._bin_combo.setEnabled(True)

    def get_result(self):
        """Return the selected tomogram details.

        Returns
        -------
        dict
            {"run", "voxel_spacing", "tomogram", "binning_level"}
        """
        run_idx = self._run_combo.currentIndex()
        vs_idx = self._vs_combo.currentIndex()
        tomo_idx = self._tomo_combo.currentIndex()
        bin_idx = self._bin_combo.currentIndex()

        return {
            "run": self._runs[run_idx] if run_idx >= 0 else None,
            "voxel_spacing": self._voxel_spacings[vs_idx] if vs_idx >= 0 else None,
            "tomogram": self._tomograms[tomo_idx] if tomo_idx >= 0 else None,
            "binning_level": int(self._bin_combo.currentText()) if bin_idx >= 0 else 0,
        }
