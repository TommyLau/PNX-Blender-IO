import struct
from ..construct import *


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
    a = [b for b in bwx.block if b.name == name]
    return a[0] if len(a) > 0 else None


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
        0x44: bwx_darray,
        0x53: Prefixed(VarInt, CString("euc-kr")),
        0x59: Byte,
        0x43: SByte,
        0x57: Int16ul,
        0x48: SInt16sl,
        0x49: Int32sl,
        0x46: Float32l,
        0x42: VarInt,
        0x80: Bytes(this.type & 0x7f),
    })),
)

bwx_main_block = Struct(
    "name" / Prefixed(VarInt, CString("utf-8")),
    "sub_block" / bwx_value,
)

bwx_file = Struct(
    "signature" / Const(b"BWXF"),
    "content_size" / VarInt,  # File content size, remove BWX header and end ("FXWB"), 7 + 4 Bytes
    "block_count" / VarInt,  # How many blocks
    "block" / Array(this.block_count, bwx_main_block),
    "ending" / Const(b"FXWB"),
)

# Process Header - HEAD
head_header = Struct(
    "name" / bwx_value,
    "description" / bwx_value,
    # "magic" / Const(b'I\x00XNP'),
    "magic" / Const(bwx_value.build(dict(type=SL_I32, data=0x504e5800))),  # PNX
    "version_type" / Const(b'W'),
    "version" / Enum(Int16ul, SLv1=0x0500, SLv2=0x0602),
    "other" / bwx_value,
)

# Process Materials

texture = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "TEX" / Const(bwx_value.build(dict(type=SL_STRING, data="TEX"))),  # TEX
    "most_0" / bwx_value,
    "filename" / bwx_value,
)

sub_material = Struct(
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
    "filename" / If(this.count > 8, texture)
)

material_header = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MTRL" / Const(bwx_value.build(dict(type=SL_STRING, data="MTRL"))),  # MTRL
    "material_name" / bwx_value,
    # "sub_material_array" / bwx_value,
    "sub_material" / Array(this.count - 2, sub_material),
)

# Process OBJ2

matrix = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MATRIX" / Const(bwx_value.build(dict(type=SL_STRING, data="MATRIX"))),  # MATRIX
    # "matrix" / Array(this.count - 1, sub_matrix),
    "matrix" / Array(this.count - 1, bwx_value),
)

sub_mesh = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MESHF" / Const(bwx_value.build(dict(type=SL_STRING, data="MESHF"))),  # MESHF
    "timeline" / bwx_value,
    "vertex_buffer" / bwx_value,
    # "uv_buffer" / If(this.count > 3, bwx_value),
    "uv_buffer" / bwx_value,  # Only the first sub mesh has UV data, others are null array
)

mesh = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "MESH" / Const(bwx_value.build(dict(type=SL_STRING, data="MESH"))),  # MESH
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "sub_mesh" / Array(this.count, sub_mesh),
    "sub_material" / bwx_value,
    "index_buffer" / bwx_value,
    "unknown1" / bwx_value,
    "unknown2" / bwx_value,
    "unknown3" / bwx_value,
    "unknown_20" / bwx_value,
)

object_header = Struct(
    "A" / Const(b'A'),  # Array
    "size" / VarInt,
    "count" / VarInt,
    "OBJ2" / Const(bwx_value.build(dict(type=SL_STRING, data="OBJ2"))),  # OBJ2
    "object_name" / bwx_value,
    "unknown1" / bwx_value,
    "material" / bwx_value,
    "unknown2" / bwx_value,
    "unknown3" / bwx_value,
    "direction" / bwx_value,
    "A" / Const(b'A'),  # Array
    "mesh_size" / VarInt,
    "mesh_count" / VarInt,
    "mesh" / Array(this.mesh_count, mesh),
    "A" / Const(b'A'),  # Array
    "matrix_size" / VarInt,
    "matrix_count" / VarInt,
    "matrix" / Array(this.matrix_count, matrix),
    "sfx" / bwx_value,
    "whatisthis" / If(this.count > 10, bwx_value),
)
