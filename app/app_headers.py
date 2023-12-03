# -*- coding: utf-8 -*-
from fastapi.security.api_key import APIKeyHeader

auth_header_account = APIKeyHeader(name="x-sec-account", scheme_name="header for api account")
auth_header_token = APIKeyHeader(name="x-sec-token", scheme_name="header for api token")
