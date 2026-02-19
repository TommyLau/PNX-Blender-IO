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
