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


# Raise this error to have the importer report an error message.
class ImportError(RuntimeError):
    pass


class BWXImporter:
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
                print(head_data.version)
