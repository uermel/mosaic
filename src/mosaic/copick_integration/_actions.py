"""High-level copick workflows used by the mosaic GUI.

Each function opens a dialog, performs the necessary conversions, and returns
a result dataclass (or ``None`` when the user cancels).  Export additionally
writes data back to the copick project and shows success/error messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from qtpy.QtWidgets import QDialog, QMessageBox

from ._dialog import CopickBrowserDialog, CopickTomogramDialog
from ._reader import (
    copick_mesh_to_geometry_data,
    copick_picks_to_geometry_data,
    copick_segmentation_to_geometries,
)
from ._writer import (
    geometry_to_copick_mesh,
    geometry_to_copick_picks,
    geometry_to_copick_segmentation,
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """Converted copick data ready for insertion into mosaic containers."""

    picks: List[dict] = field(default_factory=list)
    meshes: List[dict] = field(default_factory=list)
    segmentations: list = field(default_factory=list)


@dataclass
class TomogramResult:
    """Copick tomogram converted for the mosaic volume viewer."""

    data: np.ndarray
    voxel_size: float
    source_path: str


# ---------------------------------------------------------------------------
# Facade functions
# ---------------------------------------------------------------------------

def show_import_dialog(parent) -> Optional[ImportResult]:
    """Open the copick import dialog and return converted mosaic data.

    Returns ``None`` when the user cancels the dialog.
    """
    dialog = CopickBrowserDialog(parent=parent, mode="import")
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    result = dialog.get_result()
    out = ImportResult()

    for picks in result["picks"]:
        out.picks.append(copick_picks_to_geometry_data(picks))

    for mesh in result["meshes"]:
        out.meshes.append(copick_mesh_to_geometry_data(mesh))

    for seg in result["segmentations"]:
        from ..geometry import SegmentationGeometry

        for entry in copick_segmentation_to_geometries(seg):
            seg_geom = SegmentationGeometry(
                points=entry["points"],
                sampling_rate=entry["sampling_rate"],
                color=entry.get("color", (0.7, 0.7, 0.7)),
                meta=entry["meta"],
            )
            out.segmentations.append(seg_geom)

    return out


def export_geometries(parent, geometries) -> bool:
    """Open the copick export dialog and write *geometries* to a copick run.

    Returns ``True`` on success, ``False`` on cancel or error.
    """
    has_mesh = any(
        hasattr(g.model, "mesh") for g in geometries if g.model is not None
    )
    has_seg = any(g._representation == "segmentation" for g in geometries)

    dialog = CopickBrowserDialog(
        parent=parent,
        mode="export",
        geometry_types={
            "picks": True,
            "mesh": has_mesh,
            "segmentation": has_seg,
        },
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False

    config = dialog.get_result()
    run = config["run"]
    object_name = config["object_name"]
    user_id = config["user_id"]
    session_id = config["session_id"]
    data_type = config["data_type"]

    try:
        if data_type == "picks":
            for g in geometries:
                geometry_to_copick_picks(g, run, object_name, session_id, user_id)
        elif data_type == "mesh":
            for g in geometries:
                if g.model is not None and hasattr(g.model, "mesh"):
                    geometry_to_copick_mesh(
                        g, run, object_name, session_id, user_id
                    )
        elif data_type == "segmentation":
            voxel_size = config["voxel_size"]
            is_multilabel = config["is_multilabel"]
            for g in geometries:
                if g._representation == "segmentation":
                    geometry_to_copick_segmentation(
                        g,
                        run,
                        object_name,
                        session_id,
                        user_id,
                        voxel_size,
                        is_multilabel,
                    )

        QMessageBox.information(
            parent, "Export Complete", "Data exported to copick successfully."
        )
        return True
    except Exception as e:
        QMessageBox.warning(
            parent, "Export Error", f"Failed to export to copick:\n{e}"
        )
        return False


def show_tomogram_dialog(parent) -> Optional[TomogramResult]:
    """Open the copick tomogram dialog and return converted volume data.

    Returns ``None`` when the user cancels the dialog or no tomogram is
    selected.
    """
    dialog = CopickTomogramDialog(parent=parent)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None

    result = dialog.get_result()
    tomogram = result["tomogram"]
    voxel_spacing = result["voxel_spacing"]
    if tomogram is None or voxel_spacing is None:
        return None

    # Copick returns (Z, Y, X); transpose to match mosaic's axis order.
    data = tomogram.numpy().T.astype(np.float32)
    return TomogramResult(
        data=data,
        voxel_size=voxel_spacing.voxel_size,
        source_path=f"copick://{tomogram.tomo_type}",
    )
