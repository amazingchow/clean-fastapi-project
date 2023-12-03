# -*- coding: utf-8 -*-
import grpc

from internal.rpc_client.proto_gens import content_audit_service_pb2_grpc
from internal.rpc_client.proto_gens import infra_object_storage_service_pb2_grpc
from internal.rpc_client.proto_gens import url_shorten_service_pb2_grpc
from typing import Optional

_OSS_CLIENT_INST = None
_OSS_CLIENT_CONN = None
_CAS_CLIENT_INST = None
_CAS_CLIENT_CONN = None
_USS_CLIENT_INST = None
_USS_CLIENT_CONN = None

'''
参考资料

1. https://grpc.io/docs/guides/keepalive/
2. https://grpc.github.io/grpc/core/group__grpc__arg__keys.html
'''
CHANNEL_OPTIONS = [
    # After a duration of this time the client/server pings its peer to see if the transport is still alive.
    ("grpc.keepalive_time_ms", 60000),
    # After waiting for a duration of this time, if the keepalive ping sender does not receive the ping ack, it will close the transport.
    ("grpc.keepalive_timeout_ms", 10000),
]


def setup_oss_client(endpoint: str):
    global _OSS_CLIENT_INST
    global _OSS_CLIENT_CONN
    channel = grpc.insecure_channel(endpoint, options=CHANNEL_OPTIONS)
    _OSS_CLIENT_CONN = channel
    stub = infra_object_storage_service_pb2_grpc.InfraObjectStorageServiceStub(channel)
    _OSS_CLIENT_INST = stub


def get_oss_client() -> Optional[infra_object_storage_service_pb2_grpc.InfraObjectStorageServiceStub]:
    return _OSS_CLIENT_INST


def close_oss_client():
    if _OSS_CLIENT_CONN is not None:
        _OSS_CLIENT_CONN.close()


def setup_cas_client(endpoint: str):
    global _CAS_CLIENT_INST
    global _CAS_CLIENT_CONN
    channel = grpc.insecure_channel(endpoint, options=CHANNEL_OPTIONS)
    _CAS_CLIENT_CONN = channel
    stub = content_audit_service_pb2_grpc.ContentAuditServiceStub(channel)
    _CAS_CLIENT_INST = stub


def get_cas_client() -> Optional[content_audit_service_pb2_grpc.ContentAuditServiceStub]:
    return _CAS_CLIENT_INST


def close_cas_client():
    if _CAS_CLIENT_CONN is not None:
        _CAS_CLIENT_CONN.close()


def setup_uss_client(endpoint: str):
    global _USS_CLIENT_INST
    global _USS_CLIENT_CONN
    channel = grpc.insecure_channel(endpoint, options=CHANNEL_OPTIONS)
    _USS_CLIENT_CONN = channel
    stub = url_shorten_service_pb2_grpc.UrlShortenServiceStub(channel)
    _USS_CLIENT_INST = stub


def get_uss_client() -> Optional[url_shorten_service_pb2_grpc.UrlShortenServiceStub]:
    return _USS_CLIENT_INST


def close_uss_client():
    if _USS_CLIENT_CONN is not None:
        _USS_CLIENT_CONN.close()
