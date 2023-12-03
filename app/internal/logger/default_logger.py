# -*- coding: utf-8 -*-
import coloredlogs
import logging
import sys

from dependencies import settings
from logging.handlers import RotatingFileHandler

_logger: logging.Logger = None


def init_global_logger():
    global _logger
    _logger = logging.getLogger(settings.LOG_SERVICE_NAME)

    if settings.LOG_LEVEL.lower() == "debug":
        log_level = logging.DEBUG
    elif settings.LOG_LEVEL.lower() == "info":
        log_level = logging.INFO
    else:
        log_level = logging.INFO

    if settings.LOG_PRINTER == "disk" and len(settings.LOG_PRINTER_FILENAME) > 0:
        handler = RotatingFileHandler(
            filename=settings.LOG_PRINTER_FILENAME,
            mode="a",
            maxBytes=64 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    elif settings.LOG_PRINTER == "console":
        handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = logging.Formatter(
        fmt="[%(asctime)s][%(levelname)s][%(name)s][%(process)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    _logger.setLevel(log_level)
    _logger.addHandler(handler)
    _logger.propagate = False

    if settings.LOG_PRINTER == "console":
        coloredlogs.install(
            level=log_level,
            logger=_logger,
            fmt="[%(asctime)s][%(levelname)s][%(name)s][%(process)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def global_logger() -> logging.Logger:
    return _logger
