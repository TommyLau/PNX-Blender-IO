import struct
from .bwx_construct import *


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
            # Parse PNX file
            bwx = bwx_struct.parse(content)
            print(bwx)

            head_data = get_block(bwx, "HEAD")

            if head_data:
                print(head_data.data.version)
