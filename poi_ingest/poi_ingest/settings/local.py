"""
Local development settings for poi_ingest project.
"""

from .base import *  # noqa: F401, F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

# Development-specific apps
INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
]

# Development middleware (add debug toolbar first)
MIDDLEWARE = [  # noqa: F405
    "debug_toolbar.middleware.DebugToolbarMiddleware",
] + MIDDLEWARE  # noqa: F405

# Database for development
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Debug toolbar configuration
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "IS_RUNNING_TESTS": False,  # Disable during tests
}

# Ensure logs directory exists
import os
LOGS_DIR = BASE_DIR / "logs"  # noqa: F405
os.makedirs(LOGS_DIR, exist_ok=True)

# Development-specific logging with structured formatting
LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {name} {message}",
            "style": "{",
        },
        "structured": {
            "format": "{asctime} | {levelname:8} | {name:20} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "level": "INFO",
            "stream": "ext://sys.stdout",  # Use stdout explicitly
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "development.log",
            "formatter": "verbose",
            "level": "DEBUG",
            "encoding": "utf-8",  # Handle Unicode characters properly
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "poi_ingest": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "ingest": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        # Third-party loggers
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Development-specific DRF settings
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # noqa: F405
    "rest_framework.permissions.AllowAny",  # Allow unauthenticated access in dev
]

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
