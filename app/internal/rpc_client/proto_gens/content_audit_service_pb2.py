# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: content-audit-service.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1b\x63ontent-audit-service.proto\x12\x15\x63ontent_audit_service\"[\n\x13\x43ontentAuditRequest\x12\x0f\n\x07\x63ontent\x18\x01 \x01(\t\x12\x18\n\x10use_local_filter\x18\x02 \x01(\x08\x12\x19\n\x11use_vendor_filter\x18\x03 \x01(\x08\"Q\n\x14\x43ontentAuditResponse\x12\x0e\n\x06passed\x18\x01 \x01(\x08\x12\x13\n\x0b\x66ilter_type\x18\x02 \x01(\x05\x12\x14\n\x0chitted_words\x18\x03 \x03(\t2z\n\x13\x43ontentAuditService\x12\x63\n\x06\x46ilter\x12*.content_audit_service.ContentAuditRequest\x1a+.content_audit_service.ContentAuditResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'content_audit_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_CONTENTAUDITREQUEST']._serialized_start=54
  _globals['_CONTENTAUDITREQUEST']._serialized_end=145
  _globals['_CONTENTAUDITRESPONSE']._serialized_start=147
  _globals['_CONTENTAUDITRESPONSE']._serialized_end=228
  _globals['_CONTENTAUDITSERVICE']._serialized_start=230
  _globals['_CONTENTAUDITSERVICE']._serialized_end=352
# @@protoc_insertion_point(module_scope)
