# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from celery.app.control import Control as CeleryControl
from celery_app.app import celery_app_instance as app

celery_app_control_instance = CeleryControl(app)
