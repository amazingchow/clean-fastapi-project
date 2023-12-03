# -*- coding: utf-8 -*-
import time
import ujson as json

from celery_app.app import celery_app_instance as app
from loguru import logger as loguru_logger


@app.task(name="example_task")
def task(task_content: str) -> bool:
    loguru_logger.debug("To exec task:example_task...")
    st = time.perf_counter()
    done = False
    try:
        loguru_logger.debug(f"Task Raw Data: {task_content}.")
        task_data = json.loads(task_content)
        loguru_logger.debug(f"Task Data: {task_data}.")
        # NOTE: Add your task code here.
        time.sleep(1)

        done = True
    except Exception as e:
        loguru_logger.error(f"Failed task:example_task, err:{e}.")
    finally:
        ed = time.perf_counter()
        loguru_logger.debug(f"Finished task:example_task, latency: {ed - st:.3f}s.")
        return done
