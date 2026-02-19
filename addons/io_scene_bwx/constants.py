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

"""Constants and configuration for the BWX importer."""

from typing import Final

# Timeline conversion (game uses 120fps, Blender uses this for frame calculation)
TIMELINE_BASE: Final[int] = 32

# Default camera settings
DEFAULT_CAMERA_FOV: Final[float] = 38.6

# Object name prefixes to bypass during import
BYPASS_OBJECT_PREFIXES: Final[tuple[str, ...]] = ('EV_', 'EP_', '@', 'SFX', 'billboard')

# Supported file extensions
SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ('.BNX', '.PNX')

# Supported game versions
SUPPORTED_VERSIONS: Final[tuple[str, ...]] = ('SLv1', 'SLv2')

# Addon information
ADDON_NAME: Final[str] = "io_scene_bwx"

# BWX file signature
BWX_SIGNATURE: Final[bytes] = b"BWXF"
BWX_ENDING: Final[bytes] = b"FXWB"

# SLBWX signature
SLBWX_SIGNATURE: Final[str] = "SLBWX"

# Export-specific constants
# Version codes
DEFAULT_VERSION_SLV1: Final[int] = 0x0500  # Version 5.0
DEFAULT_VERSION_SLV2: Final[int] = 0x0602  # Version 6.02

# Matrix markers
MATRIX_MARKER_SLV1: Final[bytes] = b'\xc4'  # 69 bytes per frame (1 + 4 + 64)
MATRIX_MARKER_SLV2: Final[bytes] = b'\xe0'  # 97 bytes per frame (1 + 4 + 64 + 28)

# Vertex format (SLv2)
VERTEX_SIZE_SLV2: Final[int] = 32  # position(12) + normal(12) + uv(8)
EXTRA_VERTICES_SLV2: Final[int] = 2  # Extra dummy vertices in SLv2

# Direction flags
DIRECTION_MNHX: Final[int] = 0x4d4e4858  # Normal face winding
DIRECTION_MSHX: Final[int] = 0x4d534858  # Reversed face winding

# Magic values
PNX_MAGIC: Final[int] = 0x504e5800  # "PNX\0"
CAMR_MAGIC: Final[int] = 0x43414d52  # "CAMR"

# Default export values
DEFAULT_DESCRIPTION: Final[str] = "[BWX PNX KAK]"
DEFAULT_FILE_TYPE: Final[int] = 1  # Unknown field in header
