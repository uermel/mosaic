"""URI handling for copick segmentations.

URI format: copick://{config_path}#{run_name}/Segmentations/{voxel_size}/{user_id}_{session_id}_{name}.zarr
"""

from urllib.parse import urlparse


def parse_segmentation_uri(uri):
    """Parse a copick segmentation URI into its components.

    Parameters
    ----------
    uri : str
        URI string in the format:
        copick://{config_path}#{run_name}/Segmentations/{voxel_size}/{user_id}_{session_id}_{name}.zarr

    Returns
    -------
    dict
        Dictionary with keys: config_path, run_name, voxel_size, user_id,
        session_id, name.

    Raises
    ------
    ValueError
        If the URI format is invalid.
    """
    if not uri.startswith("copick://"):
        raise ValueError(f"URI must start with 'copick://': {uri}")

    parsed = urlparse(uri)
    config_path = parsed.netloc + parsed.path.split("#")[0] if parsed.path else parsed.netloc

    fragment = parsed.fragment
    if not fragment:
        # Try splitting on # manually for cases urlparse doesn't handle
        if "#" in uri:
            config_path, fragment = uri[len("copick://"):].split("#", 1)
        else:
            raise ValueError(f"URI must contain a '#' fragment: {uri}")

    parts = fragment.split("/")
    if len(parts) < 4 or parts[1] != "Segmentations":
        raise ValueError(
            f"URI fragment must follow: "
            f"{{run_name}}/Segmentations/{{voxel_size}}/{{filename}}.zarr, got: {fragment}"
        )

    run_name = parts[0]
    voxel_size = float(parts[2])
    filename = parts[3]

    if filename.endswith(".zarr"):
        filename = filename[:-5]

    # filename format: {user_id}_{session_id}_{name}
    filename_parts = filename.split("_", 2)
    if len(filename_parts) < 3:
        raise ValueError(
            f"Filename must follow {{user_id}}_{{session_id}}_{{name}}.zarr, got: {parts[3]}"
        )

    return {
        "config_path": config_path,
        "run_name": run_name,
        "voxel_size": voxel_size,
        "user_id": filename_parts[0],
        "session_id": filename_parts[1],
        "name": filename_parts[2],
    }


def build_segmentation_uri(config_path, run_name, voxel_size, user_id, session_id, name):
    """Build a copick segmentation URI from components.

    Parameters
    ----------
    config_path : str
        Path to copick config JSON file.
    run_name : str
        Name of the copick run.
    voxel_size : float
        Voxel size in angstroms.
    user_id : str
        User identifier.
    session_id : str
        Session identifier.
    name : str
        Segmentation name.

    Returns
    -------
    str
        The constructed copick URI.
    """
    return (
        f"copick://{config_path}#{run_name}/Segmentations/"
        f"{voxel_size}/{user_id}_{session_id}_{name}.zarr"
    )


def resolve_segmentation(uri):
    """Resolve a copick segmentation URI to a CopickSegmentation object.

    Parameters
    ----------
    uri : str
        Copick segmentation URI.

    Returns
    -------
    CopickSegmentation or None
        The resolved segmentation, or None if not found.

    Raises
    ------
    ImportError
        If copick is not installed.
    """
    from copick import from_file

    params = parse_segmentation_uri(uri)
    root = from_file(params["config_path"])
    run = root.get_run(params["run_name"])
    if run is None:
        return None

    segs = run.get_segmentations(
        user_id=params["user_id"],
        session_id=params["session_id"],
        name=params["name"],
        voxel_size=params["voxel_size"],
    )
    return segs[0] if segs else None
