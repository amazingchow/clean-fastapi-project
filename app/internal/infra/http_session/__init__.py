# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import requests

from contextvars import ContextVar
from requests.adapters import HTTPAdapter
from typing import Optional

_SESSION_MGR: ContextVar[Optional["requests.Session"]] = None
_AIO_SESSION_MGR: ContextVar[Optional["aiohttp.ClientSession"]] = None


async def init_session_mgr():
    global _SESSION_MGR
    global _AIO_SESSION_MGR

    _SESSION_MGR = ContextVar(
        "requests-session", default=requests.Session()
    )  # Acts as a global requests ClientSession that reuses connections.
    _AIO_SESSION_MGR = ContextVar(
        "aiohttp-session", default=aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=32),
            connector_owner=True,
            timeout=aiohttp.ClientTimeout(total=30),
        )
    )  # Acts as a global aiohttp ClientSession that reuses connections.
    await asyncio.sleep(0.01)
    

async def deinit_session_mgr():
    if _SESSION_MGR is not None:
        session = _SESSION_MGR.get()
        if session is not None:
            session.close()
    if _AIO_SESSION_MGR is not None:
        session = _AIO_SESSION_MGR.get()
        if session is not None:
            await session.close()


def get_session() -> Optional[requests.Session]:
    global _SESSION_MGR
    if _SESSION_MGR is None:
        _SESSION_MGR = ContextVar(
            "requests-session", default=requests.Session()
        )  # Acts as a global requests ClientSession that reuses connections.
    session = _SESSION_MGR.get()
    return session


def get_aio_session() -> Optional[aiohttp.ClientSession]:
    global _AIO_SESSION_MGR
    if _AIO_SESSION_MGR is None:
        _AIO_SESSION_MGR = ContextVar(
            "aiohttp-session", default=aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=32),
                connector_owner=True,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        )  # Acts as a global aiohttp ClientSession that reuses connections.
    session = _AIO_SESSION_MGR.get()
    return session
