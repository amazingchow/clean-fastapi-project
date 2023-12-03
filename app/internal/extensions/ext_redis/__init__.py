# -*- coding: utf-8 -*-
import asyncio
import jsonschema
import redis.asyncio as aio_redis
import redis.exceptions as redis_exceptions
import time

from internal.infra.alarm import perror
from internal.singleton import Singleton
from internal.utils.helper import get_midnight_timestamp
from loguru import logger as loguru_logger
from typing import Any, \
    Dict, \
    List, \
    Optional, \
    Tuple, \
    Union


class RedisClientSetupException(Exception):
    pass


class RedisClient(metaclass=Singleton):
    '''
    Redis自定义客户端
    '''

    DB_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string"},
            "password": {"type": "string"},
            "db": {"type": "number"},
        },
        "required": [
            "endpoint",
            "password",
            "db",
        ],
    }
    
    def __init__(self, client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None) -> None:
        if not self._validate_config(client_conf):
            raise RedisClientSetupException("Please provide valid redis config file.")

        host, port = client_conf["endpoint"].split(":")[0], int(client_conf["endpoint"].split(":")[1])
        self._conn = aio_redis.Redis(
            host=host,
            port=port,
            password=client_conf["password"],
            db=client_conf["db"],
            socket_timeout=5,
            socket_connect_timeout=2,
        )

    def _validate_config(self, conf: Optional[Dict[str, Any]] = None) -> bool:
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=self.DB_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid redis config:{conf}.")
        finally:
            return valid

    async def is_connected(self) -> bool:
        connected = False
        try:
            connected = await self._conn.ping()
        except redis_exceptions.RedisError:
            raise RedisClientSetupException("Please check connectivity with redis server.")
        finally:
            return connected

    def get_connection(self) -> aio_redis.Redis:
        return self._conn

    async def init_cache(self, pairs: List[Tuple[str, Union[str, int]]]) -> bool:
        done = True
        for kv in pairs:
            if isinstance(kv[1], str):
                done = await self.cache_string(kv[0], kv[1])
            elif isinstance(kv[1], int):
                done = await self.cache_integer(kv[0], kv[1])
            if not done:
                break
        return done
        
    async def cache_string(self, key: str, value: str, ttl: int = 0) -> bool:
        done = False
        try:
            if ttl > 0:
                await self._conn.execute_command("SET", key, value, "EX", ttl)
            else:
                await self._conn.execute_command("SET", key, value)
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to set value for key:{key}.")
        except Exception as e:
            await perror(f"Failed to set value for key:{key}, err:{e}")
        finally:
            return done

    async def exist_or_get_string(self, key: str) -> Tuple[Optional[str], bool, bool]:
        value = None
        existed = False
        done = False
        try:
            value = await self._conn.execute_command("GET", key)
            if value is not None and isinstance(value, bytes):
                value = value.decode("utf-8")
                existed = True
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to get value for key:{key}.")
        except Exception as e:
            await perror(f"Failed to get value for key:{key}, err:{e}")
        finally:
            return (value, existed, done)

    async def cache_integer(self, key: str, value: int, ttl: int = 0) -> bool:
        done = False
        try:
            if ttl > 0:
                await self._conn.execute_command("SET", key, value, "EX", ttl)
            else:
                await self._conn.execute_command("SET", key, value)
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to set value for key:{key}.")
        except Exception as e:
            await perror(f"Failed to set value for key:{key}, err:{e}")
        finally:
            return done

    async def incr_integer(self, key: str) -> bool:
        done = False
        try:
            await self._conn.execute_command("INCR", key)
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to incr for key:{key}.")
        except Exception as e:
            await perror(f"Failed to incr for key:{key}, err:{e}")
        finally:
            return done

    async def decr_integer(self, key: str) -> bool:
        done = False
        try:
            await self._conn.execute_command("DECR", key)
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to decr for key:{key}.")
        except Exception as e:
            await perror(f"Failed to decr for key:{key}, err:{e}")
        finally:
            return done

    async def exist_or_get_integer(self, key: str) -> Tuple[Optional[int], bool, bool]:
        value = None
        existed = False
        done = False
        try:
            value = await self._conn.execute_command("GET", key)
            if value is not None and isinstance(value, bytes):
                value = int(value.decode("utf-8"))
                existed = True
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to get value for key:{key}.")
        except Exception as e:
            await perror(f"Failed to get value for key:{key}, err:{e}")
        finally:
            return (value, existed, done)

    async def get_daily_token(self, key: str, total: int = 5) -> Tuple[int, bool]:
        remaining = 0
        done = False
        try:
            existed = await self._conn.execute_command("EXISTS", key)
            if existed == 0:
                remaining = total
            else:
                res = await self._conn.execute_command("GET", key)
                remaining = int(res)
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to get daily token for key:{key}.")
        except Exception as e:
            await perror(f"Failed to get daily token for key:{key}, err:{e}")
        finally:
            return (remaining, done)

    async def take_daily_token(self, key: str, total: int = 5) -> Tuple[int, bool]:
        remaining = 0
        done = False
        try:
            existed = await self._conn.execute_command("EXISTS", key)
            if existed == 0:
                remaining = total - 1
                await self._conn.execute_command("SET", key, remaining)
                await self._conn.execute_command("EXPIRE", key, get_midnight_timestamp() - int(time.time()))
            else:
                res = await self._conn.execute_command("GET", key)
                old_remaining = int(res)
                if old_remaining > 0:
                    remaining = old_remaining - 1
                    await self._conn.execute_command("SET", key, remaining)
                    await self._conn.execute_command("EXPIRE", key, get_midnight_timestamp() - int(time.time()))
                else:
                    remaining = old_remaining
            done = True
        except redis_exceptions.TimeoutError:
            await perror(f"Timeout to take daily token for key:{key}.")
        except Exception as e:
            await perror(f"Failed to take daily token for key:{key}, err:{e}")
        finally:
            return (remaining, done)

    async def close(self):
        await self._conn.aclose()


_instance: RedisClient = None


def init_instance(client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
    global _instance
    _instance = RedisClient(client_conf, io_loop)


def instance() -> RedisClient:
    return _instance
