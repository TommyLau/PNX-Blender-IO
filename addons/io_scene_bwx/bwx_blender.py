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

"""Blender object creation from BWX data.

This module provides the BWXBlender class for creating Blender objects
(meshes, materials, cameras, animations) from parsed BWX data.
"""

from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING, Any

import bpy
from bpy_extras.image_utils import load_image
from mathutils import Matrix

from .constants import DEFAULT_CAMERA_FOV, TIMELINE_BASE
from .logging_utils import get_logger
from .types import BWXData, CameraData, MaterialData, MatrixFrame, MeshData, ObjectData

if TYPE_CHECKING:
    from .bwx_io import BWXImporter


class BlenderError(RuntimeError):
    """Raised when Blender object creation fails."""
    pass


class BWXBlender:
    """Creates Blender objects from imported BWX data.

    This class handles the creation of Blender meshes, materials, cameras,
    and animations from the parsed BWX data structures.

    Attributes:
        bwx: The BWX importer instance containing parsed data

    Example:
        importer = BWXImporter('/path/to/file.PNX', {})
        importer.read()

        blender = BWXBlender(importer)
        blender.create()
    """

    def __init__(self, bwx: BWXImporter | BWXData, import_path: str = "") -> None:
        """Initialize with imported data.

        Args:
            bwx: Either a BWXImporter instance or BWXData structure
            import_path: Base path for texture search (auto-detected if not provided)
        """
        # Support both BWXImporter and BWXData for flexibility
        if hasattr(bwx, 'data'):
            self._data = bwx.data
            self._importer = bwx
        else:
            self._data = bwx
            self._importer = None

        # Auto-detect import path from file location
        if not import_path and self._importer:
            paths = [
                p for p in pathlib.Path(self._importer.filename).parents
                if p.stem == "Graphic"
            ]
            import_path = str(paths[0].resolve()) if paths else ''

        self._import_path = import_path
        self._animation_name = self._data.animation_name or "animation"

        # Caches
        self._material_cache: dict[str, bpy.types.Material] = {}
        self._material_wrap_cache: dict[bpy.types.Material, Any] = {}

        self._logger = get_logger(f"{__name__}.BWXBlender")

    @property
    def bwx(self) -> BWXData:
        """Get the BWX data (for backward compatibility)."""
        return self._data

    @property
    def import_path(self) -> str:
        """Get the import path for texture search."""
        return self._import_path

    @property
    def animation(self) -> str:
        """Get the animation name."""
        return self._animation_name

    def create(self) -> None:
        """Create all Blender objects from the imported data.

        This method creates materials, meshes, objects, cameras, and animations
        in the current Blender scene.
        """
        start_time = time.time()
        self._logger.info("Starting Blender object creation")

        try:
            self._prepare_data()
            self._create_materials()
            self._create_objects()
            self._create_cameras()
        except Exception as e:
            self._logger.exception("Failed to create Blender objects")
            raise BlenderError(f"Failed to create Blender objects: {e}") from e

        elapsed = time.time() - start_time
        self._logger.info(f"Object creation completed in {elapsed:.2f}s")

    def _prepare_data(self) -> None:
        """Prepare data before creation.

        Called before creating any Blender objects.
        """
        self._logger.debug(f"Import path: {self._import_path}")
        self._logger.debug(f"Animation name: {self._animation_name}")

    def _create_materials(self) -> None:
        """Pre-create all unique materials.

        Materials are cached to avoid duplication when multiple objects
        share the same material.
        """
        # Materials are created on-demand in _get_or_create_material
        pass

    def _create_objects(self) -> None:
        """Create all model objects."""
        for obj_data in self._data.objects:
            self._create_object(obj_data)

    def _create_object(self, obj_data: ObjectData) -> bpy.types.Object:
        """Create a single Blender object.

        Args:
            obj_data: Object data to create

        Returns:
            The created Blender object
        """
        name = obj_data.name

        if not obj_data.meshes:
            self._logger.warning(f"Object {name} has no meshes, skipping")
            return None

        # Get first mesh for base creation
        first_mesh = obj_data.meshes[0]

        # Get material
        mat = self._get_or_create_material(obj_data.material_index, first_mesh.sub_material)

        # Create mesh
        mesh = bpy.data.meshes.new(name)
        mesh.materials.append(mat)
        self._create_mesh_geometry(mesh, first_mesh)

        # Create object
        ob = bpy.data.objects.new(name, mesh)

        # Handle vertex animation (shape keys)
        if len(obj_data.meshes) > 1:
            self._create_vertex_animation(ob, obj_data.meshes)

        # Handle matrix animation or apply static transform
        if len(obj_data.matrices) > 1:
            self._create_matrix_animation(ob, obj_data.matrices)
        else:
            # Only apply object matrix when there's no animation
            if obj_data.matrices:
                ob.matrix_basis = self._matrix_from_flat_list(obj_data.matrices[0].matrix)

        # Link to scene
        bpy.context.collection.objects.link(ob)
        ob.select_set(True)

        self._logger.debug(f"Created object: {name}")
        return ob

    def _create_mesh_geometry(
        self,
        mesh: bpy.types.Mesh,
        mesh_data: MeshData
    ) -> None:
        """Create mesh geometry from mesh data.

        Args:
            mesh: Blender mesh to populate
            mesh_data: Mesh data containing vertices and faces
        """
        mesh.clear_geometry()
        mesh.from_pydata(mesh_data.positions, [], mesh_data.faces)
        mesh.validate(verbose=True, clean_customdata=True)

        # Create UV layer
        uv_layer = mesh.uv_layers.new(do_init=False)
        if uv_layer and mesh_data.tex_coords:
            vert_uvs = mesh_data.tex_coords
            uv_layer.data.foreach_set(
                "uv",
                [uv for pair in [vert_uvs[l.vertex_index] for l in mesh.loops] for uv in pair]
            )

        # Set smooth shading
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.update(calc_edges=True)

    def _create_vertex_animation(
        self,
        ob: bpy.types.Object,
        meshes: list[MeshData]
    ) -> None:
        """Create vertex animation using shape keys.

        Args:
            ob: Blender object to animate
            meshes: List of mesh frames
        """
        mesh = ob.data
        first_mesh = meshes[0]

        for mesh_data in meshes:
            # Update mesh geometry
            self._create_mesh_geometry(mesh, mesh_data)

            # Create shape key
            frame = mesh_data.timeline / TIMELINE_BASE
            sk = ob.shape_key_add(name=f'Frame {frame}', from_mix=False)
            sk.interpolation = 'KEY_LINEAR'

            # Set keyframe for evaluation time
            mesh.shape_keys.eval_time = frame * 10
            mesh.shape_keys.keyframe_insert(data_path='eval_time', frame=frame)

        # Set to non-relative mode for vertex animation
        mesh.shape_keys.use_relative = False

        self._logger.debug(f"Created vertex animation with {len(meshes)} frames")

    def _create_matrix_animation(
        self,
        ob: bpy.types.Object,
        matrices: list[MatrixFrame]
    ) -> None:
        """Create matrix animation using keyframes and NLA tracks.

        Args:
            ob: Blender object to animate
            matrices: List of matrix frames
        """
        ob.rotation_mode = "QUATERNION"
        ad = ob.animation_data_create()

        # Create action
        action_name = f'{ob.name}_Action'
        action = bpy.data.actions.new(action_name)
        ob.animation_data.action = action

        # Create keyframes
        for matrix_frame in matrices:
            frame = matrix_frame.timeline / TIMELINE_BASE
            mat = self._matrix_from_flat_list(matrix_frame.matrix)
            ob.location, ob.rotation_quaternion, ob.scale = mat.decompose()

            ob.keyframe_insert(data_path='location', frame=frame)
            ob.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            ob.keyframe_insert(data_path='scale', frame=frame)

        # Create NLA track
        track = ad.nla_tracks.new()
        track.name = self._animation_name
        track.strips.new(action.name, 1, action)

        self._logger.debug(f"Created matrix animation with {len(matrices)} frames")

    def _create_cameras(self) -> None:
        """Create all camera objects."""
        for cam_data in self._data.cameras:
            self._create_camera(cam_data)

    def _create_camera(self, cam_data: CameraData) -> bpy.types.Object:
        """Create a single camera object.

        Args:
            cam_data: Camera data to create

        Returns:
            The created Blender camera object
        """
        name = cam_data.name

        # Create camera data
        cam = bpy.data.cameras.new(name)
        cam.lens_unit = 'FOV'
        cam.lens = DEFAULT_CAMERA_FOV

        # Create camera object
        ob = bpy.data.objects.new(name, cam)

        # Create animation if multiple matrices
        if len(cam_data.matrices) > 1:
            self._create_matrix_animation(ob, cam_data.matrices)

        # Link to scene
        bpy.context.collection.objects.link(ob)
        ob.select_set(True)

        self._logger.debug(f"Created camera: {name}")
        return ob

    def _get_or_create_material(
        self,
        material_index: int,
        sub_material_index: int
    ) -> bpy.types.Material:
        """Get or create a material for the given indices.

        Materials are cached by their combined index to avoid duplication.

        Args:
            material_index: Material index
            sub_material_index: Sub-material index

        Returns:
            The Blender material
        """
        context_key = f'{material_index}-{sub_material_index}'

        # Check cache
        if context_key in self._material_cache:
            return self._material_cache[context_key]

        # Get material data
        if material_index >= len(self._data.materials):
            self._logger.warning(f"Material index {material_index} out of range")
            return self._create_default_material(context_key)

        mat_data = self._data.materials[material_index]

        if sub_material_index >= len(mat_data.sub_materials):
            self._logger.warning(
                f"Sub-material index {sub_material_index} out of range for material {mat_data.name}"
            )
            return self._create_default_material(context_key)

        sub_mat_data = mat_data.sub_materials[sub_material_index]

        # Create material
        ma = bpy.data.materials.new(mat_data.name)
        self._material_cache[context_key] = ma

        # Setup material with nodes
        self._setup_material_nodes(ma, sub_mat_data)

        self._logger.debug(f"Created material: {mat_data.name} (sub: {sub_material_index})")
        return ma

    def _create_default_material(self, name: str) -> bpy.types.Material:
        """Create a default material when data is missing.

        Args:
            name: Material name

        Returns:
            A basic Blender material
        """
        ma = bpy.data.materials.new(name)
        ma.use_nodes = True
        self._material_cache[name] = ma
        return ma

    def _setup_material_nodes(
        self,
        ma: bpy.types.Material,
        sub_mat_data: SubMaterialData
    ) -> None:
        """Setup material nodes with texture.

        Args:
            ma: Blender material to setup
            sub_mat_data: Sub-material data containing texture info
        """
        from bpy_extras import node_shader_utils

        ma_wrap = node_shader_utils.PrincipledBSDFWrapper(ma, is_readonly=False)
        self._material_wrap_cache[ma] = ma_wrap
        ma_wrap.use_nodes = True

        # Load texture if available
        if sub_mat_data.texture_path:
            img = load_image(
                sub_mat_data.texture_path,
                self._import_path,
                recursive=True,
                verbose=False,
                check_existing=True
            )

            if img:
                # Set base color texture
                ma_wrap.base_color_texture.image = img
                ma_wrap.base_color_texture.texcoords = 'UV'

                # Add alpha blending for 32-bit textures
                if img.depth == 32:
                    ma_wrap.alpha_texture.image = img
                    ma_wrap.alpha_texture.texcoords = 'UV'

                self._logger.debug(f"Loaded texture: {sub_mat_data.texture_path}")
            else:
                self._logger.warning(f"Failed to load texture: {sub_mat_data.texture_path}")

    @staticmethod
    def _matrix_from_flat_list(matrix: list[float]) -> Matrix:
        """Convert a flat 16-element list to a Matrix.

        The flat list is assumed to be in column-major order.

        Args:
            matrix: Flat list of 16 floats

        Returns:
            4x4 Matrix
        """
        mat = Matrix()
        for i in range(4):
            mat.col[i] = [matrix[j] for j in range(i * 4, (i + 1) * 4)]
        return mat
