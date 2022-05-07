import bpy
from mathutils import Vector, Quaternion, Matrix


class BlenderBWX:
    """Main BWX import class."""

    @staticmethod
    def create(bwx):
        """Create BWX main worker method."""
        BlenderBWX.prepare_data(bwx)
        # BlenderScene.create(bwx)

    @staticmethod
    def prepare_data(bwx):
        """Prepare data, just before creation."""
        pass

    @staticmethod
    def find_unused_name(haystack, desired_name):
        """Finds a name not in haystack and <= 63 UTF-8 bytes.
        (the limit on the size of a Blender name.)
        If a is taken, tries a.001, then a.002, etc.
        """
        stem = desired_name[:63]
        suffix = ''
        cntr = 1
        while True:
            name = stem + suffix

            if len(name.encode('utf-8')) > 63:
                stem = stem[:-1]
                continue

            if name not in haystack:
                return name

            suffix = '.%03d' % cntr
            cntr += 1
