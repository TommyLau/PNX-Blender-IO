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

"""Blender property definitions for BWX import settings."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class BWXImportSettings(PropertyGroup):
    """Import settings for BWX files.

    These properties appear in the file browser when importing BWX files.
    """

    filepath: StringProperty(
        name="File Path",
        description="Path to the BWX file to import",
        subtype='FILE_PATH',
        options={'HIDDEN'},
    )

    import_animations: BoolProperty(
        name="Import Animations",
        description="Import vertex and matrix animations",
        default=True,
    )

    import_cameras: BoolProperty(
        name="Import Cameras",
        description="Import camera objects",
        default=True,
    )

    scale_factor: FloatProperty(
        name="Scale",
        description="Scale factor for imported objects",
        default=1.0,
        min=0.001,
        max=100.0,
    )

    log_level: IntProperty(
        name="Log Level",
        description="Logging verbosity level (0=CRITICAL, 1=ERROR, 2=WARNING, 3=INFO, 4+=DEBUG)",
        default=20,  # INFO
        min=0,
        max=50,
    )


def register() -> None:
    """Register property classes."""
    bpy.utils.register_class(BWXImportSettings)


def unregister() -> None:
    """Unregister property classes."""
    bpy.utils.unregister_class(BWXImportSettings)
