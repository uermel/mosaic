"""Mosaic -> Copick data conversions."""

import numpy as np


def geometry_to_copick_picks(geometry, run, object_name, session_id, user_id):
    """Export a mosaic Geometry as copick picks.

    Parameters
    ----------
    geometry : Geometry
        Mosaic geometry with points and optional quaternions.
    run : CopickRun
        Target copick run.
    object_name : str
        Name of the pickable object.
    session_id : str
        Session identifier.
    user_id : str
        User identifier.

    Returns
    -------
    CopickPicks
        The stored copick picks object.
    """
    from scipy.spatial.transform import Rotation

    points = np.asarray(geometry.points, dtype=np.float64)
    quaternions = geometry.quaternions

    transforms = None
    if quaternions is not None and len(quaternions) > 0:
        # Mosaic uses scalar-first [w,x,y,z], scipy expects [x,y,z,w]
        quats_xyzw = quaternions[:, [1, 2, 3, 0]].astype(np.float64)
        rotation_matrices = Rotation.from_quat(quats_xyzw).as_matrix()

        transforms = np.zeros((len(points), 4, 4), dtype=np.float64)
        transforms[:, :3, :3] = rotation_matrices
        transforms[:, 3, 3] = 1.0

    picks = run.new_picks(object_name, session_id, user_id=user_id, exist_ok=True)
    picks.from_numpy(points, transforms)
    picks.store()
    return picks


def geometry_to_copick_mesh(geometry, run, object_name, session_id, user_id):
    """Export a mosaic Geometry with a TriangularMesh model as a copick mesh.

    Parameters
    ----------
    geometry : Geometry
        Mosaic geometry whose .model is a TriangularMesh.
    run : CopickRun
        Target copick run.
    object_name : str
        Name of the pickable object.
    session_id : str
        Session identifier.
    user_id : str
        User identifier.

    Returns
    -------
    CopickMesh
        The stored copick mesh object.
    """
    import trimesh

    model = geometry.model
    vertices = np.asarray(model.mesh.vertices, dtype=np.float64)
    faces = np.asarray(model.mesh.triangles, dtype=np.int32)

    tmesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    copick_mesh = run.new_mesh(
        object_name, session_id, user_id=user_id, exist_ok=True
    )
    copick_mesh.mesh = tmesh.scene()
    copick_mesh.store()
    return copick_mesh


def geometry_to_copick_segmentation(
    geometry, run, name, session_id, user_id, voxel_size, is_multilabel=False
):
    """Export a mosaic Geometry as a copick segmentation.

    Converts the geometry's point cloud to a binary volume using
    *voxel_size* as the sampling rate, then stores it in the copick run.
    Works with both regular point-set Geometries and SegmentationGeometry
    objects.

    Parameters
    ----------
    geometry : Geometry or SegmentationGeometry
        Mosaic geometry with points.
    run : CopickRun
        Target copick run.
    name : str
        Segmentation name (object name or multilabel identifier).
    session_id : str
        Session identifier.
    user_id : str
        User identifier.
    voxel_size : float
        Voxel size in angstroms.  Used both as the sampling rate for the
        point-to-volume conversion and as metadata stored in copick.
    is_multilabel : bool
        Whether the segmentation is multilabel.

    Returns
    -------
    CopickSegmentation
        The stored copick segmentation object.
    """
    from ..utils import points_to_volume

    points = geometry.points
    volume = points_to_volume(points, sampling_rate=voxel_size, out_dtype=np.uint8)

    seg = run.new_segmentation(
        voxel_size=voxel_size,
        name=name,
        session_id=session_id,
        is_multilabel=is_multilabel,
        user_id=user_id,
        exist_ok=True,
    )
    seg.from_numpy(volume)
    return seg
