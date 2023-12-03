FROM python:3.8.18-slim-bullseye
WORKDIR /celery
COPY celery-requirements.txt /celery
# pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
# pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir -r /celery/celery-requirements.txt
COPY celery_app /celery
RUN mkdir -p /celery/config /celery/logs /celery/persistent /celery/locks /celery/shares
ENV CELERY_CONCURRENCY_MODEL=${CELERY_CONCURRENCY_MODEL:-prefork}
ENV CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-1}
ENV CELERY_WORKER_LOG_LEVEL=${CELERY_WORKER_LOG_LEVEL:-INFO}
CMD [ \
    "celery", \
    "-A", \
    "celery_app.app.celery_app_instance", \
    "worker", \
    "--pool=${CELERY_CONCURRENCY_MODEL}", \
    "--concurrency=${CELERY_CONCURRENCY}", \
    "--loglevel=${CELERY_WORKER_LOG_LEVEL}" \
]
