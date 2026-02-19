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

"""BWX data extractor from Blender scenes.

This module provides the BWXExtractor class for extracting data from
Blender scenes into the BWXData structure for export.
"""

from __future__ import annotations

import pathlib
from pathlib import Path
from typing import Any

import bpy
from mathutils import Matrix

from .constants import TIMELINE_BASE
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


class ExportError(RuntimeError):
    """Raised when export fails.

    This exception is raised when the Blender scene cannot be exported,
    such as when no objects are selected or data is invalid.
    """
    pass


class BWXExtractor:
    """Extracts BWX-compatible data from Blender scene.

    This class scans the Blender scene and converts objects, materials,
    animations, and cameras into the BWXData structure used for export.

    Attributes:
        data: The extracted BWXData structure

    Example:
        extractor = BWXExtractor(context, {'use_selection': True})
        extractor.extract()
        bwx_data = extractor.data
    """

    def __init__(
        self,
        context: bpy.types.Context,
        export_settings: dict[str, Any],
    ) -> None:
        """Initialize the extractor.

        Args:
            context: Blender context
            export_settings: Export settings dictionary
        """
        self._context = context
        self._settings = export_settings
        self._data = BWXData()
        self._logger = get_logger(f"{__name__}.BWXExtractor")

        # Material tracking for index mapping
        self._material_index_map: dict[str, int] = {}
        self._sub_material_index_map: dict[tuple[int, str], int] = {}

        # Object tracking
        self._processed_objects: set[str] = set()

    @property
    def data(self) -> BWXData:
        """Get the extracted data.

        Returns:
            The BWXData structure
        """
        return self._data

    def extract(self) -> None:
        """Extract all data from the Blender scene.

        Main extraction workflow:
        1. Extract materials from objects
        2. Extract mesh objects with geometry
        3. Extract vertex animations from shape keys
        4. Extract matrix animations from NLA tracks
        5. Extract camera objects
        """
        self._logger.info("Starting data extraction")

        try:
            self._extract_materials()
            self._extract_objects()

            if self._settings.get('export_cameras', True):
                self._extract_cameras()

            self._logger.info(
                f"Extraction complete: {len(self._data.materials)} materials, "
                f"{len(self._data.objects)} objects, {len(self._data.cameras)} cameras"
            )
        except Exception as e:
            self._logger.exception("Failed to extract data")
            raise ExportError(f"Failed to extract data: {e}") from e

    def _get_objects(self) -> list[bpy.types.Object]:
        """Get objects to export based on settings.

        Returns:
            List of objects to export
        """
        use_selection = self._settings.get('use_selection', False)

        if use_selection:
            return [ob for ob in self._context.selected_objects if ob.type == 'MESH']
        else:
            return [ob for ob in self._context.scene.objects if ob.type == 'MESH']

    def _get_camera_objects(self) -> list[bpy.types.Object]:
        """Get camera objects to export.

        Returns:
            List of camera objects to export
        """
        use_selection = self._settings.get('use_selection', False)

        if use_selection:
            return [ob for ob in self._context.selected_objects if ob.type == 'CAMERA']
        else:
            return [ob for ob in self._context.scene.objects if ob.type == 'CAMERA']

    def _extract_materials(self) -> None:
        """Extract materials from Blender objects.

        Builds a unique list of materials and sub-materials from all
        objects to be exported.
        """
        objects = self._get_objects()

        for ob in objects:
            for slot_idx, slot in enumerate(ob.material_slots):
                if slot.material is None:
                    continue

                mat = slot.material
                mat_name = mat.name

                # Check if material already processed
                if mat_name not in self._material_index_map:
                    mat_idx = len(self._data.materials)
                    self._material_index_map[mat_name] = mat_idx

                    sub_materials = self._extract_sub_materials(mat)
                    self._data.materials.append(MaterialData(
                        name=mat_name,
                        sub_materials=sub_materials
                    ))

                    # Build sub-material index map
                    for sub_idx, sub_mat in enumerate(sub_materials):
                        key = (mat_idx, sub_mat.texture_path or '')
                        self._sub_material_index_map[key] = sub_idx

        self._logger.debug(f"Extracted {len(self._data.materials)} materials")

    def _extract_sub_materials(self, mat: bpy.types.Material) -> list[SubMaterialData]:
        """Extract sub-materials from a Blender material.

        Args:
            mat: Blender material

        Returns:
            List of SubMaterialData
        """
        sub_materials = []

        # Extract texture from Principled BSDF
        texture_path = None
        highlight = 0.0

        if mat.use_nodes:
            # Find Principled BSDF node
            bsdf = None
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    bsdf = node
                    break

            if bsdf:
                # Get base color texture
                base_color_input = bsdf.inputs.get('Base Color')
                if base_color_input and base_color_input.links:
                    link = base_color_input.links[0]
                    if link.from_node.type == 'TEX_IMAGE':
                        img = link.from_node.image
                        if img:
                            texture_path = bpy.path.abspath(img.filepath)

                # Get emission for highlight effect
                emission_input = bsdf.inputs.get('Emission')
                if emission_input:
                    # If emission has a non-zero value, consider it a highlight
                    if hasattr(emission_input, 'default_value'):
                        emit = emission_input.default_value
                        if len(emit) >= 3:
                            highlight = max(emit[0], emit[1], emit[2])

        # Create a single sub-material
        sub_materials.append(SubMaterialData(
            diffuse=(1.0, 1.0, 1.0, 1.0),
            ambient=(0.5, 0.5, 0.5, 1.0),
            specular=(1.0, 1.0, 1.0, 1.0),
            highlight=(highlight, highlight, highlight, highlight),
            texture_path=texture_path
        ))

        return sub_materials

    def _extract_objects(self) -> None:
        """Extract mesh objects from scene."""
        objects = self._get_objects()

        for ob in objects:
            if ob.name in self._processed_objects:
                continue

            obj_data = self._extract_object(ob)
            if obj_data:
                self._data.objects.append(obj_data)
                self._processed_objects.add(ob.name)

        self._logger.debug(f"Extracted {len(self._data.objects)} objects")

    def _extract_object(self, ob: bpy.types.Object) -> ObjectData | None:
        """Extract a single mesh object.

        Args:
            ob: Blender mesh object

        Returns:
            ObjectData structure or None if extraction fails
        """
        name = ob.name

        # Get evaluated mesh (with modifiers applied)
        apply_modifiers = self._settings.get('apply_modifiers', True)
        if apply_modifiers:
            depsgraph = self._context.evaluated_depsgraph_get()
            eval_ob = ob.evaluated_get(depsgraph)
            mesh = eval_ob.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        else:
            mesh = ob.to_mesh(preserve_all_data_layers=False)

        if mesh is None:
            self._logger.warning(f"Could not get mesh from object: {name}")
            return None

        try:
            # Get material index
            material_index = 0
            if ob.material_slots:
                first_slot = ob.material_slots[0]
                if first_slot.material:
                    material_index = self._material_index_map.get(first_slot.material.name, 0)

            # Extract meshes (with animation frames)
            meshes = []

            # Check for vertex animation
            export_animations = self._settings.get('export_animations', True)
            if export_animations and self._has_vertex_animation(ob):
                meshes = self._extract_vertex_animation(ob, mesh, material_index)
            else:
                # Single static mesh
                mesh_data = self._extract_mesh_geometry(mesh, material_index)
                meshes.append(mesh_data)

            # Extract matrix animation
            matrices = []
            if export_animations:
                matrices = self._extract_matrix_animation(ob)
            else:
                # Single static matrix
                matrix = self._matrix_to_flat_list(ob.matrix_world)
                matrices.append(MatrixFrame(timeline=0, matrix=matrix))

            return ObjectData(
                name=name,
                material_index=material_index,
                meshes=meshes,
                matrices=matrices
            )

        finally:
            # Clean up evaluated mesh
            if apply_modifiers:
                ob.to_mesh_clear()

    def _has_vertex_animation(self, ob: bpy.types.Object) -> bool:
        """Check if object has vertex animation (non-relative shape keys).

        Args:
            ob: Blender object

        Returns:
            True if vertex animation exists
        """
        if not ob.data.shape_keys:
            return False

        # Non-relative mode indicates vertex animation
        return not ob.data.shape_keys.use_relative

    def _extract_mesh_geometry(
        self,
        mesh: bpy.types.Mesh,
        material_index: int,
    ) -> MeshData:
        """Extract mesh geometry (positions, normals, UVs, faces).

        Args:
            mesh: Blender mesh
            material_index: Material slot index

        Returns:
            MeshData structure
        """
        # Get UV layer
        uv_layer = mesh.uv_layers.active

        # Extract vertices, normals, and UVs
        positions = []
        normals = []
        tex_coords = []
        faces = []

        # Build vertex index map (Blender vertices may be shared)
        vertex_map: dict[tuple, int] = {}
        next_index = 0

        # Get corner normals if available (Blender 4.1+)
        corner_normals = None
        if hasattr(mesh, 'corner_normals'):
            corner_normals = mesh.corner_normals

        for poly in mesh.polygons:
            face_indices = []

            for loop_idx in poly.loop_indices:
                loop = mesh.loops[loop_idx]
                vertex_idx = loop.vertex_index

                # Get position
                vert = mesh.vertices[vertex_idx]
                pos = (vert.co.x, vert.co.y, vert.co.z)

                # Get normal (use corner normals in Blender 4.1+, otherwise use vertex normal)
                if corner_normals is not None:
                    normal = tuple(corner_normals[loop_idx].vector)
                else:
                    normal = tuple(vert.normal)

                # Get UV
                if uv_layer:
                    uv = uv_layer.data[loop_idx].uv
                    tex = (uv.x, uv.y)
                else:
                    tex = (0.0, 0.0)

                # Create vertex key
                vertex_key = (pos, normal, tex)

                if vertex_key not in vertex_map:
                    vertex_map[vertex_key] = next_index
                    positions.append(pos)
                    normals.append(normal)
                    tex_coords.append(tex)
                    next_index += 1

                face_indices.append(vertex_map[vertex_key])

            # Convert to triangle if needed (should already be triangles)
            if len(face_indices) == 3:
                faces.append(tuple(face_indices))
            elif len(face_indices) == 4:
                # Split quad into two triangles
                faces.append((face_indices[0], face_indices[1], face_indices[2]))
                faces.append((face_indices[0], face_indices[2], face_indices[3]))

        return MeshData(
            timeline=0,
            sub_material=0,  # Always 0 since each exported material has one sub-material
            positions=positions,
            normals=normals,
            tex_coords=tex_coords,
            faces=faces
        )

    def _extract_vertex_animation(
        self,
        ob: bpy.types.Object,
        base_mesh: bpy.types.Mesh,
        material_index: int,
    ) -> list[MeshData]:
        """Extract vertex animation from shape keys.

        Shape keys in non-relative mode represent vertex animation frames.
        Timeline values are derived from keyframe positions.

        Args:
            ob: Blender object with shape keys
            base_mesh: Base mesh data
            material_index: Material slot index

        Returns:
            List of MeshData for each animation frame
        """
        meshes = []

        shape_keys = ob.data.shape_keys
        if not shape_keys:
            return meshes

        key_blocks = shape_keys.key_blocks

        # Get animation data to find keyframe positions
        keyframe_times = self._get_shape_key_keyframes(ob)

        # Extract each shape key as a frame
        for i, kb in enumerate(key_blocks):
            # Get timeline from keyframe or use index
            if i in keyframe_times:
                frame = keyframe_times[i]
                timeline = int(frame * TIMELINE_BASE)
            else:
                timeline = i * TIMELINE_BASE

            # Create mesh with this shape key applied
            mesh_data = self._extract_mesh_with_shape_key(ob, kb, material_index, timeline)
            if mesh_data:
                meshes.append(mesh_data)

        self._logger.debug(f"Extracted {len(meshes)} vertex animation frames")
        return meshes

    def _get_shape_key_keyframes(self, ob: bpy.types.Object) -> dict[int, float]:
        """Get keyframe positions for shape keys.

        Args:
            ob: Blender object

        Returns:
            Dictionary mapping shape key index to frame number
        """
        keyframes = {}

        if not ob.data.shape_keys or not ob.data.shape_keys.animation_data:
            return keyframes

        # Find eval_time fcurve
        action = ob.data.shape_keys.animation_data.action
        if not action:
            return keyframes

        for fc in action.fcurves:
            if fc.data_path == 'eval_time':
                for kp in fc.keyframe_points:
                    eval_time = kp.co.y
                    # eval_time = frame * 10 for non-relative shape keys
                    shape_key_idx = int(eval_time / 10)
                    keyframes[shape_key_idx] = kp.co.x

        return keyframes

    def _extract_mesh_with_shape_key(
        self,
        ob: bpy.types.Object,
        key_block: bpy.types.ShapeKey,
        material_index: int,
        timeline: int,
    ) -> MeshData | None:
        """Extract mesh with a specific shape key applied.

        Args:
            ob: Blender object
            key_block: Shape key to apply
            material_index: Material slot index
            timeline: Timeline value for this frame

        Returns:
            MeshData structure
        """
        # Store original shape key value
        original_value = key_block.value

        try:
            # Set shape key to full value
            key_block.value = 1.0

            # Get evaluated mesh
            apply_modifiers = self._settings.get('apply_modifiers', True)
            if apply_modifiers:
                depsgraph = self._context.evaluated_depsgraph_get()
                eval_ob = ob.evaluated_get(depsgraph)
                mesh = eval_ob.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            else:
                mesh = ob.to_mesh(preserve_all_data_layers=False)

            mesh_data = self._extract_mesh_geometry(mesh, material_index)
            mesh_data.timeline = timeline

            if apply_modifiers:
                ob.to_mesh_clear()

            return mesh_data

        finally:
            # Restore original value
            key_block.value = original_value

    def _extract_matrix_animation(
        self,
        ob: bpy.types.Object,
    ) -> list[MatrixFrame]:
        """Extract matrix animation from NLA tracks.

        Converts Blender keyframes (location, rotation, scale) back to
        4x4 matrices with timeline values.

        Args:
            ob: Blender object with animation data

        Returns:
            List of MatrixFrame structures
        """
        frames = []

        if not ob.animation_data:
            # No animation, return single frame with current matrix
            matrix = self._matrix_to_flat_list(ob.matrix_world)
            frames.append(MatrixFrame(timeline=0, matrix=matrix))
            return frames

        # Get all keyframe points from action
        action = ob.animation_data.action
        if not action:
            matrix = self._matrix_to_flat_list(ob.matrix_world)
            frames.append(MatrixFrame(timeline=0, matrix=matrix))
            return frames

        # Collect all unique frame numbers
        frame_set = set()
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                frame_set.add(int(kp.co.x))

        if not frame_set:
            matrix = self._matrix_to_flat_list(ob.matrix_world)
            frames.append(MatrixFrame(timeline=0, matrix=matrix))
            return frames

        # Sort frames and extract matrices
        sorted_frames = sorted(frame_set)
        original_frame = self._context.scene.frame_current

        try:
            for frame in sorted_frames:
                # Set scene frame
                self._context.scene.frame_set(frame)

                # Get matrix at this frame
                # Note: Need to evaluate depsgraph to get animated values
                depsgraph = self._context.evaluated_depsgraph_get()
                eval_ob = ob.evaluated_get(depsgraph)

                matrix = self._matrix_to_flat_list(eval_ob.matrix_world)
                timeline = int(frame * TIMELINE_BASE)

                frames.append(MatrixFrame(timeline=timeline, matrix=matrix))

        finally:
            # Restore original frame
            self._context.scene.frame_set(original_frame)

        self._logger.debug(f"Extracted {len(frames)} matrix animation frames")
        return frames

    def _extract_cameras(self) -> None:
        """Extract camera objects from scene."""
        cameras = self._get_camera_objects()

        for ob in cameras:
            cam_data = self._extract_camera(ob)
            if cam_data:
                self._data.cameras.append(cam_data)

        self._logger.debug(f"Extracted {len(self._data.cameras)} cameras")

    def _extract_camera(self, ob: bpy.types.Object) -> CameraData | None:
        """Extract a single camera object.

        Args:
            ob: Blender camera object

        Returns:
            CameraData structure
        """
        name = ob.name

        # Extract matrix animation
        export_animations = self._settings.get('export_animations', True)
        if export_animations and ob.animation_data:
            matrices = self._extract_matrix_animation(ob)
        else:
            matrix = self._matrix_to_flat_list(ob.matrix_world)
            matrices = [MatrixFrame(timeline=0, matrix=matrix)]

        return CameraData(name=name, matrices=matrices)

    @staticmethod
    def _matrix_to_flat_list(matrix: Matrix) -> list[float]:
        """Convert a Matrix to flat 16-element list (column-major).

        Args:
            matrix: 4x4 Matrix

        Returns:
            Flat list of 16 floats in column-major order
        """
        return [matrix.col[j][i] for i in range(4) for j in range(4)]
