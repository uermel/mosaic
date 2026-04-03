"""Copick -> Mosaic data conversions."""

from typing import List

import numpy as np


def copick_picks_to_geometry_data(picks) -> dict:
    """Convert CopickPicks to mosaic GeometryData keyword arguments.

    Parameters
    ----------
    picks : CopickPicks
        Copick picks object containing point positions and orientations.

    Returns
    -------
    dict
        Keyword arguments suitable for adding to a mosaic DataContainer.
    """
    from scipy.spatial.transform import Rotation

    from ..utils import apply_quat

    positions, transforms = picks.numpy()

    quaternions = None
    normals = None
    if picks.trust_orientation and transforms is not None and len(transforms) > 0:
        rotation_matrices = transforms[:, :3, :3]
        quaternions = Rotation.from_matrix(rotation_matrices).as_quat(
            scalar_first=True
        )
        quaternions = quaternions.astype(np.float32)
        normals = apply_quat(quaternions).astype(np.float32)

    return {
        "points": positions.astype(np.float32),
        "normals": normals,
        "quaternions": quaternions,
        "meta": {
            "name": f"{picks.pickable_object_name} ({picks.user_id})",
            "copick_type": "picks",
            "copick_object_name": picks.pickable_object_name,
            "copick_user_id": picks.user_id,
            "copick_session_id": picks.session_id,
        },
    }


def copick_mesh_to_geometry_data(mesh) -> dict:
    """Convert CopickMesh to mosaic GeometryData keyword arguments.

    Parameters
    ----------
    mesh : CopickMesh
        Copick mesh object wrapping a trimesh geometry.

    Returns
    -------
    dict
        Keyword arguments including points, normals, faces, and a TriangularMesh model.
    """
    import trimesh

    from ..meshing import to_open3d
    from ..parametrization import TriangularMesh

    tmesh = mesh.mesh
    if isinstance(tmesh, trimesh.Scene):
        tmesh = tmesh.dump(concatenate=True)

    vertices = np.asarray(tmesh.vertices, dtype=np.float64)
    faces = np.asarray(tmesh.faces, dtype=np.int32)
    normals = None
    if tmesh.vertex_normals is not None and len(tmesh.vertex_normals) == len(vertices):
        normals = np.asarray(tmesh.vertex_normals, dtype=np.float64)

    o3d_mesh = to_open3d(vertices, faces, normals)
    if not o3d_mesh.has_vertex_normals():
        o3d_mesh.compute_vertex_normals()

    return {
        "points": np.asarray(o3d_mesh.vertices, dtype=np.float32),
        "normals": np.asarray(o3d_mesh.vertex_normals, dtype=np.float32),
        "model": TriangularMesh(o3d_mesh),
        "meta": {
            "name": f"{mesh.pickable_object_name} mesh ({mesh.user_id})",
            "copick_type": "mesh",
            "copick_object_name": mesh.pickable_object_name,
            "copick_user_id": mesh.user_id,
            "copick_session_id": mesh.session_id,
        },
    }


def copick_segmentation_to_geometries(seg) -> List[dict]:
    """Convert CopickSegmentation to a list of mosaic geometry keyword arguments.

    For single-label segmentations, returns one entry. For multilabel segmentations,
    returns one entry per unique label (excluding background = 0).

    Parameters
    ----------
    seg : CopickSegmentation
        Copick segmentation object backed by OME-ZARR.

    Returns
    -------
    list of dict
        Each dict contains points, sampling_rate, color, and meta for creating
        a SegmentationGeometry.
    """
    data = seg.numpy()
    voxel_size = seg.voxel_size
    sampling_rate = np.array([voxel_size, voxel_size, voxel_size], dtype=np.float32)

    results = []

    if seg.is_multilabel:
        labels = np.unique(data)
        labels = labels[labels != 0]
        for label in labels:
            coords = np.argwhere(data == label).astype(np.float32)
            coords *= sampling_rate
            color = seg.color if seg.color is not None else (0.7, 0.7, 0.7)
            results.append(
                {
                    "points": coords,
                    "sampling_rate": sampling_rate,
                    "color": tuple(c / 255 if max(color) > 1 else c for c in color[:3]),
                    "meta": {
                        "name": f"{seg.name} label {int(label)} ({seg.user_id})",
                        "copick_type": "segmentation",
                        "copick_name": seg.name,
                        "copick_user_id": seg.user_id,
                        "copick_session_id": seg.session_id,
                        "copick_voxel_size": voxel_size,
                        "copick_label": int(label),
                    },
                }
            )
    else:
        coords = np.argwhere(data > 0).astype(np.float32)
        coords *= sampling_rate
        color = seg.color if seg.color is not None else (0.7, 0.7, 0.7)
        results.append(
            {
                "points": coords,
                "sampling_rate": sampling_rate,
                "color": tuple(c / 255 if max(color) > 1 else c for c in color[:3]),
                "meta": {
                    "name": f"{seg.name} ({seg.user_id})",
                    "copick_type": "segmentation",
                    "copick_name": seg.name,
                    "copick_user_id": seg.user_id,
                    "copick_session_id": seg.session_id,
                    "copick_voxel_size": voxel_size,
                },
            }
        )

    return results
