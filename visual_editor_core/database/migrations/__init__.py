"""
Database migrations for the Visual Editor Core.
"""

from .initial_schema import create_initial_schema_migration
from .add_indexes import create_indexes_migration

__all__ = [
    'create_initial_schema_migration',
    'create_indexes_migration'
]