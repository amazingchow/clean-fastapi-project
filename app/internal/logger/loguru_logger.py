# -*- coding: utf-8 -*-
import os
import sys
import ujson as json

from dependencies import settings
from loguru import logger as loguru_logger
from typing import Any, Dict


def _env(key, type_, default=None):
    if key not in os.environ:
        return default

    val = os.environ[key]

    if type_ == str:
        return val
    elif type_ == bool:
        if val.lower() in ["1", "true", "yes", "y", "ok", "on"]:
            return True
        if val.lower() in ["0", "false", "no", "n", "nok", "off"]:
            return False
        raise ValueError(
            "Invalid environment variable '%s' (expected a boolean): '%s'" % (key, val)
        )
    elif type_ == int:
        try:
            return int(val)
        except ValueError:
            raise ValueError(
                "Invalid environment variable '%s' (expected an integer): '%s'" % (key, val)
            ) from None


def custom_serialize_record(text: str, record: Dict[str, Any]) -> str:
    serializable = {
        "_host": record["extra"]["_host"],
        "_pod": record["extra"]["_pod"],
        "_namespace": record["extra"]["_namespace"],
        "app": record["extra"]["app"],
        "table": record["extra"]["table"],
        "event": record["extra"]["event"],
        "trace_id": record["extra"]["trace_id"],
        "uid": record["extra"]["uid"],
        "room_id": record["extra"]["room_id"],
        "ts": text[3:26],
        "msg": text[31:]
    }
    return json.dumps(serializable, default=str, ensure_ascii=False) + "\n"


def init_global_logger():
    # remove default logger
    loguru_logger.remove()
    if settings.LOG_PRINTER == "disk" and len(settings.LOG_PRINTER_FILENAME) > 0:
        if settings.DEPLOY_ENV == "k8s":
            # loguru_logger.configure() must be called before loguru_logger.add()
            _host = os.environ.get("PARAMETRIX_HOST", "unknown")
            if _host == "unknown":
                raise EnvironmentError("PARAMETRIX_HOST env variable not set, all logging record will miss the field.")
            _pod = os.environ.get("PARAMETRIX_POD", "unknown")
            if _pod == "unknown":
                raise EnvironmentError("PARAMETRIX_POD env variable not set, all logging record will miss the field.")
            _namespace = os.environ.get("PARAMETRIX_NAMESPACE", "unknown")
            if _namespace == "unknown":
                raise EnvironmentError("PARAMETRIX_NAMESPACE env variable not set, all logging record will miss the field.")
            _app = os.environ.get("PARAMETRIX_LOGGER_VAR_APP", "unknown")
            if _app == "unknown":
                raise EnvironmentError("PARAMETRIX_LOGGER_VAR_APP env variable not set, all logging record will miss the field.")
            _table = os.environ.get("PARAMETRIX_LOGGER_VAR_TABLE", "unknown")
            if _table == "unknown":
                raise EnvironmentError("PARAMETRIX_LOGGER_VAR_TABLE env variable not set, all logging record will miss the field.")
            _event = os.environ.get("PARAMETRIX_LOGGER_VAR_DEFAULT_EVENT", "unknown")
            if _event == "unknown":
                raise EnvironmentError("PARAMETRIX_LOGGER_VAR_DEFAULT_EVENT env variable not set, all logging record will miss the field.")
            loguru_logger.configure(extra={
                "_host": _host, "_pod": _pod, "_namespace": _namespace,
                "app": _app, "table": _table, "event": _event,
                "trace_id": "", "uid": "", "room_id": ""
            })  # Default values
            # add new logger
            handler_id = loguru_logger.add(
                sink=settings.LOG_PRINTER_FILENAME,
                level=settings.LOG_LEVEL.upper(),
                format="<green>ts={time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
                    "<level>msg={message}</level>",
                colorize=_env("LOGURU_COLORIZE", bool, False),
                serialize=True,
                backtrace=_env("LOGURU_BACKTRACE", bool, True),
                diagnose=_env("LOGURU_DIAGNOSE", bool, True),
                enqueue=_env("LOGURU_ENQUEUE", bool, False),
                catch=_env("LOGURU_CATCH", bool, True),
                rotation="256 MB",
            )
            # override _serialize_record method
            loguru_logger._core.handlers[handler_id]._serialize_record = custom_serialize_record
        else:
            # loguru_logger.configure() must be called before loguru_logger.add()
            loguru_logger.configure(extra={
                "trace_id": "", "uid": "", "room_id": ""
            })  # Default values
            # add new logger
            loguru_logger.add(
                sink=settings.LOG_PRINTER_FILENAME,
                level=settings.LOG_LEVEL.upper(),
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<red>trace_id={extra[trace_id]}</red> <red>uid={extra[uid]}</red> <red>room_id={extra[room_id]}</red> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "- <level>{message}</level>",
                colorize=_env("LOGURU_COLORIZE", bool, False),
                serialize=_env("LOGURU_SERIALIZE", bool, False),
                backtrace=_env("LOGURU_BACKTRACE", bool, True),
                diagnose=_env("LOGURU_DIAGNOSE", bool, True),
                enqueue=_env("LOGURU_ENQUEUE", bool, False),
                catch=_env("LOGURU_CATCH", bool, True),
                rotation="64 MB",
            )
    else:
        # loguru_logger.configure() must be called before loguru_logger.add()
        loguru_logger.configure(extra={
            "trace_id": "", "uid": "", "room_id": ""
        })  # Default values
        # add new logger
        loguru_logger.add(
            sink=sys.stderr,
            level=settings.LOG_LEVEL.upper(),
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<red>trace_id={extra[trace_id]}</red> <red>uid={extra[uid]}</red> <red>room_id={extra[room_id]}</red> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "- <level>{message}</level>",
            colorize=_env("LOGURU_COLORIZE", bool, False),
            serialize=_env("LOGURU_SERIALIZE", bool, False),
            backtrace=_env("LOGURU_BACKTRACE", bool, True),
            diagnose=_env("LOGURU_DIAGNOSE", bool, True),
            enqueue=_env("LOGURU_ENQUEUE", bool, False),
            catch=_env("LOGURU_CATCH", bool, True),
        )
