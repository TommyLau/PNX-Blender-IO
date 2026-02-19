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

"""Logging utilities for the addon."""

from __future__ import annotations

import logging
from typing import Final

from .constants import ADDON_NAME

# Module-level logger cache
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str = ADDON_NAME) -> logging.Logger:
    """Get a logger instance for the addon.

    Args:
        name: Logger name, defaults to addon name

    Returns:
        Configured logger instance
    """
    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger
    return _loggers[name]


def setup_logging(level: int = logging.INFO) -> None:
    """Setup logging configuration.

    Args:
        level: Logging level to set
    """
    logger = get_logger()
    logger.setLevel(level)

    # Add handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            '[%(name)s] %(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def get_log_level_from_debug_value() -> int:
    """Convert Blender debug_value to logging level.

    The debug_value can be set in Blender via bpy.app.debug_value:
        0 = CRITICAL (default)
        1 = ERROR
        2 = WARNING
        3 = INFO
        4+ = DEBUG

    Returns:
        Logging level constant
    """
    try:
        import bpy
        debug_value = bpy.app.debug_value
    except ImportError:
        # Outside Blender context
        return logging.INFO

    levels: dict[int, int] = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
    }
    return levels.get(debug_value, logging.DEBUG)


class LogContext:
    """Context manager for temporary log level changes.

    Usage:
        with LogContext(logging.DEBUG):
            # Debug logging enabled
            pass
    """

    def __init__(self, level: int) -> None:
        """Initialize context with target level.

        Args:
            level: Logging level to use within context
        """
        self._level = level
        self._original_level: int | None = None

    def __enter__(self) -> LogContext:
        """Enter context, saving original level."""
        logger = get_logger()
        self._original_level = logger.level
        logger.setLevel(self._level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context, restoring original level."""
        if self._original_level is not None:
            logger = get_logger()
            logger.setLevel(self._original_level)
