# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import celery
import os

from dotenv import dotenv_values

ENV = {
    # Load shared development environment variables.
    **dotenv_values(".env.shared"),
    # Load sensitive environment variables.
    **dotenv_values(".env.secret"),
    # Override loaded values with environment variables.
    **os.environ,
}

registered_tasks = [
    # NOTE: Add tasks here.
    "celery_app.tasks.example_task",
]
celery_app_instance = celery.Celery(
    __name__,
    backend=ENV["CELERY_RESULT_BACKEND_URL"],
    broker=ENV["CELERY_BROKER_URL"],
    include=registered_tasks,
)
celery_app_instance.set_current()
celery_app_instance.set_default()
