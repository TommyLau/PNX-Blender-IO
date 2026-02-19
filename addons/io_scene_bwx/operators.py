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

"""Blender operators for BWX import.

This module provides the ImportBWX operator for importing ShiningLore
BNX/PNX files into Blender.
"""

from __future__ import annotations

import logging
import os
import pathlib
import time
from typing import Set

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, StringProperty
from bpy.types import Context, Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .bwx_io import BWXImporter, ImportError
from .bwx_blender import BWXBlender
from .bwx_extractor import BWXExtractor, ExportError
from .bwx_writer import BWXWriter, WriterError
from .logging_utils import get_logger, get_log_level_from_debug_value


class ImportBWX(Operator, ImportHelper):
    """Import ShiningLore BWX file.

    This operator provides the main entry point for importing BNX/PNX files.
    It supports single file and batch file import through the file browser.
    """
    bl_idname = "import_scene.bwx"
    bl_label = "Import BWX File"
    bl_description = "Import a ShiningLore BNX/PNX file"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser filter
    filter_glob: StringProperty(
        default="*.BNX;*.PNX",
        options={'HIDDEN'},
    )

    # Multiple file selection support
    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )

    # Import options
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

    def draw(self, context: Context) -> None:
        """Draw the import options panel.

        Args:
            context: Blender context
        """
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Import options
        layout.prop(self, "import_animations")
        layout.prop(self, "import_cameras")

    def execute(self, context: Context) -> Set[str]:
        """Execute the import operation.

        Args:
            context: Blender context

        Returns:
            Set containing 'FINISHED' or 'CANCELLED'
        """
        logger = get_logger()
        logger.setLevel(get_log_level_from_debug_value())

        settings = self.as_keywords()

        if self.files:
            return self._import_multiple(settings)
        else:
            return self._import_single(self.filepath, settings)

    def _import_single(self, filepath: str, settings: dict) -> Set[str]:
        """Import a single file.

        Args:
            filepath: Path to the file
            settings: Import settings dictionary

        Returns:
            Set containing 'FINISHED' or 'CANCELLED'
        """
        logger = get_logger()

        try:
            # Parse the file
            importer = BWXImporter(filepath, settings)
            importer.read()
            importer.checks()

            logger.info("Data loaded, starting Blender object creation")

            # Create Blender objects
            start_time = time.time()
            import_path = self._get_import_path(filepath)

            blender = BWXBlender(importer, import_path)
            blender.create()

            elapsed = time.time() - start_time
            logger.info(f"BWX import finished in {elapsed:.2f}s")

            self.report({'INFO'}, f"Successfully imported: {os.path.basename(filepath)}")
            return {'FINISHED'}

        except ImportError as e:
            logger.error(f"Import failed: {e}")
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            logger.exception("Unexpected error during import")
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

    def _import_multiple(self, settings: dict) -> Set[str]:
        """Import multiple files.

        Args:
            settings: Import settings dictionary

        Returns:
            Set containing 'FINISHED' if at least one file succeeded
        """
        logger = get_logger()
        dirname = os.path.dirname(self.filepath)
        success = False

        for file in self.files:
            filepath = os.path.join(dirname, file.name)
            result = self._import_single(filepath, settings)
            if result == {'FINISHED'}:
                success = True

        return {'FINISHED'} if success else {'CANCELLED'}

    def _get_import_path(self, filepath: str) -> str:
        """Get the base import path for texture search.

        Looks for a 'Graphic' parent directory in the path hierarchy.

        Args:
            filepath: Path to the imported file

        Returns:
            The import path for texture search, or empty string
        """
        paths = [
            p for p in pathlib.Path(filepath).parents
            if p.stem == "Graphic"
        ]
        return str(paths[0].resolve()) if paths else ""


def menu_func_import(self, context: Context) -> None:
    """Add import menu entry.

    Args:
        context: Blender context (unused)
    """
    self.layout.operator(
        ImportBWX.bl_idname,
        text="ShiningLore BWX File (.BNX/.PNX)"
    )


class ExportBWX(Operator, ExportHelper):
    """Export ShiningLore BWX file.

    This operator provides the main entry point for exporting Blender
    scenes to BNX/PNX format.
    """
    bl_idname = "export_scene.bwx"
    bl_label = "Export BWX File"
    bl_description = "Export scene to ShiningLore BNX/PNX format"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser filter
    filename_ext = ".PNX"
    filter_glob: StringProperty(
        default="*.BNX;*.PNX",
        options={'HIDDEN'},
    )

    # Export options
    format_version: EnumProperty(
        name="Format Version",
        description="Target BWX format version",
        items=[
            ('1', "SLv1 (Legacy)", "Version 5.0 - OBJ2/MESH format (older)"),
            ('2', "SLv2 (Modern)", "Version 6.02 - SPOB/DXMESH format (recommended)"),
        ],
        default='2',
    )

    export_animations: BoolProperty(
        name="Export Animations",
        description="Export vertex and matrix animations",
        default=True,
    )

    export_cameras: BoolProperty(
        name="Export Cameras",
        description="Export camera objects",
        default=True,
    )

    use_selection: BoolProperty(
        name="Selected Objects Only",
        description="Export only selected objects",
        default=False,
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers before exporting",
        default=True,
    )

    copy_textures: BoolProperty(
        name="Copy Textures",
        description="Copy texture files to output directory",
        default=True,
    )

    def draw(self, context: Context) -> None:
        """Draw the export options panel.

        Args:
            context: Blender context
        """
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Format options
        layout.prop(self, "format_version")

        # Export options
        layout.prop(self, "export_animations")
        layout.prop(self, "export_cameras")
        layout.prop(self, "use_selection")
        layout.prop(self, "apply_modifiers")
        layout.prop(self, "copy_textures")

    def execute(self, context: Context) -> Set[str]:
        """Execute the export operation.

        Args:
            context: Blender context

        Returns:
            Set containing 'FINISHED' or 'CANCELLED'
        """
        logger = get_logger()
        logger.setLevel(get_log_level_from_debug_value())

        settings = self.as_keywords()

        try:
            # Extract data from Blender scene
            extractor = BWXExtractor(context, settings)
            extractor.extract()

            # Get format version
            version = int(settings.get('format_version', '2'))

            # Write to file
            writer = BWXWriter(extractor.data, version=version)
            writer.write(self.filepath)

            # Copy textures if requested
            texture_count = 0
            if settings.get('copy_textures', True):
                texture_count = self._copy_textures(extractor.data, self.filepath)

            msg = f"Successfully exported: {os.path.basename(self.filepath)}"
            if texture_count > 0:
                msg += f" ({texture_count} textures)"
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        except ExportError as e:
            logger.error(f"Export failed: {e}")
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except WriterError as e:
            logger.error(f"Write failed: {e}")
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            logger.exception("Unexpected error during export")
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

    def _copy_textures(self, data, filepath: str) -> int:
        """Copy texture files to output directory.

        Args:
            data: BWXData with material information
            filepath: Output PNX file path

        Returns:
            Number of textures copied
        """
        import shutil

        output_dir = pathlib.Path(filepath).parent
        copied = set()
        count = 0

        for mat in data.materials:
            for sub_mat in mat.sub_materials:
                if sub_mat.texture_path:
                    src_path = pathlib.Path(sub_mat.texture_path)
                    if src_path.exists() and src_path.name not in copied:
                        dst_path = output_dir / src_path.name
                        if not dst_path.exists():
                            shutil.copy2(src_path, dst_path)
                            count += 1
                        copied.add(src_path.name)

        return count


def menu_func_export(self, context: Context) -> None:
    """Add export menu entry.

    Args:
        context: Blender context (unused)
    """
    self.layout.operator(
        ExportBWX.bl_idname,
        text="ShiningLore BWX File (.BNX/.PNX)"
    )
