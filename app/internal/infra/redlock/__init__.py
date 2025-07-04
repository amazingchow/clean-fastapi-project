# -*- coding: utf-8 -*-
import asyncio
import random
import redis
import redis.asyncio as aio_redis
import redis.exceptions as redis_exceptions
import string
import time

from collections import namedtuple
from loguru import logger as loguru_logger
from typing import List, Optional, Tuple, Union

Lock = namedtuple("Lock", ("validity", "resource", "val"))


class CannotObtainLock(Exception):
    pass


class MultipleRedlockException(Exception):
    def __init__(self, errors, *args, **kwargs):
        super(MultipleRedlockException, self).__init__(*args, **kwargs)
        self.errors = errors

    def __str__(self):
        return " :: ".join([str(e) for e in self.errors])

    def __repr__(self):
        return self.__str__()


class Redlock(object):

    def __init__(
            self,
            connections: List[Union[redis.Redis, aio_redis.Redis]],
            async_mode: bool = True,
            retry_count: float = None,
            retry_delay: float = None
        ):

        self._async_mode = async_mode
        self._servers = connections
        self._quorum = (len(connections) // 2) + 1
        loguru_logger.debug("Redis Server Quorum:{}".format(self._quorum))

        default_retry_count = 3
        self.retry_count = retry_count or default_retry_count
        default_retry_delay = 0.2
        self.retry_delay = retry_delay or default_retry_delay
        self._clock_drift_factor = 0.01
        self._unlock_script = """if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("del",KEYS[1])
else
    return 0
end"""
        self._extend_script = """if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("pexpire",KEYS[1],ARGV[2])
else
    return 0
end"""

    async def _alock_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        try:
            assert isinstance(ttl, int), "ttl {} is not an integer".format(ttl)
        except AssertionError as e:
            raise ValueError(str(e))
        return await server.execute_command(f"SET {resource} {val} NX PX {ttl}") == b"OK"

    def _lock_instance(
            self,
            server: redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        try:
            assert isinstance(ttl, int), "ttl {} is not an integer".format(ttl)
        except AssertionError as e:
            raise ValueError(str(e))
        return server.execute_command(f"SET {resource} {val} NX PX {ttl}") == b"OK"

    async def _aunlock_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str
        ) -> bool:
        return await server.execute_command("EVAL", self._unlock_script, 1, resource, val) == 1

    def _unlock_instance(
            self,
            server: redis.Redis,
            resource: str,
            val: str
        ) -> bool:
        return server.execute_command("EVAL", self._unlock_script, 1, resource, val) == 1

    async def _aextend_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        return await server.execute_command("EVAL", self._extend_script, 1, resource, val, ttl) == 1

    def _extend_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        return server.execute_command("EVAL", self._extend_script, 1, resource, val, ttl) == 1

    def _get_unique_id(self) -> str:
        CHARACTERS = string.ascii_letters + string.digits
        return "".join([random.choice(CHARACTERS) for _ in range(22)])

    async def alock(self, resource: str, ttl: int) -> Tuple[bool, Optional[Lock]]:
        """To acquire a lock. Param ttl should be milliseconds."""
        retry = 0
        val = self._get_unique_id()

        # Add 2 milliseconds to the drift to account for Redis expires
        # precision, which is 1 millisecond, plus 1 millisecond min
        # drift for small TTLs.
        drift = int(ttl * self._clock_drift_factor) + 2

        redis_errors = []
        restart_attempt = True
        while restart_attempt:
            n = 0
            del redis_errors[:]

            st = int(time.time() * 1000)
            for server in self._servers:
                try:
                    ok = await self._alock_instance(server, resource, val, ttl)
                    if ok:
                        n += 1
                except redis_exceptions.RedisError as e:
                    redis_errors.append(e)
            ed = int(time.time() * 1000)
            elapsed_time = ed - st
            
            validity = int(ttl - elapsed_time - drift)
            if validity > 0 and n >= self._quorum:
                if len(redis_errors) > 0:
                    loguru_logger.error(f"Redlock Lock Error:{MultipleRedlockException(redis_errors)}")
                return (True, Lock(validity, resource, val))
            else:
                for server in self._servers:
                    try:
                        await self._aunlock_instance(server, resource, val)
                    except:
                        pass
                retry += 1
                restart_attempt = retry < self.retry_count
                if restart_attempt:
                    await asyncio.sleep(self.retry_delay)
        return (False, None)

    def lock(self, resource: str, ttl: int) -> Tuple[bool, Optional[Lock]]:
        """To acquire a lock. Param ttl should be milliseconds."""
        retry = 0
        val = self._get_unique_id()

        # Add 2 milliseconds to the drift to account for Redis expires
        # precision, which is 1 millisecond, plus 1 millisecond min
        # drift for small TTLs.
        drift = int(ttl * self._clock_drift_factor) + 2

        redis_errors = []
        restart_attempt = True
        while restart_attempt:
            n = 0
            del redis_errors[:]

            st = int(time.time() * 1000)
            for server in self._servers:
                try:
                    ok = self._lock_instance(server, resource, val, ttl)
                    if ok:
                        n += 1
                except redis_exceptions.RedisError as e:
                    redis_errors.append(e)
            ed = int(time.time() * 1000)
            elapsed_time = ed - st
            
            validity = int(ttl - elapsed_time - drift)
            if validity > 0 and n >= self._quorum:
                if len(redis_errors) > 0:
                    loguru_logger.error(f"Redlock Lock Error:{MultipleRedlockException(redis_errors)}")
                return (True, Lock(validity, resource, val))
            else:
                for server in self._servers:
                    try:
                        self._unlock_instance(server, resource, val)
                    except:
                        pass
                retry += 1
                restart_attempt = retry < self.retry_count
                if restart_attempt:
                    time.sleep(self.retry_delay)
        return (False, None)

    async def aunlock(self, lock: Lock) -> bool:
        """To release a lock you already own"""
        redis_errors = []
        for server in self._servers:
            try:
                await self._aunlock_instance(server, lock.resource, lock.val)
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Unlock Error:{MultipleRedlockException(redis_errors)}")
            return False
        return True

    def unlock(self, lock: Lock) -> bool:
        """To release a lock you already own"""
        redis_errors = []
        for server in self._servers:
            try:
                self._unlock_instance(server, lock.resource, lock.val)
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Unlock Error:{MultipleRedlockException(redis_errors)}")
            return False
        return True

    async def aextend(self, lock: Lock, ttl: int) -> bool:
        """To extend your ownership of a lock you already own. Param ttl should be milliseconds."""
        redis_errors = []
        n = 0
        for server in self._servers:
            try:
                ok = await self._aextend_instance(server, lock.resource, lock.val, ttl)
                if ok:
                    n += 1
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Extend Error:{MultipleRedlockException(redis_errors)}")
        return n >= self._quorum

    def extend(self, lock: Lock, ttl: int) -> bool:
        """To extend your ownership of a lock you already own. Param ttl should be milliseconds."""
        redis_errors = []
        n = 0
        for server in self._servers:
            try:
                ok = self._extend_instance(server, lock.resource, lock.val, ttl)
                if ok:
                    n += 1
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Extend Error:{MultipleRedlockException(redis_errors)}")
        return n >= self._quorum

_instance: Redlock = None


def init_instance(connections: List[aio_redis.Redis], retry_count: float = None, retry_delay: float = None):
    global _instance
    _instance = Redlock(connections, retry_count, retry_delay)


def instance() -> Redlock:
    return _instance
