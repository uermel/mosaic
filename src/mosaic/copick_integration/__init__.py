"""Copick integration for mosaic.

Provides bidirectional data flow between copick projects and mosaic,
supporting picks (point clouds), meshes, and segmentations.

Requires the optional ``copick`` dependency:
    pip install mosaic-gui[copick]
"""

from ._reader import (
    copick_picks_to_geometry_data,
    copick_mesh_to_geometry_data,
    copick_segmentation_to_geometries,
)
from ._writer import (
    geometry_to_copick_picks,
    geometry_to_copick_mesh,
    geometry_to_copick_segmentation,
)
from ._uri import (
    parse_segmentation_uri,
    build_segmentation_uri,
    resolve_segmentation,
)
from ._dialog import CopickBrowserDialog

__all__ = [
    "copick_picks_to_geometry_data",
    "copick_mesh_to_geometry_data",
    "copick_segmentation_to_geometries",
    "geometry_to_copick_picks",
    "geometry_to_copick_mesh",
    "geometry_to_copick_segmentation",
    "parse_segmentation_uri",
    "build_segmentation_uri",
    "resolve_segmentation",
    "CopickBrowserDialog",
]
