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


bl_info = {
    'name': 'ShiningLore BWX Format',
    'author': 'Tommy Lau',
    "version": (0, 1, 0),
    'blender': (2, 93, 0),
    'location': 'File > Import-Export',
    'description': 'Import BNX/PNX from ShiningLore',
    'warning': '',
    'category': 'Import-Export',
}


#
# Script reloading (if the user calls 'Reload Scripts' from Blender)
#

def reload_package(module_dict_main):
    import importlib
    from pathlib import Path

    def reload_package_recursive(current_dir, module_dict):
        for path in current_dir.iterdir():
            if "__init__" in str(path) or path.stem not in module_dict:
                continue

            if path.is_file() and path.suffix == ".py":
                importlib.reload(module_dict[path.stem])
            elif path.is_dir():
                reload_package_recursive(path, module_dict[path.stem].__dict__)

    reload_package_recursive(Path(__file__).parent, module_dict_main)


if "bpy" in locals():
    reload_package(locals())

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       EnumProperty,
                       IntProperty,
                       CollectionProperty)
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper


#
#  Functions / Classes.
#

class ImportBWX(Operator, ImportHelper):
    """Load a ShiningLore BNX/PNX file"""
    bl_idname = 'import_scene.bwx'
    bl_label = 'Import BWX File'
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(default="*.BNX;*.PNX", options={'HIDDEN'})

    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )

    loglevel: IntProperty(
        name='Log Level',
        description="Log Level")

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

    def execute(self, context):
        return self.import_bwx(context)

    def import_bwx(self, context):
        import os

        self.set_debug_log()
        import_settings = self.as_keywords()

        if self.files:
            # Multiple file import
            ret = {'CANCELLED'}
            dirname = os.path.dirname(self.filepath)
            for file in self.files:
                path = os.path.join(dirname, file.name)
                if self.unit_import(path, import_settings) == {'FINISHED'}:
                    ret = {'FINISHED'}
            return ret
        else:
            # Single file import
            return self.unit_import(self.filepath, import_settings)

    def unit_import(self, filename, import_settings):
        # from .io.imp.bwx_io import BWXImporter, ImportError
        # from .blender.imp.bwx_blender import BlenderBWX

        # try:
        #     bwx_importer = BWXImporter(filename, import_settings)
        #     bwx_importer.read()
        #     bwx_importer.checks()
        #
        #     print("Data are loaded, start creating Blender stuff")
        #
        #     start_time = time.time()
        #     BlenderBWX.create(bwx_importer)
        #     elapsed_s = "{:.2f}s".format(time.time() - start_time)
        #     print("BWX import finished in " + elapsed_s)
        #
        #     bwx_importer.log.removeHandler(bwx_importer.log_handler)
        #
        #     return {'FINISHED'}
        #
        # except ImportError as e:
        #     self.report({'ERROR'}, e.args[0])
        #     return {'CANCELLED'}
        return {'FINISHED'}

    def set_debug_log(self):
        import logging
        if bpy.app.debug_value == 0:
            self.loglevel = logging.CRITICAL
        elif bpy.app.debug_value == 1:
            self.loglevel = logging.ERROR
        elif bpy.app.debug_value == 2:
            self.loglevel = logging.WARNING
        elif bpy.app.debug_value == 3:
            self.loglevel = logging.INFO
        else:
            self.loglevel = logging.NOTSET


def menu_func_import(self, context):
    self.layout.operator(ImportBWX.bl_idname, text='ShiningLore BWX File (.BNX/.PNX)')


classes = (
    ImportBWX
)


def register():
    # import io_scene_bwx.blender.com.bwx_blender_ui as blender_ui
    # for c in classes:
    bpy.utils.register_class(ImportBWX)

    # blender_ui.register()

    # add to the export / import menu
    # bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    # import io_scene_bwx.blender.com.bwx_blender_ui as blender_ui
    # for c in classes:
    bpy.utils.unregister_class(ImportBWX)

    # blender_ui.unregister()

    # remove from the export / import menu
    # bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
