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

import pathlib
from io_scene_bwx.bwx_construct import *

BYPASS_OBJECT_NAMES = ['EV_', 'EP_', '@', 'SFX', 'billboard']


# Raise this error to have the importer report an error message.
class ImportError(RuntimeError):
    pass


class BWXImporter:
    """BWX Importer class."""

    def __init__(self, filename, import_settings):
        """initialization."""
        self.materials = []
        self.model = []
        self.camera = []
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
                sl_version = 1
            elif head.version == EnumIntegerString('SLv2'):
                sl_version = 2
            else:
                raise ImportError("Unsupported version")

            # Version 1
            model = get_block(bwx, "OBJ2") if sl_version == 1 else get_block(bwx, "SPOB")

            for o in model.object:
                # Object
                name = o.name.value
                material = o.material.value

                if any(name.startswith(n) for n in BYPASS_OBJECT_NAMES):
                    # FIXME: Enable later when process with collision detection and etc.
                    continue

                meshes = []
                for m in o.mesh:
                    for sm in m.sub_mesh:
                        if sl_version == 1:
                            # Only retrieve the first face's sub material id as texture for whole mesh
                            sub_material = m.sub_material[0].value
                            positions = [Array(3, Float32l).parse(v.value)[:] for v in sm.vertex_buffer]
                            normals = []
                            tex_coords = [Array(2, Float32l).parse(u.value)[:] for u in sm.uv_buffer]
                            indices = iter([i.value for i in m.index_buffer])
                        else:
                            # Version 2 use one int to represent the sub_material value
                            sub_material = m.sub_material.value
                            # There are two more vertices which are unknown
                            # Remember to write two more back when exporting
                            vertex_buffer = Array(sm.vertex_count.value, bwx_dx_vertex_struct).parse(
                                sm.vertex_buffer.value)
                            positions = [v.positions[:] for v in vertex_buffer]
                            normals = [v.normals[:] for v in vertex_buffer]  # Unused right now
                            tex_coords = [[v.tex_coords[0], 1 - v.tex_coords[1]] for v in vertex_buffer]
                            indices = iter(Array(m.index_count.value, Int16ul).parse(m.index_buffer.value))

                        # Flip if direction = "MSHX"
                        flip = o.direction.value == EnumIntegerString('MSHX')
                        faces = [(a, c, b) if flip else (a, b, c) for a, b, c in zip(indices, indices, indices)]
                        timeline = sm.timeline.value

                        meshes.append([timeline, sub_material, positions, normals, tex_coords, faces])

                # Assume have only ONE matrix group - o.matrix[0]
                matrices = [[m.timeline, m.matrix[:]] for m in o.matrix[0].matrices]

                # Insert object into model
                self.model.append([name, material, meshes, matrices])

            # Process Materials
            texture_path = pathlib.Path(self.filename).parent
            mtrl = get_block(bwx, "MTRL")
            for m in mtrl.material:
                name = m.material_name.value
                sub_materials = []
                for sm in m.sub_material:
                    sub_materials.append([
                        sm.diffuse.value,
                        sm.ambient.value,
                        sm.specular.value,
                        sm.highlight.value,
                        str(texture_path.joinpath(
                            pathlib.PureWindowsPath(sm.texture.filename.value).name).resolve()) if sm.texture else None
                    ])
                self.materials.append([name, sub_materials])

            # Process Camera
            cam = get_block(bwx, "CAM")
            for c in cam.camera:
                name = c.name.value
                matrix = [[m.timeline, m.camera[:]] for m in c.matrix]
                self.camera.append([name, matrix])
