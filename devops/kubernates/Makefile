CURR_DIR = $(shell pwd)

.PHONY: help
help: ### Display this help screen.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: render_chart
render_chart:
	@(python render.py --render_root_path=.)

.PHONY: check_chart
check_chart:
	@(helm template ./charts/clean-fastapi-project -f ./charts/clean-fastapi-project/values.yaml)

.PHONY: package_check
package_check:
	@(cd charts && tar -zcvf clean-fastapi-project.tar.gz clean-fastapi-project)
