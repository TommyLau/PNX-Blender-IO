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

"""BWX binary writer.

This module provides the BWXWriter class for serializing BWXData
to binary file format.
"""

from __future__ import annotations

import pathlib
import struct
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_DESCRIPTION,
    DEFAULT_FILE_TYPE,
    DEFAULT_VERSION_SLV1,
    DEFAULT_VERSION_SLV2,
    DIRECTION_MNHX,
    DIRECTION_MSHX,
    EXTRA_VERTICES_SLV2,
    MATRIX_MARKER_SLV1,
    MATRIX_MARKER_SLV2,
    PNX_MAGIC,
    VERTEX_SIZE_SLV2,
    CAMR_MAGIC,
    TIMELINE_BASE,
)
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


class WriterError(RuntimeError):
    """Raised when writing fails."""
    pass


class BWXWriter:
    """Writes BWX data to binary file format.

    Builds binary data directly without using construct library for
    better control over the output format.

    Attributes:
        version: Format version (1 for SLv1, 2 for SLv2)

    Example:
        writer = BWXWriter(bwx_data, version=2)
        writer.write('/path/to/output.PNX')
    """

    def __init__(
        self,
        data: BWXData,
        version: int = 2,
    ) -> None:
        """Initialize the writer.

        Args:
            data: BWXData structure to write
            version: Format version (1 or 2)
        """
        self._data = data
        self._version = version
        self._logger = get_logger(f"{__name__}.BWXWriter")

    @property
    def version(self) -> int:
        """Get the format version."""
        return self._version

    def write(self, filepath: str | Path) -> None:
        """Write BWX data to file.

        Args:
            filepath: Output file path

        Raises:
            WriterError: If writing fails
        """
        self._logger.info(f"Writing to: {filepath}")

        try:
            binary_data = self.build()

            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(binary_data)

            self._logger.info(f"Successfully wrote {len(binary_data)} bytes")
        except Exception as e:
            self._logger.exception("Failed to write file")
            raise WriterError(f"Failed to write file: {e}") from e

    def build(self) -> bytes:
        """Build binary data without writing to file.

        Returns:
            Binary BWX file content
        """
        self._logger.debug("Building binary data")

        # Build all blocks
        blocks_data = bytearray()
        block_count = 0

        # Block 0: SLBWX signature
        blocks_data.extend(self._build_block_0())
        block_count += 1

        # HEAD block
        blocks_data.extend(self._build_head_block())
        block_count += 1

        # MTRL block (materials)
        if self._data.materials:
            blocks_data.extend(self._build_mtrl_block())
            block_count += 1

        # Object block (version-specific)
        if self._data.objects:
            if self._version == 1:
                blocks_data.extend(self._build_obj2_block())
            else:
                blocks_data.extend(self._build_spob_block())
            block_count += 1

        # CAM block (cameras)
        if self._data.cameras:
            blocks_data.extend(self._build_cam_block())
            block_count += 1

        # Build complete file
        output = bytearray()
        output.extend(b'BWXF')
        output.extend(self._build_varint(len(blocks_data) + 10))  # content size (approximate)
        output.extend(self._build_varint(block_count))
        output.extend(blocks_data)
        output.extend(b'FXWB')

        self._logger.debug(f"Built {len(output)} bytes")
        return bytes(output)

    def _build_varint(self, value: int) -> bytes:
        """Build a variable-length integer.

        Args:
            value: Integer value to encode

        Returns:
            Encoded bytes
        """
        if value < 0:
            raise ValueError("VarInt cannot encode negative values")

        result = bytearray()
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    def _build_packed_int(self, value: int) -> bytes:
        """Build a packed integer (same as varint in this implementation).

        Args:
            value: Integer value to encode

        Returns:
            Encoded bytes
        """
        return self._build_varint(value)

    def _build_prefixed_string(self, s: str, encoding: str = 'utf-8') -> bytes:
        """Build a length-prefixed string.

        Args:
            s: String to encode
            encoding: Character encoding

        Returns:
            Encoded bytes with length prefix
        """
        encoded = s.encode(encoding) + b'\x00'
        return self._build_varint(len(encoded)) + encoded

    def _build_bwx_value_int(self, value: int) -> bytes:
        """Build a bwx_value for an integer (type 0x49)."""
        return bytes([0x49]) + struct.pack('<I', value)

    def _build_bwx_value_compact_int(self, value: int) -> bytes:
        """Build a compact bwx_value for a non-negative integer.

        Uses the most compact representation:
        - 0-31: type = value (1 byte)
        - 32-255: type 0x59 (U8) + 1 byte (2 bytes)
        - 256-65535: type 0x57 (U16) + 2 bytes (3 bytes)
        - Larger: type 0x49 (I32) + 4 bytes (5 bytes)
        """
        if 0 <= value < 32:
            # Type itself is the value
            return bytes([value])
        elif 0 <= value <= 255:
            # U8 type
            return bytes([0x59, value])
        elif 0 <= value <= 65535:
            # U16 type
            return bytes([0x57]) + struct.pack('<H', value)
        else:
            # I32 type
            return bytes([0x49]) + struct.pack('<I', value)

    def _build_bwx_value_string(self, value: str) -> bytes:
        """Build a bwx_value for a string (type 0x53)."""
        encoded = value.encode('euc-kr') + b'\x00'
        return bytes([0x53]) + self._build_varint(len(encoded)) + encoded

    def _build_bwx_value_float(self, value: float) -> bytes:
        """Build a bwx_value for a float (type 0x46)."""
        return bytes([0x46]) + struct.pack('<f', value)

    def _build_bwx_value_byte(self, value: int) -> bytes:
        """Build a bwx_value for a byte (type 0x59)."""
        return bytes([0x59, value & 0xFF])

    def _build_bwx_value_data(self, data: bytes) -> bytes:
        """Build a bwx_value for raw data (type 0x42)."""
        return bytes([0x42]) + self._build_varint(len(data)) + data

    def _build_bwx_value_block(self, data: bytes) -> bytes:
        """Build an inline data block (type 0x80+)."""
        length = len(data)
        if length > 0x7F:
            # For larger data, use type 0x42 (VarInt prefixed)
            return self._build_bwx_value_data(data)
        return bytes([0x80 | length]) + data

    def _build_block_0(self) -> bytes:
        """Build the '0' signature block (SLBWX)."""
        # Block name
        name_data = self._build_prefixed_string("0")

        # Block data - just the SLBWX signature as a bwx_value string
        block_data = self._build_bwx_value_string("SLBWX")

        return name_data + block_data

    def _build_head_block(self) -> bytes:
        """Build the HEAD block with file metadata."""
        # Block name
        name_data = self._build_prefixed_string("HEAD")

        # Version
        version_code = DEFAULT_VERSION_SLV1 if self._version == 1 else DEFAULT_VERSION_SLV2

        # Build header content
        inner = bytearray()
        inner.extend(self._build_bwx_value_string("PNX"))
        inner.extend(self._build_bwx_value_string(DEFAULT_DESCRIPTION))
        inner.extend(bytes([0x49]) + struct.pack('<I', PNX_MAGIC))  # magic as I32
        inner.extend(b'W')  # version type marker
        inner.extend(struct.pack('<H', version_code))
        inner.extend(self._build_bwx_value_int(DEFAULT_FILE_TYPE))

        # Build outer array
        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(5))  # count of fields
        outer.extend(inner)

        return name_data + outer

    def _build_mtrl_block(self) -> bytes:
        """Build the MTRL (materials) block."""
        # Block name
        name_data = self._build_prefixed_string("MTRL")

        # Build materials array
        mat_array = bytearray()
        for mat in self._data.materials:
            mat_array.extend(self._build_material(mat))

        # Build outer array
        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(mat_array) + 10))
        outer.extend(self._build_varint(len(self._data.materials)))
        outer.extend(mat_array)

        return name_data + outer

    def _build_material(self, mat: MaterialData) -> bytes:
        """Build a single material structure.

        Structure: 'A' + size + count + "MTRL" + name + sub_materials
        count = 2 (MTRL + name) + len(sub_materials)
        """
        # Build sub-materials
        sub_mat_data = bytearray()
        for sm in mat.sub_materials:
            sub_mat_data.extend(self._build_sub_material(sm))

        # Build material content (MTRL + name + sub_materials)
        content = bytearray()
        content.extend(self._build_bwx_value_string("MTRL"))
        content.extend(self._build_bwx_value_string(mat.name))
        content.extend(sub_mat_data)

        # Build material entry (without extra wrapper)
        entry = bytearray()
        entry.extend(b'A')
        entry.extend(self._build_varint(len(content) + 10))
        entry.extend(self._build_varint(len(mat.sub_materials) + 2))  # MTRL + name + sub_materials
        entry.extend(content)

        return bytes(entry)

    def _build_sub_material(self, sm: SubMaterialData) -> bytes:
        """Build a sub-material structure."""
        inner = bytearray()
        inner.extend(self._build_bwx_value_string("SUBMTRL"))
        inner.extend(self._build_bwx_value_int(self._color_to_int(sm.diffuse)))
        inner.extend(self._build_bwx_value_int(self._color_to_int(sm.ambient)))
        inner.extend(self._build_bwx_value_int(self._color_to_int(sm.specular)))
        inner.extend(self._build_bwx_value_float(0.0))  # some_float
        inner.extend(self._build_bwx_value_float(sm.highlight[0] if sm.highlight else 0.0))
        inner.extend(self._build_bwx_value_int(0))  # most_1
        inner.extend(self._build_bwx_value_int(0))  # unknown

        count = 8
        if sm.texture_path:
            inner.extend(self._build_texture(sm.texture_path))
            count += 1

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(count))
        outer.extend(inner)

        return bytes(outer)

    def _build_texture(self, texture_path: str) -> bytes:
        """Build a texture structure."""
        filename = pathlib.Path(texture_path).name

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("TEX"))
        inner.extend(self._build_bwx_value_int(0))  # most_0
        inner.extend(self._build_bwx_value_string(filename))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(3))
        outer.extend(inner)

        return bytes(outer)

    @staticmethod
    def _color_to_int(color: tuple) -> int:
        """Convert color tuple to integer (BGRA format)."""
        if len(color) >= 4:
            r, g, b, a = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255), int(color[3] * 255)
        else:
            r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            a = 255
        return (a << 24) | (r << 16) | (g << 8) | b

    def _build_obj2_block(self) -> bytes:
        """Build the OBJ2 block (SLv1 format)."""
        name_data = self._build_prefixed_string("OBJ2")

        obj_array = bytearray()
        for obj in self._data.objects:
            obj_array.extend(self._build_v1_object(obj))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(obj_array) + 10))
        outer.extend(self._build_varint(len(self._data.objects)))
        outer.extend(obj_array)

        return name_data + outer

    def _build_spob_block(self) -> bytes:
        """Build the SPOB block (SLv2 format)."""
        name_data = self._build_prefixed_string("SPOB")

        obj_array = bytearray()
        for obj in self._data.objects:
            obj_array.extend(self._build_v2_object(obj))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(obj_array) + 10))
        outer.extend(self._build_varint(len(self._data.objects)))
        outer.extend(obj_array)

        return name_data + outer

    def _build_v1_object(self, obj: ObjectData) -> bytes:
        """Build a single SLv1 object structure.

        Structure: 'A' + size + count + "OBJ2" + name + unknown1 + material + unknown2 + unknown3 + direction + meshes + matrices + sfx
        """
        # Build meshes
        mesh_data = self._build_v1_meshes(obj)

        # Build matrices
        matrix_data = self._build_v1_matrices(obj)

        # Determine face winding
        direction = self._determine_face_winding(obj)

        # Build content (everything after 'A' + size + count)
        content = bytearray()
        content.extend(self._build_bwx_value_string("OBJ2"))
        content.extend(self._build_bwx_value_string(obj.name))
        content.extend(self._build_bwx_value_compact_int(0))  # unknown1
        content.extend(self._build_bwx_value_compact_int(obj.material_index))
        content.extend(self._build_bwx_value_compact_int(0))  # unknown2
        content.extend(self._build_bwx_value_compact_int(0))  # unknown3
        content.extend(b'I')  # direction type marker
        content.extend(struct.pack('<I', direction))
        content.extend(mesh_data)
        content.extend(matrix_data)
        content.extend(self._build_bwx_value_compact_int(0))  # sfx

        # Build complete object entry
        # count = 10 fields (OBJ2 + name + 4 unknowns + direction + meshes + matrices + sfx)
        entry = bytearray()
        entry.extend(b'A')
        entry.extend(self._build_varint(len(content) + 10))  # size (approximate with buffer)
        entry.extend(self._build_varint(10))  # count of fields
        entry.extend(content)

        return bytes(entry)

    def _build_v2_object(self, obj: ObjectData) -> bytes:
        """Build a single SLv2 object structure.

        Structure: 'A' + size + count + "DXOBJ" + name + unknown1 + material + unknown2 + unknown3 + direction + meshes + matrices + sfx
        """
        mesh_data = self._build_v2_meshes(obj)
        matrix_data = self._build_v2_matrices(obj)
        direction = self._determine_face_winding(obj)

        # Build content
        content = bytearray()
        content.extend(self._build_bwx_value_string("DXOBJ"))
        content.extend(self._build_bwx_value_string(obj.name))
        content.extend(self._build_bwx_value_compact_int(0))  # unknown1
        content.extend(self._build_bwx_value_compact_int(obj.material_index))
        content.extend(self._build_bwx_value_compact_int(0))  # unknown2
        content.extend(self._build_bwx_value_compact_int(0))  # unknown3
        content.extend(b'I')
        content.extend(struct.pack('<I', direction))
        content.extend(mesh_data)
        content.extend(matrix_data)
        content.extend(self._build_bwx_value_compact_int(0))  # sfx

        # Build complete object entry
        entry = bytearray()
        entry.extend(b'A')
        entry.extend(self._build_varint(len(content) + 10))
        entry.extend(self._build_varint(10))
        entry.extend(content)

        return bytes(entry)

    def _build_v1_meshes(self, obj: ObjectData) -> bytes:
        """Build SLv1 mesh array."""
        # Group meshes by sub_material
        mesh_groups: dict[int, list[MeshData]] = {}
        for mesh in obj.meshes:
            sub_mat = mesh.sub_material
            if sub_mat not in mesh_groups:
                mesh_groups[sub_mat] = []
            mesh_groups[sub_mat].append(mesh)

        mesh_array = bytearray()
        for sub_mat, meshes in mesh_groups.items():
            mesh_array.extend(self._build_v1_mesh(meshes, sub_mat))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(mesh_array) + 10))
        outer.extend(self._build_varint(len(mesh_groups)))
        outer.extend(mesh_array)

        return bytes(outer)

    def _build_v1_mesh(self, meshes: list[MeshData], sub_material: int) -> bytes:
        """Build a single SLv1 mesh with frames."""
        base_mesh = meshes[0]

        # Build sub-mesh frames
        sub_mesh_array = bytearray()
        for mesh in meshes:
            sub_mesh_array.extend(self._build_v1_mesh_frame(mesh))

        # Build sub-material array
        sub_mat_array = bytearray()
        sub_mat_array.extend(b'A')
        sub_mat_array.extend(self._build_varint(10))
        sub_mat_array.extend(self._build_varint(1))
        sub_mat_array.extend(self._build_bwx_value_compact_int(sub_material))

        # Build index buffer with compact integers
        index_data = bytearray()
        index_count = len(base_mesh.faces) * 3
        for face in base_mesh.faces:
            for idx in face:
                index_data.extend(self._build_bwx_value_compact_int(idx))

        index_array = bytearray()
        index_array.extend(b'A')
        index_array.extend(self._build_varint(len(index_data) + 10))
        index_array.extend(self._build_varint(index_count))
        index_array.extend(index_data)

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("MESH"))
        inner.extend(b'A')
        inner.extend(self._build_varint(len(sub_mesh_array) + 10))
        inner.extend(self._build_varint(len(meshes)))
        inner.extend(sub_mesh_array)
        inner.extend(sub_mat_array)
        inner.extend(index_array)
        inner.extend(self._build_bwx_value_compact_int(0))  # unknown1
        inner.extend(self._build_bwx_value_compact_int(0))  # unknown2
        inner.extend(self._build_bwx_value_compact_int(0))  # unknown3
        inner.extend(self._build_bwx_value_compact_int(0))  # unknown_20

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(10))
        outer.extend(inner)

        return bytes(outer)

    def _build_v1_mesh_frame(self, mesh: MeshData) -> bytes:
        """Build a single SLv1 mesh frame."""
        # Build vertex data blocks
        vertex_blocks = bytearray()
        for pos in mesh.positions:
            pos_data = struct.pack('<3f', *pos)
            vertex_blocks.extend(self._build_bwx_value_block(pos_data))

        uv_blocks = bytearray()
        for uv in mesh.tex_coords:
            uv_data = struct.pack('<2f', *uv)
            uv_blocks.extend(self._build_bwx_value_block(uv_data))

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("MESHF"))
        inner.extend(self._build_bwx_value_int(mesh.timeline))

        # Vertex array
        inner.extend(b'A')
        inner.extend(self._build_varint(len(vertex_blocks) + 10))
        inner.extend(self._build_varint(len(mesh.positions)))
        inner.extend(vertex_blocks)

        # UV array
        inner.extend(b'A')
        inner.extend(self._build_varint(len(uv_blocks) + 10))
        inner.extend(self._build_varint(len(mesh.tex_coords)))
        inner.extend(uv_blocks)

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(5))
        outer.extend(inner)

        return bytes(outer)

    def _build_v2_meshes(self, obj: ObjectData) -> bytes:
        """Build SLv2 mesh array."""
        mesh_groups: dict[int, list[MeshData]] = {}
        for mesh in obj.meshes:
            sub_mat = mesh.sub_material
            if sub_mat not in mesh_groups:
                mesh_groups[sub_mat] = []
            mesh_groups[sub_mat].append(mesh)

        mesh_array = bytearray()
        for sub_mat, meshes in mesh_groups.items():
            mesh_array.extend(self._build_v2_mesh(meshes, sub_mat))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(mesh_array) + 10))
        outer.extend(self._build_varint(len(mesh_groups)))
        outer.extend(mesh_array)

        return bytes(outer)

    def _build_v2_mesh(self, meshes: list[MeshData], sub_material: int) -> bytes:
        """Build a single SLv2 mesh with frames."""
        base_mesh = meshes[0]

        sub_mesh_array = bytearray()
        for mesh in meshes:
            sub_mesh_array.extend(self._build_v2_mesh_frame(mesh))

        index_count = len(base_mesh.faces) * 3
        index_data = struct.pack(f'<{index_count}H', *[idx for face in base_mesh.faces for idx in face])

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("DXMESH"))
        inner.extend(self._build_bwx_value_int(sub_material))
        inner.extend(b'A')
        inner.extend(self._build_varint(len(sub_mesh_array) + 10))
        inner.extend(self._build_varint(len(meshes)))
        inner.extend(sub_mesh_array)
        inner.extend(self._build_bwx_value_int(index_count))
        inner.extend(self._build_bwx_value_data(index_data))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(6))
        outer.extend(inner)

        return bytes(outer)

    def _build_v2_mesh_frame(self, mesh: MeshData) -> bytes:
        """Build a single SLv2 mesh frame with interleaved vertex data."""
        vertex_buffer = self._build_v2_vertex_buffer(mesh)
        vertex_count = len(mesh.positions) + EXTRA_VERTICES_SLV2

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("DXMESHF"))
        inner.extend(self._build_bwx_value_int(mesh.timeline))
        inner.extend(self._build_bwx_value_int(0x15))  # vertex type
        inner.extend(self._build_bwx_value_int(vertex_count))
        inner.extend(self._build_bwx_value_int(VERTEX_SIZE_SLV2))
        inner.extend(self._build_bwx_value_data(vertex_buffer))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(6))
        outer.extend(inner)

        return bytes(outer)

    def _build_v2_vertex_buffer(self, mesh: MeshData) -> bytes:
        """Build interleaved vertex buffer for SLv2 format."""
        buffer = bytearray()

        for i in range(len(mesh.positions)):
            pos = mesh.positions[i]
            buffer.extend(struct.pack('<3f', *pos))

            if i < len(mesh.normals) and mesh.normals[i]:
                normal = mesh.normals[i]
            else:
                normal = (0.0, 0.0, 1.0)
            buffer.extend(struct.pack('<3f', *normal))

            if i < len(mesh.tex_coords) and mesh.tex_coords[i]:
                uv = mesh.tex_coords[i]
                flipped_uv = (uv[0], 1.0 - uv[1])
            else:
                flipped_uv = (0.0, 0.0)
            buffer.extend(struct.pack('<2f', *flipped_uv))

        # Add 2 extra dummy vertices
        for _ in range(EXTRA_VERTICES_SLV2):
            buffer.extend(struct.pack('<8f', 0, 0, 0, 0, 0, 0, 0, 0))

        return bytes(buffer)

    def _build_v1_matrices(self, obj: ObjectData) -> bytes:
        """Build SLv1 matrix array."""
        return self._build_matrices(obj, MATRIX_MARKER_SLV1, include_unknown=False)

    def _build_v2_matrices(self, obj: ObjectData) -> bytes:
        """Build SLv2 matrix array."""
        return self._build_matrices(obj, MATRIX_MARKER_SLV2, include_unknown=True)

    def _build_matrices(self, obj: ObjectData, marker: bytes, include_unknown: bool) -> bytes:
        """Build matrix array structure.

        Structure is doubly nested:
        - Outer array: 'A' + size + count + [matrix_structs]
        - Inner matrix struct: 'A' + size + count + "MATRIX" + frames

        The outer size = inner_wrapper length (because construct uses this.size - count.sizeof())
        """
        if not obj.matrices:
            # Empty matrix array
            outer = bytearray()
            outer.extend(b'A')
            outer.extend(self._build_varint(10))
            outer.extend(self._build_varint(0))
            return bytes(outer)

        # Build matrix frames
        matrix_frames = bytearray()
        for mf in obj.matrices:
            frame = bytearray()
            frame.extend(marker)
            frame.extend(struct.pack('<I', mf.timeline))
            for val in mf.matrix:
                frame.extend(struct.pack('<f', val))
            if include_unknown:
                frame.extend(struct.pack('<7f', 0, 0, 0, 0, 0, 0, 0))
            matrix_frames.extend(frame)

        # Build inner matrix struct content (MATRIX string + frames)
        inner_content = bytearray()
        inner_content.extend(self._build_bwx_value_string("MATRIX"))
        inner_content.extend(matrix_frames)

        # Build inner wrapper: 'A' + size + count + content
        inner_count = len(obj.matrices) + 1  # count-1 matrices in construct, so count = frames + 1
        inner_wrapper = bytearray()
        inner_wrapper.extend(b'A')  # 1 byte
        inner_wrapper.extend(self._build_varint(len(inner_content) + 10))  # size
        inner_wrapper.extend(self._build_varint(inner_count))  # count
        inner_wrapper.extend(inner_content)

        # Build outer wrapper: 'A' + size + count + inner_wrapper
        # The size should be the total length of everything after the outer 'A'
        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner_wrapper)))  # size = inner wrapper length
        outer.extend(self._build_varint(1))  # count = 1 (one matrix struct)
        outer.extend(inner_wrapper)

        return bytes(outer)

    def _build_cam_block(self) -> bytes:
        """Build the CAM (camera) block."""
        name_data = self._build_prefixed_string("CAM")

        cam_array = bytearray()
        for cam in self._data.cameras:
            cam_array.extend(self._build_camera(cam))

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(cam_array) + 10))
        outer.extend(self._build_varint(len(self._data.cameras)))
        outer.extend(cam_array)

        return name_data + outer

    def _build_camera(self, cam: CameraData) -> bytes:
        """Build camera structure with animation."""
        matrix_frames = bytearray()
        for mf in cam.matrices:
            frame = bytearray()
            frame.extend(b'B')
            frame.extend(self._build_varint(4 + 64 + 64 + 24 + 24))  # size
            frame.extend(struct.pack('<I', mf.timeline))
            for val in mf.matrix:
                frame.extend(struct.pack('<f', val))
            for _ in range(16):
                frame.extend(struct.pack('<f', 0.0))  # target matrix
            for _ in range(6):
                frame.extend(struct.pack('<f', 0.0))  # unknown vectors
            matrix_frames.extend(frame)

        inner = bytearray()
        inner.extend(self._build_bwx_value_string("CAM"))
        inner.extend(self._build_bwx_value_string(cam.name))
        inner.extend(self._build_bwx_value_int(CAMR_MAGIC))
        inner.extend(self._build_bwx_value_int(0))  # unknown
        inner.extend(matrix_frames)

        outer = bytearray()
        outer.extend(b'A')
        outer.extend(self._build_varint(len(inner) + 10))
        outer.extend(self._build_varint(len(cam.matrices) + 4))
        outer.extend(inner)

        return bytes(outer)

    def _determine_face_winding(self, obj: ObjectData) -> int:
        """Determine if face winding is MSHX (reversed) or MNHX (normal)."""
        return DIRECTION_MNHX
