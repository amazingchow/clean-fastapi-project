# -*- coding: utf-8 -*-
import argparse
import os
import pathlib
import ujson as json

from dotenv import dotenv_values
from mako.lookup import TemplateLookup

SETTINGS = {
    **dotenv_values(".env.chart"),
    **os.environ,  # override loaded values with environment variables
}

def render_chart_pkg(root_path: str):
    template_root_path = f"{root_path}/chart-pkg-template"
    tmpl_lookup = TemplateLookup(
        directories=[template_root_path],
        output_encoding="utf-8",
        input_encoding="utf-8",
        default_filters=["decode.utf8"],
        encoding_errors="replace"
    )
    print(f"Render for service:{SETTINGS['SERVICE_NAME']}...")

    values = {
        "service_name": SETTINGS["SERVICE_NAME"],
        "service_namespace": SETTINGS["SERVICE_NAMESPACE"],
        "service_api_version": SETTINGS["SERVICE_API_VERSION"],
        "service_app_version": SETTINGS["SERVICE_APP_VERSION"],
        "service_executor": SETTINGS["SERVICE_EXECUTOR"],
        "docker_image_name": SETTINGS["DOCKER_IMAGE_NAME"],
        "docker_image_tag": SETTINGS["DOCKER_IMAGE_TAG"],
        "docker_pull_secret": SETTINGS["DOCKER_PULL_SECRET"],
        "enable_k8s_service": SETTINGS["ENABLE_K8S_SERVICE"] == "true",
        "service_net_type": SETTINGS["SERVICE_NET_TYPE"],
        "enable_k8s_metrics": SETTINGS["ENABLE_K8S_METRICS"] == "true",
        "metrics_port": SETTINGS["METRICS_PORT"],
        "enable_k8s_service_http": SETTINGS["ENABLE_K8S_SERVICE_HTTP"] == "true",
        "service_net_http_port": SETTINGS["SERVICE_NET_HTTP_PORT"],
        "enable_k8s_service_grpc": SETTINGS["ENABLE_K8S_SERVICE_GRPC"] == "true",
        "service_net_grpc_port": SETTINGS["SERVICE_NET_GRPC_PORT"],
        "service_resource_usage_limit_cpu": SETTINGS["SERVICE_RESOURCE_USAGE_LIMIT_CPU"],
        "service_resource_usage_limit_mem": SETTINGS["SERVICE_RESOURCE_USAGE_LIMIT_MEM"],
        "service_resource_usage_request_cpu": SETTINGS["SERVICE_RESOURCE_USAGE_REQUEST_CPU"],
        "service_resource_usage_request_mem": SETTINGS["SERVICE_RESOURCE_USAGE_REQUEST_MEM"],
        "enable_k8s_ingress": SETTINGS["ENABLE_K8S_INGRESS"] == "true",
        "ingress_path": SETTINGS["INGRESS_PATH"]
    }
    template_path_list = [
        ("/Chart.yaml.tmpl", "Chart.yaml"),
        ("/delete.sh.tmpl", "delete.sh.yaml"),
        ("/install.sh.tmpl", "install.sh.yaml"),
        ("/values.yaml.tmpl", "values.yaml"),
        ("/templates/_helpers.tpl.tmpl", "templates/_helpers.tpl.yaml"),
        ("/templates/configmap.yaml.tmpl", "templates/configmap.yaml"),
        ("/templates/ingress.yaml.tmpl", "templates/ingress.yaml"),
        ("/templates/runner.yaml.tmpl", "templates/runner.yaml"),
        ("/templates/service.yaml.tmpl", "templates/service.yaml"),
        ("/templates/servicemonitor.yaml.tmpl", "templates/servicemonitor.yaml"),
    ]
    pathlib.Path(f"{root_path}/charts/{values['service_name']}/templates").mkdir(parents=True, exist_ok=True)
    for template_path in template_path_list:
        if template_path[0] == "/templates/service.yaml.tmpl" and (not values["enable_k8s_service"]):
            continue
        if template_path[0] == "/templates/ingress.yaml.tmpl" and (not values["enable_k8s_ingress"]):
            continue
        if template_path[0] == "/templates/servicemonitor.yaml.tmpl" and (not values["enable_k8s_metrics"]):
            continue

        template = tmpl_lookup.get_template(template_path[0])
        raw_content = template.render(**values)
        content = raw_content.decode("utf8")
        with open("{}/charts/{}/{}".format(root_path, values["service_name"], template_path[1]), "w") as fw:
            fw.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--render_root_path", help="root path", default="./devops/kubernates")
    args = parser.parse_args()
    render_chart_pkg(args.render_root_path)
