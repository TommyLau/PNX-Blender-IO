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


from io_scene_bwx.bwx_construct import *

BYPASS_OBJECT_NAMES = ['EV_', 'EP_', '@', 'SFX', 'billboard']


# Raise this error to have the importer report an error message.
class ImportError(RuntimeError):
    pass


class BWXImporter:
    """BWX Importer class."""

    def __init__(self, filename, import_settings):
        """initialization."""
        self.model = []
        self.filename = filename
        self.import_settings = import_settings

    def checks(self):
        """Some checks."""
        pass

    def read(self):
        """Read file."""
        with open(self.filename, 'rb') as f:
            content = memoryview(f.read())
            # Parse PNX file
            bwx = bwx_struct.parse(content)
            head = get_block(bwx, "HEAD")

            if head.version == EnumIntegerString('SLv1'):
                # Version 1
                obj2 = get_block(bwx, "OBJ2")

                for o in obj2.object:
                    # Object
                    name = o.name.value
                    material = o.material.value

                    if any(name.startswith(n) for n in BYPASS_OBJECT_NAMES):
                        # FIXME: Enable later when process with collision detection and etc.
                        continue

                    # Only process one sub_mesh (no vertex animation support)
                    # TODO: Support vertex animation
                    meshes = []

                    for m in o.mesh:
                        # Only retrieve the first face's sub material id as texture for whole mesh
                        sub_material = m.sub_material[0].value
                        sm = m.sub_mesh[0]
                        positions = [Array(3, Float32l).parse(v.value)[:] for v in sm.vertex_buffer]
                        tex_coords = [Array(2, Float32l).parse(u.value)[:] for u in sm.uv_buffer]
                        indices = [i.value for i in m.index_buffer]

                        # Flip if direction = "MSHX"
                        if o.direction.value == EnumIntegerString('MSHX'):
                            for i in range(0, len(indices), 3):
                                indices[i + 1], indices[i + 2] = indices[i + 2], indices[i + 1]

                        meshes.append([sub_material, positions, tex_coords, indices])

                    # Assume have only ONE matrix group - o.matrix[0]
                    matrices = [[m.timeline, m.matrix[:]] for m in o.matrix[0].matrices]

                    # Insert object into model
                    self.model.append([name, material, meshes, matrices])

            elif head.version == EnumIntegerString('SLv2'):
                # TODO
                pass
