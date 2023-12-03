# python:3.8.18-slim-bullseye镜像是基于Debian Linux发行版构建的.
# Debian Linux是一个非常流行的Linux发行版, 由于其广泛的应用, Debian Linux发行版的软件包数量非常多.
# 但是, Debian Linux发行版本身非常庞大, 这意味着python:3.8.18-slim-bullseye镜像的下载速度和部署速度会慢一些, 同时占用的系统资源会更多.

# The python:3.8.18-slim-bullseye image is based on the Debian Linux distribution.
# Debian Linux is a popular Linux distribution with a wide range of software packages.
# However, Debian Linux is quite large, which means that the python:3.8.18-slim-bullseye image will be slower to download and deploy, and will consume more system resources.

FROM python:3.8.18-slim-bullseye
WORKDIR /app
COPY requirements.txt /app
# pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
# pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
RUN mkdir -p /app/config /app/logs /app/persistent /app/locks /app/shares
ENV SERVICE_HOST=${SERVICE_HOST:-"0.0.0.0"}
ENV SERVICE_PORT=${SERVICE_PORT:-18888}
ENV WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}
EXPOSE 18888
CMD [ \
    "uvicorn", \
    "app:app", \
    "--app-dir=/app/app", \
    '--host=${SERVICE_HOST}', \
    "--port=${SERVICE_PORT}", \
    "--workers=${WEB_CONCURRENCY}" \
    "--loop=uvloop", \
    "--http=httptools", \
    "--interface=asgi3", \
    "--log-level=info", \
    " --access-log", \
    "--root-path=/", \
    "--limit-concurrency=1024" \
    "--backlog=64" \
    "--timeout-keep-alive=5" \
    "--timeout-graceful-shutdown=5" \
]
