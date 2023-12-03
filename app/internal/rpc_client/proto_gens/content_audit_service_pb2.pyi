from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ContentAuditRequest(_message.Message):
    __slots__ = ["content", "use_local_filter", "use_vendor_filter"]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    USE_LOCAL_FILTER_FIELD_NUMBER: _ClassVar[int]
    USE_VENDOR_FILTER_FIELD_NUMBER: _ClassVar[int]
    content: str
    use_local_filter: bool
    use_vendor_filter: bool
    def __init__(self, content: _Optional[str] = ..., use_local_filter: bool = ..., use_vendor_filter: bool = ...) -> None: ...

class ContentAuditResponse(_message.Message):
    __slots__ = ["passed", "filter_type", "hitted_words"]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    FILTER_TYPE_FIELD_NUMBER: _ClassVar[int]
    HITTED_WORDS_FIELD_NUMBER: _ClassVar[int]
    passed: bool
    filter_type: int
    hitted_words: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, passed: bool = ..., filter_type: _Optional[int] = ..., hitted_words: _Optional[_Iterable[str]] = ...) -> None: ...
