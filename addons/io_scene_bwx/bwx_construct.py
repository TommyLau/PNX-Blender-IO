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


import struct
from io_scene_bwx.construct import *
# from construct import *


def singleton(arg):
    x = arg()
    return x


@singleton
class PackedInt(Construct):
    def _parse(self, stream, context, path):
        self.length = 0
        acc = []
        while True:
            b = stream_read(stream, 1, path)[0]
            acc.append(b & 0b01111111)
            if b & 0b10000000 == 0:
                break
        num = 0
        for b in reversed(acc):
            self.length += 1
            num = (num << 7) | b
        return num

    def _build(self, obj, stream, context, path):
        if not isinstance(obj, integertypes):
            raise IntegerError(f"value {obj} is not an integer", path=path)
        if obj < 0:
            raise IntegerError(f"VarInt cannot build from negative number {obj}", path=path)
        x = obj
        B = bytearray()
        while x > 0b01111111:
            B.append(0b10000000 | (x & 0b01111111))
            x >>= 7
        B.append(x)
        stream_write(stream, bytes(B), len(B), path)
        return obj

    def _emitprimitivetype(self, ksy, bitwise):
        # pass
        return "vlq_base128_le"

    def _sizeof(self, context, path):
        return self.length


class SFormatField(Construct):
    def __init__(self, endianity, format):
        super().__init__()
        self.fmtstr = endianity + format
        self.length = struct.calcsize(endianity + format)

    def _parse(self, stream, context, path):
        data = stream_read(stream, self.length, path)
        try:
            return -struct.unpack(self.fmtstr, data)[0]
        except Exception:
            raise FormatFieldError("struct %r error during parsing" % self.fmtstr, path=path)

    def _build(self, obj, stream, context, path):
        try:
            data = struct.pack(self.fmtstr, -obj)
        except Exception:
            raise FormatFieldError("struct %r error during building, given value %r" % (self.fmtstr, obj), path=path)
        stream_write(stream, data, self.length, path)
        return -obj

    def _sizeof(self, context, path):
        return self.length


@singleton
def SByte():
    return SFormatField("<", "B")


@singleton
def SInt16sl():
    return SFormatField("<", "H")


def get_block(bwx, name):
    a = [b.data for b in bwx.block if b.name == name]
    return a[0] if len(a) > 0 else None


# Add Korean EUC-KR support
possiblestringencodings["euc_kr"] = 1

# Signature A - 0x41
bwx_array = Struct(
    # "size" / VarInt,
    "size" / VarInt,
    "count" / PackedInt,
    "data" / Bytes((lambda this: this.size - this._subcons.count.sizeof())),
)

# Signature D - 0x44
bwx_darray = Struct(
    "size" / VarInt,
    "count" / PackedInt,
    "data" / Array(this.count, Struct(
        "name" / Prefixed(VarInt, CString("euc-kr")),
        "array" / Struct(
            "A" / Const(b'A'),  # Array
            "data" / bwx_array,
        )
    ))
)

bwx_direction = Struct(
    "type" / Const(b'I'),
    "value" / Enum(Int32ul, MNHX=0x4d4e4858, MSHX=0x4d534858),
)

'''
Array = 0x41
# VarInt = 0x42
S8 = 0x43
DArray = 0x44
F32 = 0x46
S16 = 0x48
U16 = 0x57
U8 = 0x59
Block = 0x80
'''
SL_I32 = 0x49
SL_STRING = 0x53

bwx_value = Struct(
    "type" / Byte,
    "data" / IfThenElse(this.type > 0x80, Bytes(this.type & 0x7f), Switch(this.type, {
        0x41: bwx_array,
        0x42: Prefixed(VarInt, GreedyBytes),
        0x43: SByte,
        0x44: bwx_darray,
        0x46: Float32l,
        0x48: SInt16sl,
        0x49: Int32sl,
        0x53: Prefixed(VarInt, CString("euc-kr")),
        0x57: Int16ul,
        0x59: Byte,
    })),
    "value" / Computed(lambda this: this.type if this.type < 0x20 else this.data),
)

# ------------------------------------------------------------
# 0
# ------------------------------------------------------------
bwx_0_struct = Struct(
    "signature" / Const(bwx_value.build(dict(type=SL_STRING, data="SLBWX"))),  # SLBWX
)
# ------------------------------------------------------------
# 0 - END
# ------------------------------------------------------------

# ------------------------------------------------------------
# Header
# ------------------------------------------------------------
bwx_header_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "name" / bwx_value,
    "description" / bwx_value,
    "magic" / Const(bwx_value.build(dict(type=SL_I32, data=0x504e5800))),  # PNX
    "version_type" / Const(b'W'),
    "version" / Enum(Int16ul, SLv1=0x0500, SLv2=0x0602),
    "other" / bwx_value,
)
# ------------------------------------------------------------
# Header - END
# ------------------------------------------------------------

# ------------------------------------------------------------
# Materials
# ------------------------------------------------------------
bwx_texture_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "TEX" / Const(bwx_value.build(dict(type=SL_STRING, data="TEX"))),  # TEX
    "most_0" / bwx_value,
    "filename" / bwx_value,
)

bwx_sub_material_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "SUBMTRL" / Const(bwx_value.build(dict(type=SL_STRING, data="SUBMTRL"))),  # SUBMTRL
    "diffuse" / bwx_value,
    "ambient" / bwx_value,
    "specular" / bwx_value,
    "some_float" / bwx_value,
    "highlight" / bwx_value,
    "most_1" / bwx_value,
    "unknown" / bwx_value,
    "texture" / If(this.count > 8, bwx_texture_struct)
)

bwx_material_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "material" / Array(this.count, Struct(
        "A" / Const(b'A'),  # Array
        "size" / VarInt,
        "count" / VarInt,
        "MTRL" / Const(bwx_value.build(dict(type=SL_STRING, data="MTRL"))),  # MTRL
        "material_name" / bwx_value,
        "sub_material" / Array(this.count - 2, bwx_sub_material_struct),
    )),
)
# ------------------------------------------------------------
# Materials - END
# ------------------------------------------------------------

# ------------------------------------------------------------
# Objects - Version 1
# ------------------------------------------------------------
bwx_matrix_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MATRIX" / Const(bwx_value.build(dict(type=SL_STRING, data="MATRIX"))),  # MATRIX
    "matrices" / Array(this.count - 1, Struct(
        "type" / Const(b'\xc4'),
        "timeline" / Int32ul,
        "matrix" / Array(16, Float32l),
    )),
)

bwx_meshf_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MESHF" / Const(bwx_value.build(dict(type=SL_STRING, data="MESHF"))),  # MESHF
    "timeline" / bwx_value,
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "vertex_count" / VarInt,
    "vertex_buffer" / Array(this.vertex_count, bwx_value),
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "uv_count" / VarInt,
    "uv_buffer" / Array(this.uv_count, bwx_value),  # Only the first sub mesh has UV data, others are null array
)

bwx_mesh_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MESH" / Const(bwx_value.build(dict(type=SL_STRING, data="MESH"))),  # MESH
    "A" / Const(b'A'),  # Array
    "sub_size" / VarInt,
    "sub_count" / VarInt,
    "sub_mesh" / Array(this.sub_count, bwx_meshf_struct),
    "A" / Const(b'A'),  # Array
    "sub_material_size" / VarInt,
    "sub_material_count" / VarInt,
    "sub_material" / Array(this.sub_material_count, bwx_value),
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "index_count" / VarInt,
    "index_buffer" / Array(this.index_count, bwx_value),
    "unknown1" / bwx_value,
    "unknown2" / bwx_value,
    "unknown3" / bwx_value,
    "unknown_20" / bwx_value,
)

bwx_object_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "object" / Array(this.count, Struct(
        "A" / Const(b'A'),  # Array
        "size" / VarInt,
        "count" / VarInt,
        "OBJ2" / Const(bwx_value.build(dict(type=SL_STRING, data="OBJ2"))),  # OBJ2
        "name" / bwx_value,
        "unknown1" / bwx_value,
        "material" / bwx_value,
        "unknown2" / bwx_value,
        "unknown3" / bwx_value,
        "direction" / bwx_direction,
        "A" / Const(b'A'),  # Array
        "mesh_size" / VarInt,
        "mesh_count" / VarInt,
        "mesh" / Array(this.mesh_count, bwx_mesh_struct),
        "A" / Const(b'A'),  # Array
        "matrix_size" / VarInt,
        "matrix_count" / VarInt,
        "matrix" / Array(this.matrix_count, bwx_matrix_struct),
        "sfx" / bwx_value,
        "whatisthis" / If(this.count > 10, bwx_value),
    )),
)

# ------------------------------------------------------------
# Objects - Version 2
# ------------------------------------------------------------
bwx_matrix2_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MATRIX" / Const(bwx_value.build(dict(type=SL_STRING, data="MATRIX"))),  # MATRIX
    "matrices" / Array(this.count - 1, Struct(
        "type" / Const(b'\xe0'),
        "timeline" / Int32ul,
        "matrix" / Array(16, Float32l),
        "unknown" / Array(7, Float32l),
    )),
)

bwx_dx_vertex_struct = Struct(
    "positions" / Array(3, Float32l),
    "normals" / Array(3, Float32l),
    "tex_coords" / Array(2, Float32l),
)

bwx_dx_meshf_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "DXMESHF" / Const(bwx_value.build(dict(type=SL_STRING, data="DXMESHF"))),  # DXMESHF
    "timeline" / bwx_value,
    "vertex_type" / bwx_value,  # Maybe, seems always = 0x15
    "vertex_count" / bwx_value,
    "vertex_size" / bwx_value,  # 0x20
    "vertex_buffer" / bwx_value,
)

bwx_dx_mesh_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "DXMESH" / Const(bwx_value.build(dict(type=SL_STRING, data="DXMESH"))),  # DXMESH
    "sub_material" / bwx_value,
    "A" / Const(b'A'),  # Array
    "sub_size" / VarInt,
    "sub_count" / VarInt,
    "sub_mesh" / Array(this.sub_count, bwx_dx_meshf_struct),
    "index_count" / bwx_value,
    "index_buffer" / bwx_value,
)

bwx_dx_object_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "object" / Array(this.count, Struct(
        "A" / Const(b'A'),  # Array
        "size" / VarInt,
        "count" / VarInt,
        "DXOBJ" / Const(bwx_value.build(dict(type=SL_STRING, data="DXOBJ"))),  # DXOBJ
        "name" / bwx_value,
        "unknown1" / bwx_value,
        "material" / bwx_value,
        "unknown2" / bwx_value,
        "unknown3" / bwx_value,
        "direction" / bwx_direction,
        "A" / Const(b'A'),  # Array
        "mesh_size" / VarInt,
        "mesh_count" / VarInt,
        "mesh" / Array(this.mesh_count, bwx_dx_mesh_struct),
        "A" / Const(b'A'),  # Array
        "matrix_size" / VarInt,
        "matrix_count" / VarInt,
        "matrix" / Array(this.matrix_count, bwx_matrix2_struct),
        "sfx" / bwx_value,
        "whatisthis" / If(this.count > 10, bwx_value),
    )),
)
# ------------------------------------------------------------
# Objects - END
# ------------------------------------------------------------

# ------------------------------------------------------------
# Camera
# ------------------------------------------------------------
bwx_camera_matrix_struct = Struct(
    "B" / Const(b'B'),  # Data block
    "size" / VarInt,
    "timeline" / Int32ul,
    "camera" / Array(16, Float32l),
    "target" / Array(16, Float32l),
    "unknown1" / Array(3, Float32l),
    "unknown2" / Array(3, Float32l),
)

bwx_camera_struct = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "camera" / Array(this.count, Struct(
        "A" / Const(b'A'),  # Array
        "size" / VarInt,
        "cam_count" / VarInt,
        "CAM" / Const(bwx_value.build(dict(type=SL_STRING, data="CAM"))),  # CAM
        "name" / bwx_value,
        "CAMR" / Const(bwx_value.build(dict(type=SL_I32, data=0x43414d52))),  # CAMR
        "unknown" / bwx_value,
        "matrix" / Array(this.cam_count - 4, bwx_camera_matrix_struct),
    )),
)
# ------------------------------------------------------------
# Camera - END
# ------------------------------------------------------------

# BWX Main Blocks
bwx_main_block_struct = Struct(
    "name" / Prefixed(VarInt, CString("utf-8")),
    "data" / Switch(this.name, {
        "0": bwx_0_struct,
        "HEAD": bwx_header_struct,
        "MTRL": bwx_material_struct,
        "OBJ2": bwx_object_struct,
        "OBJECT": bwx_object_struct,
        "CAM": bwx_camera_struct,
        "LIGHT": bwx_value,  # TODO
        "SOUND": bwx_value,  # TODO
        "BONE": bwx_value,  # TODO
        "CHART": bwx_value,  # TODO
        "DXOBJ": bwx_dx_object_struct,
        "SPOB": bwx_dx_object_struct,
    }, default=bwx_value),
)

# BWX File Struct
bwx_struct = Struct(
    "signature" / Const(b"BWXF"),
    "content_size" / VarInt,  # File content size, remove BWX header and end ("FXWB"), 7 + 4 Bytes
    "block_count" / VarInt,  # How many blocks
    "block" / Array(this.block_count, bwx_main_block_struct),
    "ending" / Const(b"FXWB"),
)
