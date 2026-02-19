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

"""ShiningLore BWX Format Importer for Blender 4.x.

This addon provides import functionality for ShiningLore Online game files
in the BNX/PNX format (internally referred to as BWX format).

Features:
    - Import 3D models with materials and textures
    - Import vertex animations (shape keys)
    - Import matrix animations (NLA tracks)
    - Import camera objects

Usage:
    File > Import > ShiningLore BWX File (.BNX/.PNX)

Debugging:
    Set bpy.app.debug_value to control log verbosity:
        0 = CRITICAL (default)
        1 = ERROR
        2 = WARNING
        3 = INFO
        4+ = DEBUG
"""

from __future__ import annotations

from typing import Final

bl_info = {
    'name': 'ShiningLore BWX Format',
    'author': 'Tommy Lau',
    'version': (1, 0, 0),
    'blender': (4, 0, 0),
    'location': 'File > Import',
    'description': 'Import BNX/PNX files from ShiningLore Online',
    'warning': '',
    'category': 'Import-Export',
}

ADDON_NAME: Final = __name__

# Script reloading support (for development)
if "bpy" in locals():
    import importlib

    modules = [
        'bwx_construct',
        'bwx_io',
        'bwx_blender',
        'operators',
        'properties',
        'logging_utils',
        'constants',
        'types',
    ]

    for module in modules:
        if module in locals():
            importlib.reload(locals()[module])

import bpy

from . import operators, properties
from .logging_utils import get_logger, setup_logging

# Classes to register
_classes = (
    operators.ImportBWX,
)


def register() -> None:
    """Register all addon classes and menu items.

    This function is called by Blender when the addon is enabled.
    """
    logger = get_logger()
    logger.info("Registering io_scene_bwx addon")

    # Setup logging based on debug value
    setup_logging(getattr(bpy.app, 'debug_value', 0) if bpy.app.debug_value >= 3 else 20)

    # Register operator classes
    for cls in _classes:
        bpy.utils.register_class(cls)

    # Add menu entry
    bpy.types.TOPBAR_MT_file_import.append(operators.menu_func_import)

    logger.info("Addon registered successfully")


def unregister() -> None:
    """Unregister all addon classes and menu items.

    This function is called by Blender when the addon is disabled.
    """
    logger = get_logger()
    logger.info("Unregistering io_scene_bwx addon")

    # Remove menu entry
    bpy.types.TOPBAR_MT_file_import.remove(operators.menu_func_import)

    # Unregister operator classes in reverse order
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    logger.info("Addon unregistered successfully")


# Allow running the script directly from Blender's Text editor
if __name__ == "__main__":
    register()
