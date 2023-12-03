include .env .env.secret .env.shared
export

CURR_DIR = $(shell pwd)

.PHONY: help
help: ### Display this help screen.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: deps
deps: ### Package the runtime requirements.
	@pip freeze > requirements.txt

.PHONY: local_run_task_worker
local_run_task_worker: ### Run the celery worker.
	@(celery -A celery_app.app.celery_app_instance worker --concurrency=1 --pool=prefork --loglevel=DEBUG)

.PHONY: local_run_task_dashboard
local_run_task_dashboard: ### Run the celery dashboard.
	@(celery -A celery_app.app.celery_app_instance flower --port=${CELERY_DASHBOARD_PORT})

.PHONY: run_infra
run_infra: ### Run the infra.
	@(docker-compose -f "${CURR_DIR}/devops/docker-compose/infra.yaml" up -d --build)

.PHONY: shutdown_infra
shutdown_infra: ### Shutdown the infra.
	@(docker-compose -f "${CURR_DIR}/devops/docker-compose/infra.yaml" down)
