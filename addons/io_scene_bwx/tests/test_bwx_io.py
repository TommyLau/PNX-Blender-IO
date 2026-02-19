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

"""Unit tests for bwx_io module."""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import os

# Mock bpy module for testing outside Blender
sys.modules['bpy'] = MagicMock()

from io_scene_bwx.bwx_io import BWXImporter, ImportError
from io_scene_bwx.types import BWXData, MaterialData, ObjectData, CameraData
from io_scene_bwx.constants import BYPASS_OBJECT_PREFIXES


class TestBWXImporter(unittest.TestCase):
    """Tests for BWXImporter class."""

    def test_init_with_string_path(self):
        """Test initialization with string path."""
        importer = BWXImporter('/path/to/file.PNX', {})
        self.assertEqual(importer.filename, '/path/to/file.PNX')
        self.assertIsInstance(importer.data, BWXData)

    def test_init_with_path_object(self):
        """Test initialization with Path object."""
        path = Path('/path/to/file.PNX')
        importer = BWXImporter(path, {})
        self.assertEqual(importer.filename, str(path))

    def test_animation_name_extraction(self):
        """Test animation name extraction from filename."""
        # Test with underscore-separated filename
        importer = BWXImporter('/path/to/HEROBIO_default.PNX', {})
        self.assertEqual(importer.data.animation_name, 'default')

        # Test with simple filename
        importer = BWXImporter('/path/to/character.PNX', {})
        self.assertEqual(importer.data.animation_name, 'character')

    def test_file_not_found(self):
        """Test error handling for non-existent file."""
        importer = BWXImporter('/non/existent/file.PNX', {})
        with self.assertRaises(ImportError) as context:
            importer.read()
        self.assertIn('File not found', str(context.exception))

    def test_invalid_file(self):
        """Test error handling for invalid file."""
        with tempfile.NamedTemporaryFile(suffix='.PNX', delete=False) as f:
            f.write(b'invalid content')
            temp_path = f.name

        try:
            importer = BWXImporter(temp_path, {})
            with self.assertRaises(ImportError):
                importer.read()
        finally:
            os.unlink(temp_path)

    def test_checks_method(self):
        """Test that checks method doesn't raise."""
        importer = BWXImporter('/path/to/file.PNX', {})
        # Should not raise
        importer.checks()


class TestBWXData(unittest.TestCase):
    """Tests for BWXData dataclass."""

    def test_empty_initialization(self):
        """Test empty data initialization."""
        data = BWXData()
        self.assertEqual(data.materials, [])
        self.assertEqual(data.objects, [])
        self.assertEqual(data.cameras, [])
        self.assertEqual(data.filepath, "")
        self.assertEqual(data.animation_name, "")

    def test_full_initialization(self):
        """Test full data initialization."""
        data = BWXData(
            filepath='/path/to/file.PNX',
            animation_name='test'
        )
        self.assertEqual(data.filepath, '/path/to/file.PNX')
        self.assertEqual(data.animation_name, 'test')


class TestConstants(unittest.TestCase):
    """Tests for constants."""

    def test_bypass_prefixes(self):
        """Test bypass object prefixes."""
        self.assertIn('EV_', BYPASS_OBJECT_PREFIXES)
        self.assertIn('EP_', BYPASS_OBJECT_PREFIXES)
        self.assertIn('@', BYPASS_OBJECT_PREFIXES)
        self.assertIn('SFX', BYPASS_OBJECT_PREFIXES)
        self.assertIn('billboard', BYPASS_OBJECT_PREFIXES)

    def test_timeline_base(self):
        """Test timeline base constant."""
        from io_scene_bwx.constants import TIMELINE_BASE
        self.assertEqual(TIMELINE_BASE, 32)


if __name__ == '__main__':
    unittest.main()
