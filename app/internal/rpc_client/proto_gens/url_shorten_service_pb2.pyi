from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ShortenUrlRequest(_message.Message):
    __slots__ = ["original_url"]
    ORIGINAL_URL_FIELD_NUMBER: _ClassVar[int]
    original_url: str
    def __init__(self, original_url: _Optional[str] = ...) -> None: ...

class ShortenUrlResponse(_message.Message):
    __slots__ = ["shortened_url_suffix"]
    SHORTENED_URL_SUFFIX_FIELD_NUMBER: _ClassVar[int]
    shortened_url_suffix: str
    def __init__(self, shortened_url_suffix: _Optional[str] = ...) -> None: ...

class RestoreUrlRequest(_message.Message):
    __slots__ = ["shortened_url_suffix"]
    SHORTENED_URL_SUFFIX_FIELD_NUMBER: _ClassVar[int]
    shortened_url_suffix: str
    def __init__(self, shortened_url_suffix: _Optional[str] = ...) -> None: ...

class RestoreUrlResponse(_message.Message):
    __slots__ = ["original_url"]
    ORIGINAL_URL_FIELD_NUMBER: _ClassVar[int]
    original_url: str
    def __init__(self, original_url: _Optional[str] = ...) -> None: ...
