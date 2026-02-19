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

"""Data structures for BWX import data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MeshData:
    """Holds mesh data for a single frame.

    Attributes:
        timeline: Timeline value for this frame
        sub_material: Sub-material index
        positions: List of vertex positions (x, y, z)
        normals: List of vertex normals (nx, ny, nz)
        tex_coords: List of UV coordinates (u, v)
        faces: List of face indices (i1, i2, i3)
    """
    timeline: int
    sub_material: int
    positions: list[tuple[float, float, float]]
    normals: list[tuple[float, float, float]]
    tex_coords: list[tuple[float, float]]
    faces: list[tuple[int, int, int]]


@dataclass
class SubMaterialData:
    """Holds sub-material data.

    Attributes:
        diffuse: Diffuse color values
        ambient: Ambient color values
        specular: Specular color values
        highlight: Highlight values
        texture_path: Path to texture file (optional)
    """
    diffuse: tuple[float, ...]
    ambient: tuple[float, ...]
    specular: tuple[float, ...]
    highlight: tuple[float, ...]
    texture_path: Optional[str] = None


@dataclass
class MaterialData:
    """Holds material data.

    Attributes:
        name: Material name
        sub_materials: List of sub-materials
    """
    name: str
    sub_materials: list[SubMaterialData] = field(default_factory=list)


@dataclass
class MatrixFrame:
    """Holds a single matrix animation frame.

    Attributes:
        timeline: Timeline value for this frame
        matrix: 4x4 transformation matrix as flat list of 16 floats
    """
    timeline: int
    matrix: list[float]


@dataclass
class ObjectData:
    """Holds object data.

    Attributes:
        name: Object name
        material_index: Index into materials list
        meshes: List of mesh frames (for vertex animation)
        matrices: List of matrix frames (for matrix animation)
    """
    name: str
    material_index: int
    meshes: list[MeshData] = field(default_factory=list)
    matrices: list[MatrixFrame] = field(default_factory=list)


@dataclass
class CameraData:
    """Holds camera data.

    Attributes:
        name: Camera name
        matrices: List of matrix frames for camera animation
    """
    name: str
    matrices: list[MatrixFrame] = field(default_factory=list)


@dataclass
class BWXData:
    """Root data structure for imported BWX file.

    Attributes:
        materials: List of materials
        objects: List of model objects
        cameras: List of cameras
        filepath: Original file path
        animation_name: Animation name derived from filename
    """
    materials: list[MaterialData] = field(default_factory=list)
    objects: list[ObjectData] = field(default_factory=list)
    cameras: list[CameraData] = field(default_factory=list)
    filepath: str = ""
    animation_name: str = ""
