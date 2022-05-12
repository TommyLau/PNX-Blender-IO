# Copyright 2022 Tommy Lau @ SLODT
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


import bpy
import pathlib
from bpy_extras.image_utils import load_image
from mathutils import Vector, Quaternion, Matrix


class BWXBlender:
    """Main BWX import class."""

    def __init__(self, bwx):
        self.nodal_material_wrap_map = {}
        self.unique_materials = {}
        self.bwx = bwx
        import_path = [p for p in pathlib.Path(bwx.filename).parents if p.stem == "Graphic"]
        self.import_path = str(import_path[0].resolve()) if import_path else ''

    def create(self):
        """Create BWX main worker method."""
        self.prepare_data()

        for o in self.bwx.model:
            [name, material, meshes, matrices] = o
            [sub_material, positions, _normals, tex_coords, faces] = meshes[0]

            # Material
            mat = self.create_material(material, sub_material)

            me = bpy.data.meshes.new(name)
            me.materials.append(mat)
            me.from_pydata(positions, [], faces)
            corrections = me.validate(verbose=True, clean_customdata=True)
            print(f'Object: {name}, Correction!!!') if corrections else None

            uv_layer = me.uv_layers.new(do_init=False)  # Returns the created uv layer
            vert_uvs = tex_coords
            uv_layer.data.foreach_set("uv",
                                      [uv for pair in [vert_uvs[l.vertex_index] for l in me.loops] for uv in pair])

            me.calc_normals_split()
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
            me.update(calc_edges=True)
            new_object = bpy.data.objects.new(name, me)

            # Try matrix
            if matrices:
                [timeline, matrix] = matrices[0]
                mat = Matrix()
                for i in range(4):
                    mat.col[i] = [matrix[j] for j in range(i * 4, (i + 1) * 4)]

                new_object.matrix_basis = mat

            bpy.context.collection.objects.link(new_object)
            new_object.select_set(True)

    def prepare_data(self):
        """Prepare data, just before creation."""
        print(self.import_path)

    def create_material(self, material, sub_material):
        from bpy_extras import node_shader_utils

        [material_name, materials] = self.bwx.materials[material]
        context_material_key = f'{material}-{sub_material}'

        context_material = self.unique_materials.get(context_material_key)
        if context_material is not None:
            context_mat_wrap = self.nodal_material_wrap_map[context_material]
        else:
            ma_name = material_name
            ma = self.unique_materials[context_material_key] = bpy.data.materials.new(ma_name)
            ma_wrap = node_shader_utils.PrincipledBSDFWrapper(ma, is_readonly=False)
            self.nodal_material_wrap_map[ma] = ma_wrap
            ma_wrap.use_nodes = True

            [_, _, _, _, texture_file] = materials[sub_material]
            img = load_image(texture_file, self.import_path, recursive=True, verbose=True, check_existing=True)

            if img:
                # Add texture for material
                ma_wrap.base_color_texture.image = img
                ma_wrap.base_color_texture.texcoords = 'UV'

                # Add alpha blending if the texture is 32bits
                if img.depth == 32:
                    ma_wrap.alpha_texture.image = img
                    ma_wrap.alpha_texture.texcoords = 'UV'

            context_material = ma
            context_mat_wrap = ma_wrap

        return context_material
