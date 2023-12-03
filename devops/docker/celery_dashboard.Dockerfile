FROM python:3.8.18-slim-bullseye
WORKDIR /celery
COPY celery-requirements.txt /celery
# pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
# pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir -r /celery/celery-requirements.txt
COPY celery_app /celery
RUN mkdir -p /celery/config /celery/logs /celery/persistent /celery/locks /celery/shares
ENV CELERY_DASHBOARD_PORT=${CELERY_DASHBOARD_PORT:-16666}
CMD [ \
    "celery", \
    "-A", \
    "celery_app.app.celery_app_instance", \
    "flower", \
    "--port=${CELERY_DASHBOARD_PORT}" \
]
