"""
Settings module for poi_ingest project.

By default, imports local settings for development.
Override by setting DJANGO_SETTINGS_MODULE environment variable.
"""

from .local import *  # noqa: F401, F403
