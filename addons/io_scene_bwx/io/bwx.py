import struct
from .pnx_construct import *


# Raise this error to have the importer report an error message.
class ImportError(RuntimeError):
    pass


class BWXImporter():
    """BWX Importer class."""

    def __init__(self, filename, import_settings):
        """initialization."""
        self.filename = filename
        self.import_settings = import_settings

    def checks(self):
        """Some checks."""
        pass

    def read(self):
        """Read file."""
        with open(self.filename, 'rb') as f:
            content = memoryview(f.read())
            # Parse PNX file and get main blocks
            bwx = bwx_file.parse(content)

            head_data = get_block(bwx, "HEAD")

            if head_data:
                h = head_header.parse(head_data.sub_block.data.data)
                print(h.version)

            # Materials
            MTRL = get_block(bwx, "MTRL")
            material_children = MTRL.sub_block.data
            material_struct = Struct(
                "object" / Array(material_children.count, material_header),
            )
            print(material_struct.parse(material_children.data))

            # Objects
            OBJECT = get_block(bwx, "OBJ2")
            object_children = OBJECT.sub_block.data
            object_struct = Struct(
                "object" / Array(object_children.count, object_header),
            )
            print(object_struct.parse(object_children.data))
