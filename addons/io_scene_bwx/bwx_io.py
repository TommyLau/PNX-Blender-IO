# Copyright 2022-2026 Tommy Lau @ SLODT
#
# Licensed under the GPL License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.gnu.org/licenses/gpl-3.0.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""BWX file importer.

This module provides the BWXImporter class for parsing ShiningLore
BNX/PNX binary files into structured Python dataclasses.
"""

from __future__ import annotations

import pathlib
from pathlib import Path
from typing import Any

from .bwx_construct import (
    Array,
    EnumIntegerString,
    Float32l,
    Int16ul,
    bwx_dx_vertex_struct,
    bwx_struct,
    get_block,
)
from .constants import BYPASS_OBJECT_PREFIXES, SUPPORTED_VERSIONS
from .logging_utils import get_logger
from .types import (
    BWXData,
    CameraData,
    MaterialData,
    MatrixFrame,
    MeshData,
    ObjectData,
    SubMaterialData,
)


class ImportError(RuntimeError):
    """Raised when import fails.

    This exception is raised when the BWX file cannot be read or parsed,
    such as when the file is not found, has an unsupported version,
    or contains malformed data.
    """
    pass


class BWXImporter:
    """BWX file importer class.

    This class handles parsing ShiningLore BNX/PNX binary files and
    extracting materials, objects, and cameras into structured data.

    Attributes:
        data: The parsed BWX data structure

    Example:
        importer = BWXImporter('/path/to/file.PNX', {})
        importer.read()
        importer.checks()
        # Access parsed data via importer.data
    """

    def __init__(self, filepath: str | Path, import_settings: dict[str, Any]) -> None:
        """Initialize the importer.

        Args:
            filepath: Path to the BWX file to import
            import_settings: Dictionary of import settings (currently unused)
        """
        self._filepath = Path(filepath)
        self._settings = import_settings
        self._data = BWXData(
            filepath=str(filepath),
            animation_name=self._filepath.stem.split('_')[-1].lower()
        )
        self._logger = get_logger(f"{__name__}.BWXImporter")
        self._sl_version: int = 0

    @property
    def data(self) -> BWXData:
        """Get the imported data.

        Returns:
            The parsed BWX data structure
        """
        return self._data

    @property
    def filename(self) -> str:
        """Get the import file path (for backward compatibility).

        Returns:
            The file path as a string
        """
        return str(self._filepath)

    @property
    def materials(self) -> list[MaterialData]:
        """Get materials list (for backward compatibility).

        Returns:
            List of material data
        """
        return self._data.materials

    @property
    def model(self) -> list[ObjectData]:
        """Get model objects list (for backward compatibility).

        Returns:
            List of object data
        """
        return self._data.objects

    @property
    def camera(self) -> list[CameraData]:
        """Get cameras list (for backward compatibility).

        Returns:
            List of camera data
        """
        return self._data.cameras

    def checks(self) -> None:
        """Perform validation checks on the imported data.

        This method is called after read() to validate the parsed data.
        Currently a no-op but can be extended for validation.
        """
        self._logger.debug("Running validation checks")
        # Placeholder for validation logic
        pass

    def read(self) -> None:
        """Read and parse the BWX file.

        Raises:
            ImportError: If the file cannot be read or parsed
        """
        self._logger.info(f"Reading file: {self._filepath}")

        try:
            content = self._filepath.read_bytes()
            self._parse(memoryview(content))
            self._logger.info(
                f"File parsed successfully: {len(self._data.materials)} materials, "
                f"{len(self._data.objects)} objects, {len(self._data.cameras)} cameras"
            )
        except FileNotFoundError:
            raise ImportError(f"File not found: {self._filepath}")
        except PermissionError:
            raise ImportError(f"Permission denied: {self._filepath}")
        except Exception as e:
            self._logger.exception("Failed to parse file")
            raise ImportError(f"Failed to read file: {e}") from e

    def _parse(self, content: memoryview) -> None:
        """Parse the binary content.

        Args:
            content: Memory view of the file content
        """
        bwx = bwx_struct.parse(content)
        head = get_block(bwx, "HEAD")

        if head is None:
            raise ImportError("Invalid BWX file: missing HEAD block")

        # Determine version
        version_str = str(head.version)
        if version_str == 'SLv1':
            self._sl_version = 1
        elif version_str == 'SLv2':
            self._sl_version = 2
        else:
            raise ImportError(f"Unsupported version: {version_str}")

        self._logger.debug(f"Detected version: {version_str}")

        # Parse all sections
        self._parse_materials(bwx)
        self._parse_objects(bwx)
        self._parse_cameras(bwx)

    def _parse_materials(self, bwx) -> None:
        """Parse materials from BWX data.

        Args:
            bwx: Parsed BWX structure
        """
        mtrl = get_block(bwx, "MTRL")
        if mtrl is None:
            self._logger.warning("No MTRL block found")
            return

        texture_path = self._filepath.parent

        for m in mtrl.material:
            name = m.material_name.value
            sub_materials: list[SubMaterialData] = []

            for sm in m.sub_material:
                texture_file = None
                if sm.texture:
                    texture_file = str(
                        texture_path.joinpath(
                            pathlib.PureWindowsPath(sm.texture.filename.value).name
                        ).resolve()
                    )

                sub_materials.append(SubMaterialData(
                    diffuse=sm.diffuse.value,
                    ambient=sm.ambient.value,
                    specular=sm.specular.value,
                    highlight=sm.highlight.value,
                    texture_path=texture_file
                ))

            self._data.materials.append(MaterialData(
                name=name,
                sub_materials=sub_materials
            ))

        self._logger.debug(f"Parsed {len(self._data.materials)} materials")

    def _parse_objects(self, bwx) -> None:
        """Parse objects from BWX data.

        Args:
            bwx: Parsed BWX structure
        """
        # Get the correct object block based on version
        if self._sl_version == 1:
            model = get_block(bwx, "OBJ2")
        else:
            model = get_block(bwx, "SPOB")

        if model is None:
            self._logger.warning("No object block found")
            return

        for o in model.object:
            name = o.name.value
            material = o.material.value

            # Skip bypass objects
            if any(name.startswith(prefix) for prefix in BYPASS_OBJECT_PREFIXES):
                self._logger.debug(f"Skipping bypass object: {name}")
                continue

            meshes = self._parse_meshes(o)
            matrices = self._parse_matrices(o)

            self._data.objects.append(ObjectData(
                name=name,
                material_index=material,
                meshes=meshes,
                matrices=matrices
            ))

        self._logger.debug(f"Parsed {len(self._data.objects)} objects")

    def _parse_meshes(self, obj) -> list[MeshData]:
        """Parse meshes from an object.

        Args:
            obj: Object structure from BWX

        Returns:
            List of mesh data for each frame
        """
        meshes: list[MeshData] = []

        for m in obj.mesh:
            for sm in m.sub_mesh:
                if self._sl_version == 1:
                    mesh = self._parse_v1_mesh(m, sm)
                else:
                    mesh = self._parse_v2_mesh(m, sm)

                if mesh:
                    meshes.append(mesh)

        return meshes

    def _parse_v1_mesh(self, m, sm) -> MeshData:
        """Parse a version 1 mesh.

        Args:
            m: Mesh structure
            sm: Sub-mesh structure

        Returns:
            MeshData instance
        """
        # Only retrieve the first face's sub material id as texture for whole mesh
        sub_material = m.sub_material[0].value
        positions = [Array(3, Float32l).parse(v.value)[:] for v in sm.vertex_buffer]
        normals: list[tuple[float, float, float]] = []
        tex_coords = [Array(2, Float32l).parse(u.value)[:] for u in sm.uv_buffer]
        indices = iter([i.value for i in m.index_buffer])

        # Flip if direction = "MSHX"
        flip = obj_direction_is_mshx(m)
        faces = [
            (a, c, b) if flip else (a, b, c)
            for a, b, c in zip(indices, indices, indices)
        ]

        return MeshData(
            timeline=sm.timeline.value,
            sub_material=sub_material,
            positions=positions,
            normals=normals,
            tex_coords=tex_coords,
            faces=faces
        )

    def _parse_v2_mesh(self, m, sm) -> MeshData:
        """Parse a version 2 mesh.

        Args:
            m: Mesh structure
            sm: Sub-mesh structure

        Returns:
            MeshData instance
        """
        # Version 2 uses one int to represent the sub_material value
        sub_material = m.sub_material.value

        # There are two more vertices which are unknown
        # Remember to write two more back when exporting
        vertex_buffer = Array(
            sm.vertex_count.value,
            bwx_dx_vertex_struct
        ).parse(sm.vertex_buffer.value)

        # Exclude the last 2 dummy vertices (SLv2 format adds 2 extra vertices)
        actual_vertex_count = len(vertex_buffer) - 2 if len(vertex_buffer) > 2 else len(vertex_buffer)

        positions = [v.positions[:] for v in vertex_buffer[:actual_vertex_count]]
        normals = [v.normals[:] for v in vertex_buffer[:actual_vertex_count]]
        # Flip UV y-coordinate for v2
        tex_coords = [[v.tex_coords[0], 1 - v.tex_coords[1]] for v in vertex_buffer[:actual_vertex_count]]
        indices = iter(Array(m.index_count.value, Int16ul).parse(m.index_buffer.value))

        # Flip if direction = "MSHX"
        flip = obj_direction_is_mshx(m)
        faces = [
            (a, c, b) if flip else (a, b, c)
            for a, b, c in zip(indices, indices, indices)
        ]

        return MeshData(
            timeline=sm.timeline.value,
            sub_material=sub_material,
            positions=positions,
            normals=normals,
            tex_coords=tex_coords,
            faces=faces
        )

    def _parse_matrices(self, obj) -> list[MatrixFrame]:
        """Parse matrices from an object.

        Args:
            obj: Object structure from BWX

        Returns:
            List of matrix frames
        """
        # Assume have only ONE matrix group - obj.matrix[0]
        if not obj.matrix:
            return []

        return [
            MatrixFrame(timeline=m.timeline, matrix=m.matrix[:])
            for m in obj.matrix[0].matrices
        ]

    def _parse_cameras(self, bwx) -> None:
        """Parse cameras from BWX data.

        Args:
            bwx: Parsed BWX structure
        """
        cam = get_block(bwx, "CAM")
        if cam is None:
            return

        for c in cam.camera:
            name = c.name.value
            matrices = [
                MatrixFrame(timeline=m.timeline, matrix=m.camera[:])
                for m in c.matrix
            ]

            self._data.cameras.append(CameraData(
                name=name,
                matrices=matrices
            ))

        self._logger.debug(f"Parsed {len(self._data.cameras)} cameras")


def obj_direction_is_mshx(obj) -> bool:
    """Check if object direction is MSHX.

    Args:
        obj: Object structure to check

    Returns:
        True if direction is MSHX, False otherwise
    """
    try:
        return obj.direction.value == EnumIntegerString('MSHX')
    except (AttributeError, KeyError):
        return False
