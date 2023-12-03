from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ListBucketsRequest(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class ListBucketsResponse(_message.Message):
    __slots__ = ["buckets"]
    BUCKETS_FIELD_NUMBER: _ClassVar[int]
    buckets: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, buckets: _Optional[_Iterable[str]] = ...) -> None: ...

class GetSignedUploadLinkRequest(_message.Message):
    __slots__ = ["bucket_name"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    def __init__(self, bucket_name: _Optional[str] = ...) -> None: ...

class GetSignedUploadLinkResponse(_message.Message):
    __slots__ = ["request_uri", "request_headers", "object_name"]
    class RequestHeadersEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    REQUEST_URI_FIELD_NUMBER: _ClassVar[int]
    REQUEST_HEADERS_FIELD_NUMBER: _ClassVar[int]
    OBJECT_NAME_FIELD_NUMBER: _ClassVar[int]
    request_uri: str
    request_headers: _containers.ScalarMap[str, str]
    object_name: str
    def __init__(self, request_uri: _Optional[str] = ..., request_headers: _Optional[_Mapping[str, str]] = ..., object_name: _Optional[str] = ...) -> None: ...
