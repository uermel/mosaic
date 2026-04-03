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
from ._setup_dialog import CopickSetupDialog
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

    # Build a name → colour lookup from copick pickable objects.
    color_map = {}
    root = result.get("root")
    if root is not None:
        for obj in root.pickable_objects:
            if obj.color is not None:
                c = obj.color[:3]
                color_map[obj.name] = tuple(
                    v / 255 if max(c) > 1 else v for v in c
                )

    for picks in result["picks"]:
        out.picks.append(copick_picks_to_geometry_data(picks))

    for mesh in result["meshes"]:
        d = copick_mesh_to_geometry_data(mesh)
        color = color_map.get(mesh.pickable_object_name)
        if color is not None:
            d["color"] = color
        out.meshes.append(d)

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
    default_voxel_size = float(np.max(geometries[0].sampling_rate))

    dialog = CopickBrowserDialog(
        parent=parent,
        mode="export",
        geometry_types={
            "picks": True,
            "mesh": has_mesh,
            "segmentation": True,
        },
        default_voxel_size=default_voxel_size,
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

    # Read the requested OME-Zarr resolution level and transpose from
    # copick's (Z, Y, X) axis order to mosaic's (X, Y, Z).
    # Each binning level doubles the voxel size (level 0 = 1x, 1 = 2x, 2 = 4x).
    binning_level = result["binning_level"]
    data = tomogram.numpy(zarr_group=str(binning_level)).T.astype(np.float32)
    voxel_size = voxel_spacing.voxel_size * (2 ** binning_level)
    return TomogramResult(
        data=data,
        voxel_size=voxel_size,
        source_path=f"copick://{tomogram.tomo_type}",
    )


def show_setup_dialog(parent) -> Optional[str]:
    """Open the copick project setup dialog.

    Returns the path to the created config file on success, or ``None``
    if the user cancels.
    """
    dialog = CopickSetupDialog(parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.get_config_path()
