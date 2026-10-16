"""
Memory Exceptions.

Custom exception hierarchy for the Memory subsystem.
"""

from __future__ import annotations


class MemoryError(Exception):
    """
    Base exception for all memory-related errors.
    """


class MemoryStoreError(MemoryError):
    """
    Raised when a memory backend fails.
    """


class MemoryNotFoundError(MemoryError):
    """
    Raised when a requested memory cannot be found.
    """


class MemoryValidationError(MemoryError):
    """
    Raised when memory data is invalid.
    """


class MemoryInitializationError(MemoryError):
    """
    Raised when the memory module fails to initialize.
    """
