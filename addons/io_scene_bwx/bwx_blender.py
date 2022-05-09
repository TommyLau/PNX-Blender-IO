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
from mathutils import Vector, Quaternion, Matrix


class BlenderBWX:
    """Main BWX import class."""

    @staticmethod
    def create(bwx):
        """Create BWX main worker method."""
        BlenderBWX.prepare_data(bwx)

        for o in bwx.model:
            [name, material, meshes, matrices] = o
            [sub_material, positions, tex_coords, indices] = meshes[0]
            faces = [indices[i:i + 3] for i in range(0, len(indices), 3)]

            me = bpy.data.meshes.new(name)
            me.from_pydata(positions, [], faces)
            corrections = me.validate(verbose=True, clean_customdata=True)

            uv_layer = me.uv_layers.new(do_init=False)  # Returns the created uv layer
            vert_uvs = tex_coords
            uv_layer.data.foreach_set("uv",
                                      [uv for pair in [vert_uvs[l.vertex_index] for l in me.loops] for uv in pair])

            # Try matrix
            [timeline, matrix] = matrices[0]
            mat = Matrix()
            mat[0][0] = matrix[0]
            mat[0][1] = matrix[4]
            mat[0][2] = matrix[8]
            mat[0][3] = matrix[12]
            mat[1][0] = matrix[1]
            mat[1][1] = matrix[5]
            mat[1][2] = matrix[9]
            mat[1][3] = matrix[13]
            mat[2][0] = matrix[2]
            mat[2][1] = matrix[6]
            mat[2][2] = matrix[10]
            mat[2][3] = matrix[14]
            mat[3][0] = matrix[3]
            mat[3][1] = matrix[7]
            mat[3][2] = matrix[11]
            mat[3][3] = matrix[15]

            # me.transform(mat)
            me.calc_normals()
            me.update()
            new_object = bpy.data.objects.new(name, me)
            new_object.matrix_basis = mat
            bpy.context.collection.objects.link(new_object)

    @staticmethod
    def prepare_data(bwx):
        """Prepare data, just before creation."""
        if bwx.model:
            print(bwx.model)

    @staticmethod
    def find_unused_name(haystack, desired_name):
        """Finds a name not in haystack and <= 63 UTF-8 bytes.
        (the limit on the size of a Blender name.)
        If a is taken, tries a.001, then a.002, etc.
        """
        stem = desired_name[:63]
        suffix = ''
        cntr = 1
        while True:
            name = stem + suffix

            if len(name.encode('utf-8')) > 63:
                stem = stem[:-1]
                continue

            if name not in haystack:
                return name

            suffix = '.%03d' % cntr
            cntr += 1
