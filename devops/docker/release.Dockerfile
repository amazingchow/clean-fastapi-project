# python:3.8.18-alpine镜像是基于Alpine Linux发行版构建的.
# Alpine Linux是一个轻量级的Linux发行版, 这意味着python:3.8.18-alpine镜像的下载速度和部署速度会更快, 同时占用的系统资源会更少.
# 但是, 由于Alpine Linux发行版的特殊性, 一些常用的命令可能会有所不同. 例如, Alpine Linux发行版中没有bash命令, 而是使用sh命令.
# 另外, 由于Alpine Linux采用了musl C库而不是glibc, 在构建和运行时可能会遇到一些问题. 例如, 在构建时可能会遇到gcc找不到的头文件, 在运行时可能会遇到一些Python库找不到的问题.

# The python:3.8.18-alpine image is based on the Alpine Linux distribution.
# Alpine Linux is a lightweight Linux distribution, which means that the python:3.8.18-alpine image can be downloaded and deployed faster, and it consumes fewer system resources.
# However, due to the specific nature of the Alpine Linux distribution, some common commands may be different. For example, there is no "bash" command in the Alpine Linux distribution, instead, "sh" command is used.
# Additionally, because Alpine Linux uses the musl C library instead of glibc, you may encounter some issues during the build stage and runtime stage. For example, during the building, you may encounter header files that gcc cannot find, and during the runtime, you may encounter issues with some Python libraries not being found.

FROM python:3.8.18-alpine
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
    "--workers=${WEB_CONCURRENCY}", \
    "--loop=uvloop", \
    "--http=httptools", \
    "--interface=asgi3", \
    "--log-level=info", \
    " --access-log", \
    "--root-path=/", \
    "--limit-concurrency=1024", \
    "--backlog=64", \
    "--timeout-keep-alive=5", \
    "--timeout-graceful-shutdown=5" \
]
