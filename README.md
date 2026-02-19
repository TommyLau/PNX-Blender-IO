# ShiningLore BWX Format Importer

Blender addon for importing ShiningLore Online game files (.BNX/.PNX format).

## Credits

Developed by [Tommy Lau](http://tommy.net.cn/), with support from OopsWare and SLODT.

## Introduction

ShiningLore Online PNX/BNX importer for Blender 4.x.

This addon enables importing 3D models, materials, textures, and animations from ShiningLore Online game files into Blender.

### Features

- Import 3D models with materials and textures
- Import vertex animations (shape keys)
- Import matrix animations (NLA tracks)
- Import camera objects
- Support for both SLv1 and SLv2 file formats

## Requirements

- **Blender**: 4.2+ (tested with 4.5 LTS)
- **Python**: 3.11+

## Installation

### Method 1: Extension (Recommended)

1. Download `io_scene_bwx-0.2.0.zip` from [Releases](https://github.com/TommyLau/PNX-Blender-IO/releases)
2. In Blender, go to **Edit > Preferences > Extensions**
3. Click the dropdown menu (⋮) and select **Install from Disk**
4. Select the downloaded zip file
5. Enable the extension

### Method 2: Legacy (Development)

1. Copy the `addons/io_scene_bwx` folder to Blender's addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/4.x/scripts/addons/`
   - **Linux**: `~/.config/blender/4.x/scripts/addons/`

2. Enable in Blender:
   - Go to **Edit > Preferences > Add-ons**
   - Search for "ShiningLore"
   - Enable the checkbox

## Usage

1. Go to **File > Import > ShiningLore BWX File (.BNX/.PNX)**
2. Select a BNX or PNX file
3. Adjust import options if needed
4. Click **Import**

### Import Options

| Option | Description | Default |
|--------|-------------|---------|
| Import Animations | Import vertex and matrix animations | Yes |
| Import Cameras | Import camera objects | Yes |

## File Format

The addon supports two format versions:

- **SLv1**: Uses OBJ2/MESH structures
- **SLv2**: Uses DXOBJ/DXMESH structures

## Debugging

Set `bpy.app.debug_value` to control log verbosity:

| Value | Level |
|-------|-------|
| 0 | CRITICAL (default) |
| 1 | ERROR |
| 2 | WARNING |
| 3 | INFO |
| 4+ | DEBUG |

Example (in Blender Python console):
```python
import bpy
bpy.app.debug_value = 3  # Enable INFO logging
```

## Development

For development and debugging, see [DEBUGGING.md](DEBUGGING.md) (if available).

### Project Structure

```
io_scene_bwx/
├── __init__.py              # Addon entry point
├── blender_manifest.toml    # Extension manifest (Blender 4.2+)
├── constants.py             # Constants and configuration
├── types.py                 # Dataclasses for data structures
├── bwx_construct.py         # Binary format definitions
├── bwx_io.py                # Data importer
├── bwx_blender.py           # Blender integration
├── operators.py             # Blender operators
├── properties.py            # PropertyGroup classes
├── logging_utils.py         # Logging configuration
├── wheels/                  # Python wheel dependencies
└── tests/                   # Unit tests
```

## Notes

- Textures are loaded recursively from a `Graphic` parent directory if found in the file path
- The addon uses EUC-KR encoding for Korean strings in the game files
- UV coordinates for SLv2 files are flipped vertically (1 - y)
- Face winding order may be reversed based on the `MSHX` direction flag

## License

GPL v3.0
