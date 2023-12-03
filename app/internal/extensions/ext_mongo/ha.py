# -*- coding: utf-8 -*-
import asyncio
import datetime
import jsonschema
import logging
import pymongo
import pymongo.errors as perrors
import pymongoexplain
import time
import ujson as json

from dependencies import settings
from internal.infra.alarm import perror
from internal.singleton import Singleton
from internal.utils.helper import new_uid
from loguru import logger as loguru_logger
from motor.motor_asyncio import AsyncIOMotorClient
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing import Any, \
    Callable, \
    Dict, \
    List, \
    Optional, \
    Tuple


def _create_retry_decorator(min_secs: int = 1, max_secs: int = 60, max_retries: int = 3) -> Callable[[Any], Any]:
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=min_secs, max=max_secs),
        retry=(
            # When the client was unable to find an available server to
            # run the operation within the given timeout.
            retry_if_exception_type(perrors.ServerSelectionTimeoutError)
            # When either the client was unable to establish a connection
            # within the given timeout or the operation was sent but the
            # server was not able to respond in time.
            | retry_if_exception_type(perrors.NetworkTimeout)
            # When the server cancelled the operation because it exceeded
            # the given timeout. Note that the operation may have partially
            # completed on the server (depending on the operation).
            # Or When the client cancelled the operation because it was not
            # possible to complete within the given timeout.
            | retry_if_exception_type(perrors.ExecutionTimeout)
            # When the client attempted a write operation but the server could
            # not replicate that write (according to the configured write
            # concern) within the given timeout.
            | retry_if_exception_type(perrors.WTimeoutError)
            # The same error as WTimeoutError but for insert_many() or bulk_write().
            | retry_if_exception_type(perrors.BulkWriteError)
        ),
        before_sleep=before_sleep_log(loguru_logger, logging.WARNING),
    )


retry_decorator = _create_retry_decorator()


class MongoClientSetupException(Exception):
    pass


class MongoClient(metaclass=Singleton):
    '''
    MongoDB自定义客户端
    '''

    DB_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "endpoints": {"type": "array"},
            "username": {"type": "string"},
            "password": {"type": "string"},
            "auth_mechanism": {"type": "string"},
            "database": {"type": "string"},
            "replica_set": {"type": "string"},
        },
        "required": [
            "endpoints",
            "username",
            "password",
            "auth_mechanism",
            "database",
            "replica_set",
        ],
    }

    def __init__(self, client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
        '''
        Every MongoClient instance has a built-in connection pool per server in your MongoDB topology.
        '''
        if not self._validate_config(client_conf):
            raise MongoClientSetupException("Please provide mongodb config file.")
        
        if io_loop is not None:
            self._client = AsyncIOMotorClient(
                "mongodb://{}/".format(client_conf["endpoints"][0]),
                directConnection=False,
                timeoutMS=3000,
                socketTimeoutMS=5000,
                connectTimeoutMS=2000,
                serverSelectionTimeoutMS=2000,
                w=2,
                replicaSet=client_conf["replica_set"],
                readPreference="secondary",
                username=client_conf["username"],
                password=client_conf["password"],
                authSource="admin",
                authMechanism=client_conf["auth_mechanism"],
                io_loop=io_loop,
            )
        else:
            self._client = AsyncIOMotorClient(
                "mongodb://{}/".format(client_conf["endpoints"][0]),
                directConnection=False,
                timeoutMS=3000,
                socketTimeoutMS=5000,
                connectTimeoutMS=2000,
                serverSelectionTimeoutMS=2000,
                w=2,
                replicaSet=client_conf["replica_set"],
                readPreference="secondary",
                username=client_conf["username"],
                password=client_conf["password"],
                authSource="admin",
                authMechanism=client_conf["auth_mechanism"],
            )
        self._db = self._client[f"ha_{client_conf['database']}_{settings.DEPLOY_ENV}"]

    def _validate_config(self, conf: Optional[Dict[str, Any]] = None) -> bool:
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=self.DB_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid mongodb config:{conf}.")
        finally:
            return valid

    async def is_connected(self) -> bool:
        connected = False
        try:
            res = await self._db.command("ping")
            connected = res["ok"] == 1.0
            if connected:
                loguru_logger.debug(f"NODES ==> {self._client.nodes}")
                self._db_session = await self._client.start_session(causal_consistency=True)
        except perrors.ServerSelectionTimeoutError as exc:
            loguru_logger.error(f"Cannot select the master server, err:{exc}.")
        finally:
            return connected

    async def init_indexes(self) -> bool:
        done = False
        try:
            # 用户档案数据存储文档
            self._user_profile_store = self._db["user_profile"]
            await self._user_profile_store.create_index("uid", unique=True)
            await self._user_profile_store.create_index("account", unique=False)
            await self._user_profile_store.create_index("account_usr", unique=False)
            await self._user_profile_store.create_index("device_id", unique=False)
            await self._user_profile_store.create_index("create_ts", unique=False)
            await self._user_profile_store.create_index("is_deleted", unique=False)
            # 用于用户注销再注册后, 老账号能保留数据, 新账号的数据为空
            self._user_profile_store_s = self._db["user_profile_for_bad_man"]
            await self._user_profile_store_s.create_index("uid", unique=True)
            await self._user_profile_store_s.create_index("account", unique=False)
            await self._user_profile_store_s.create_index("account_usr", unique=False)
            await self._user_profile_store_s.create_index("device_id", unique=False)
            await self._user_profile_store_s.create_index("create_ts", unique=False)
            await self._user_profile_store_s.create_index("is_deleted", unique=False)
            # 用户反馈数据存储文档
            self._user_feedback_store = self._db["user_feedback"]
            await self._user_feedback_store.create_index(
                [
                    ("account", pymongo.ASCENDING),
                    ("create_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            # 应用程序权限数据存储文档
            self._app_permission_store = self._db["app_permission"]
            await self._app_permission_store.create_index(
                [
                    ("device_id", pymongo.ASCENDING),
                    ("permission_type", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            # 用户专属AI玩伴数据存储文档
            self._personal_ai_player_store = self._db["personal_ai_player"]
            await self._personal_ai_player_store.create_index("uid", unique=True)
            await self._personal_ai_player_store.create_index("pid", unique=False)
            await self._personal_ai_player_store.create_index("create_ts", unique=False)
            # 用户游戏账号数据存储文档
            self._personal_game_account_store = self._db["personal_game_account"]
            await self._personal_game_account_store.create_index("uid", unique=True)
            await self._personal_game_account_store.create_index("info_confirmed", unique=False)
            await self._personal_game_account_store.create_index("update_ts", unique=False)
            # 用户游戏对战数据存储文档
            self._personal_game_result_store = self._db["personal_game_result"]
            await self._personal_game_result_store.create_index("uid", unique=True)
            await self._personal_game_result_store.create_index("update_ts", unique=False)
            # 用户专属邀请码数据存储文档
            self._personal_invite_code_store = self._db["personal_invite_code"]
            await self._personal_invite_code_store.create_index("uid", unique=True)
            await self._personal_invite_code_store.create_index("code", unique=False)
            await self._personal_invite_code_store.create_index("create_ts", unique=False)
            # 用户专属邀请码使用情况数据存储文档
            self._personal_invite_code_usage_store = self._db["personal_invite_code_usage"]
            await self._personal_invite_code_usage_store.create_index(
                [
                    ("uid_f", pymongo.ASCENDING),
                    ("create_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            # 用户游戏对战结果数据存储文档
            self._game_result_store = self._db["game_result"]
            await self._game_result_store.create_index(
                [
                    ("app_uid", pymongo.ASCENDING),
                    ("create_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            # 用户私聊数据存储文档
            self._chat_store = self._db["chat"]
            await self._chat_store.create_index(
                [
                    ("uid", pymongo.ASCENDING),
                    ("pid", pymongo.ASCENDING),
                    ("create_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            self._chat_counter_store = self._db["chat_counter"]
            await self._chat_counter_store.create_index(
                [
                    ("uid", pymongo.ASCENDING),
                    ("pid", pymongo.ASCENDING),
                    ("create_ts", pymongo.DESCENDING),
                ],
                unique=True,
            )
            # 游戏信息库
            self._installed_game_store = self._db["installed_games"]
            await self._installed_game_store.create_index("index", unique=True)
            await self._installed_game_store.create_index("update_ts", unique=False)
            # AI角色信息库
            self._installed_ai_player_store = self._db["installed_ai_players"]
            await self._installed_ai_player_store.create_index("id", unique=True)
            await self._installed_ai_player_store.create_index("game_index", unique=False)
            await self._installed_ai_player_store.create_index("update_ts", unique=False)
            # AI角色开设的房间
            self._installed_game_room_store = self._db["installed_game_rooms"]
            await self._installed_game_room_store.create_index("id", unique=True)
            await self._installed_game_room_store.create_index("in_game_queue_be_ready_user_cnt", unique=False)
            await self._installed_game_room_store.create_index(
                [
                    ("game_index", pymongo.ASCENDING),
                    ("be_hosting", pymongo.ASCENDING),
                    ("rank_weight", pymongo.ASCENDING),
                    ("in_game_queue_user_cnt", pymongo.ASCENDING),
                    ("online_user_cnt", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=False,
            )
            # 房间内的（在线/离线）用户
            self._game_room_online_users_store = self._db["game_room_online_users"]
            await self._game_room_online_users_store.create_index(
                [
                    ("room_id", pymongo.ASCENDING),
                    ("user_id", pymongo.ASCENDING),
                    ("online", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=False,
            )
            # 房间内的车队（内/外）用户
            self._game_room_in_game_queue_users_store = self._db["game_room_in_game_queue_users"]
            await self._game_room_in_game_queue_users_store.create_index(
                [
                    ("room_id", pymongo.ASCENDING),
                    ("user_id", pymongo.ASCENDING),
                    ("in_game_queue", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=False,
            )
            # 房间内的车队中（已/未）准备就绪用户
            self._game_room_in_game_queue_be_ready_users_store = self._db["game_room_in_game_queue_be_ready_users"]
            await self._game_room_in_game_queue_be_ready_users_store.create_index(
                [
                    ("room_id", pymongo.ASCENDING),
                    ("user_id", pymongo.ASCENDING),
                    ("in_game_queue_be_ready", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=False,
            )
            # 房间内的车队中（进入/结束游戏）用户
            self._game_room_in_game_battle_users_store = self._db["game_room_in_game_battle_users"]
            await self._game_room_in_game_battle_users_store.create_index(
                [
                    ("room_id", pymongo.ASCENDING),
                    ("user_id", pymongo.ASCENDING),
                    ("in_game_battle", pymongo.ASCENDING),
                    ("update_ts", pymongo.DESCENDING),
                ],
                unique=False,
            )
            # 房间信息库
            self._game_room_store = self._db["game_rooms"]
            await self._game_room_store.create_index("id", unique=True)
            await self._game_room_store.create_index("game_index", unique=False)
            await self._game_room_store.create_index("update_ts", unique=False)

            done = True
        except perrors.PyMongoError as exc:
            done = False
            if exc.timeout:
                loguru_logger.warning("Timeout to init indexes.")
            else:
                loguru_logger.warning(f"Failed to init indexes, err:{exc}.")
        except Exception as exc:
            loguru_logger.error(f"Failed to init indexes, err:{exc}.")
        finally:
            return done

    async def init(self) -> bool:
        done = False
        try:
            self._user_cnt = await self._user_profile_store.count_documents({})
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                loguru_logger.error("Timeout to get total user count.")
            else:
                loguru_logger.error(f"Failed to get total user count, err:{exc}.")
        except Exception as exc:
            loguru_logger.error(f"Failed to get total user count, err:{exc}.")
        finally:
            return done

    @property
    def user_cnt(self):
        return self._user_cnt

    @retry_decorator
    async def init_user_account(self, uid: Optional[str], account: str, device_type: int, device_id: str, jpush_registration_id: str, do_recreate: bool = False):
        query = {"account": account}
        _uid = uid if uid else new_uid()
        update_ts = int(time.time())
        create_ts = update_ts
        update = {"$set": {
            # unique user id (auto-generated by our service)
            "uid": _uid,
            # account, cell-phone number or account from wechat/qq/apple, etc...
            "account": account,
            # username for system account (generated by system, 'User_' + uid)
            "account_usr": _uid,
            # hashed password for system account, optional
            "account_pwd": "",
            # extra_info
            "device_type": device_type,
            # extra_info
            "device_id": device_id,
            # extra_info
            "jpush_registration_id": jpush_registration_id,
            # extra_info
            "nickname": "",
            # extra_info
            "gendor": 0,
            # extra_info
            "avatar": "",
            # extra_info
            "birthday": "",
            # extra_info
            "age": 0,
            # extra_info, 已经废除免费剩余次数的功能, 故这里直接设置为一百万
            "extra_free_play_cnt": 1000000,
            # extra_info
            "extra_invited_user_cnt": 0,
            # user profile created time (auto-generated by our service)
            "create_ts": create_ts,
            # user profile updated time (auto-generated by our service)
            "update_ts": update_ts,
            "is_online": False,
            "is_deleted": False,
            "delete_reason": "",
        }}
        if do_recreate:
            await self._user_profile_store_s.update_one(query, update, upsert=True)
        else:
            await self._user_profile_store.update_one(query, update, upsert=True)

    async def set_user_profile(self, profile: Dict[str, Any]) -> Tuple[int, bool]:
        update_ts = None
        done = False
        try:
            query = {"uid": profile["uid"], "is_deleted": False}
            update_ts = int(time.time())
            update = {"$set": {
                "nickname": profile["nickname"],
                "gendor": profile["gendor"],
                "avatar": profile["avatar"],
                "birthday": profile["birthday"],
                "age": datetime.date.today().year - int(profile["birthday"][:4]),
                "update_ts": update_ts,
            }}
            
            is_recreated, _ = await self.is_user_account_recreated(uid=profile["uid"])
            if is_recreated:
                await self._user_profile_store_s.update_one(query, update, upsert=True)
            else:
                await self._user_profile_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to set profile for user:{profile['uid']}.")
            else:
                await perror(f"Failed to set profile for user:{profile['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to set profile for user:{profile['uid']}, err:{exc}.")
        finally:
            return (update_ts, done)

    async def set_user_profile_extra_info(self, extra: Dict[str, Any]) -> bool:
        done = False
        try:
            if extra["extra_info_type"] == "invite":
                # 邀请了新用户, 增加陪玩次数
                query = {"uid": extra["uid"], "is_deleted": False}
                doc = await self._user_profile_store.find_one(query)
                if doc is not None:
                    profile = doc
                    update_ts = int(time.time())
                    update = {"$set": {
                        "extra_free_play_cnt": profile.get("extra_free_play_cnt", 3) + extra["incr_free_play_cnt"],
                        "extra_invited_user_cnt": profile.get("extra_invited_user_cnt", 0) + 1,
                        "update_ts": update_ts,
                    }}
                    await self._user_profile_store.update_one(query, update, upsert=True)
            elif extra["extra_info_type"] == "play":
                # 开始了新的对局, 扣除陪玩次数
                query = {"uid": extra["uid"], "is_deleted": False}
                doc = await self._user_profile_store.find_one(query)
                if doc is not None:
                    profile = doc
                    update_ts = int(time.time())
                    update = {"$set": {
                        "extra_free_play_cnt": profile.get("extra_free_play_cnt", 3) + extra["incr_free_play_cnt"],
                        "update_ts": update_ts,
                    }}
                    await self._user_profile_store.update_one(query, update, upsert=True)
            elif extra["extra_info_type"] == "device":
                # 更新设备类型和设备ID
                query = {"uid": extra["uid"], "is_deleted": False}
                update_ts = int(time.time())
                update = {"$set": {
                    "device_type": extra["device_type"],
                    "device_id": extra["device_id"],
                    "jpush_registration_id": extra["jpush_registration_id"],
                    "update_ts": update_ts,
                }}
                await self._user_profile_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to set profile for user:{extra['uid']}.")
            else:
                await perror(f"Failed to set profile for user:{extra['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to set profile for user:{extra['uid']}, err:{exc}.")
        finally:
            return done

    async def get_user_profile(self, uid: Optional[str] = None, account: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], bool]:
        profile = None
        done = False
        try:
            is_recreated = False
            if uid is not None:
                query = {"uid": uid}
                is_recreated, _ = await self.is_user_account_recreated(uid=uid)
            elif account is not None:
                query = {"account": account}
                is_recreated, _ = await self.is_user_account_recreated(account=account)

            if is_recreated:
                doc = await self._user_profile_store_s.find_one(query)
            else:
                doc = await self._user_profile_store.find_one(query)
            if doc is not None:
                profile = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get profile for user:{uid}.")
            else:
                await perror(f"Failed to get profile for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get profile for user:{uid}, account:{account}, err:{exc}.")
        finally:
            return (profile, done)

    async def set_user_online(self, account: str, online: bool) -> bool:
        done = False
        try:
            query = {"account": account, "is_deleted": False}
            update_ts = int(time.time())
            update = {"$set": {
                "is_online": online,
                "update_ts": update_ts,
            }}
            
            is_recreated, _ = await self.is_user_account_recreated(account=account)
            if is_recreated:
                await self._user_profile_store_s.update_one(query, update, upsert=True)
            else:
                await self._user_profile_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to set online status for account:{account}.")
            else:
                await perror(f"Failed to set online status for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to set online status for account:{account}, err:{exc}.")
        finally:
            return done

    async def delete_user_account(self, account: str, do_delete: bool, delete_reason: str = "") -> bool:
        done = False
        try:
            query = {"account": account}
            update_ts = int(time.time())
            if do_delete:
                update = {"$set": {
                    "is_deleted": True,
                    "delete_reason": delete_reason,
                    "update_ts": update_ts,
                }}
            else:
                update = {"$set": {
                    "is_deleted": False,
                    "update_ts": update_ts,
                }}
            await self._user_profile_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to set deleted status for account:{account}.")
            else:
                await perror(f"Failed to set deleted status for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to set deleted status for account:{account}, err:{exc}.")
        finally:
            return done

    async def is_user_account_deleted(self, account: str) -> Tuple[bool, Optional[str], bool]:
        is_deleted = False
        uid = None
        done = False
        try:
            query = {"account": account}
            doc = await self._user_profile_store.find_one(query)
            if doc is not None:
                is_deleted = doc["is_deleted"]
                uid = doc["uid"]
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query profile for account:{account}.")
            else:
                await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        finally:
            return (is_deleted, uid, done)

    async def is_user_account_created(self, account: str) -> Tuple[bool, Optional[str], bool]:
        is_created = False
        uid = None
        done = False
        try:
            query = {"account": account, "is_deleted": False}
            doc = await self._user_profile_store.find_one(query)
            if doc is not None:
                is_created = True
                uid = doc["uid"]
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query profile for account:{account}.")
            else:
                await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        finally:
            return (is_created, uid, done)
        
    async def is_user_account_recreated(self, uid: Optional[str] = None, account: Optional[str] = None) -> Tuple[bool, bool]:
        is_recreated = False
        done = False
        try:
            if uid is not None:
                query = {"uid": uid, "is_deleted": False}
            elif account is not None:
                query = {"account": account, "is_deleted": False}
            doc = await self._user_profile_store_s.find_one(query)
            if doc is not None:
                is_recreated = True
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query profile for account:{account}.")
            else:
                await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        finally:
            return (is_recreated, done)

    async def is_user_account_activation_expired(self, account: str) -> Tuple[bool, bool]:
        is_expired = True
        done = False
        try:
            query = {"account": account, "is_deleted": True}
            doc = await self._user_profile_store.find_one(query)
            if doc is not None:
                is_expired = (int(time.time()) - doc["update_ts"]) > 15 * 24 * 3600
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query profile for account:{account}.")
            else:
                await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query profile for account:{account}, err:{exc}.")
        finally:
            return (is_expired, done)

    async def add_user_feedback(self, feedback: Dict[str, Any]) -> bool:
        done = False
        try:
            create_ts = int(time.time())
            doc = {
                "account": feedback["account"],
                "content": feedback["content"],
                "image_list": feedback["image_list"],
                "contact_info": feedback["contact_info"],
                "log_link": feedback["log_link"],
                "create_ts": create_ts,
            }
            await self._user_feedback_store.insert_one(doc)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to add new feedback for account:{feedback['account']}.")
            else:
                await perror(f"Failed to add new feedback for account:{feedback['account']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to add new feedback for account:{feedback['account']}, err:{exc}.")
        finally:
            return done

    async def query_user_feedback(self, account: str, n: int = 3) -> Tuple[List[Dict[str, Any]], bool]:
        feedback_list: List[Dict[str, Any]] = []
        done = False
        try:
            query = {"account": account}
            f = lambda doc, x: doc[x] if x in doc else None
            async for doc in self._user_feedback_store.find(query).sort([("create_ts", -1)]).limit(n):
                feedback_list.append(
                    {
                        "account": f(doc, "account"),
                        "content": f(doc, "content"),
                        "image_list": f(doc, "image_list"),
                        "contact_info": f(doc, "contact_info"),
                        "log_link": f(doc, "log_link"),
                    }
                )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query feedback for account:{account}.")
            else:
                await perror(f"Failed to query feedback for account:{account}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query feedback for account:{account}, err:{exc}")
        finally:
            return (feedback_list, done)
        
    async def upsert_app_permission(self, permission: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"device_id": permission["device_id"], "permission_type": permission["permission_type"]}
            update_ts = int(time.time())
            update = {"$set": {
                "device_id": permission["device_id"],
                "permission_type": permission["permission_type"],
                "permission_open": permission["permission_open"],
                "update_ts": update_ts,
            }}
            await self._app_permission_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert app permission:{permission['permission_type']} for device:{permission['device_id']}.")
            else:
                await perror(f"Failed to upsert app permission:{permission['permission_type']} for device:{permission['device_id']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert app permission:{permission['permission_type']} for device:{permission['device_id']}, err:{exc}.")
        finally:
            return done

    async def query_all_app_permissions(self, device_id: str, n: int = 10) -> Tuple[List[Dict[str, Any]], bool]:
        permissions: List[Dict[str, Any]] = []
        done = False
        try:
            query = {"device_id": device_id}
            async for doc in self._app_permission_store.find(query).sort([("update_ts", -1)]).limit(n):
                if doc is not None:
                    permissions.append(
                        {
                            "device_id": doc["device_id"],
                            "permission_type": doc["permission_type"],
                            "permission_open": doc["permission_open"],
                        }
                    )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query permissions for device:{device_id}.")
            else:
                await perror(f"Failed to query permissions for device:{device_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query permissions for device:{device_id}, err:{exc}")
        finally:
            return (permissions, done)

    async def upsert_personal_ai_player(self, settings: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"uid": settings["uid"]}
            create_ts = int(time.time())
            update = {"$set": {
                "uid": settings["uid"],
                "account": settings["account"],
                "ai_player_uid": settings["ai_player_uid"],
                "pid": settings["pid"],
                "nickname": settings["nickname"],
                "gendor": settings["gendor"],
                "avatar": settings["avatar"],
                "character": settings["character"],
                "game": settings["game"],
                "game_region": settings["game_region"],
                "game_location": settings["game_location"],
                "create_ts": create_ts,
            }}
            await self._personal_ai_player_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert ai player for user:{settings['uid']}.")
            else:
                await perror(f"Failed to upsert ai player for user:{settings['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert ai player for user:{settings['uid']}, err:{exc}.")
        finally:
            return done

    async def query_personal_ai_player(self, uid: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        ai_player = None
        done = False
        try:
            query = {"uid": uid}
            doc = await self._personal_ai_player_store.find_one(query)
            ai_player = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query ai player for user:{uid}.")
            else:
                await perror(f"Failed to query ai player for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query ai player for user:{uid}, err:{exc}.")
        finally:
            return (ai_player, done)

    async def upsert_personal_game_account(self, settings: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"uid": settings["uid"]}
            update_ts = int(time.time())
            update = {"$set": {
                "uid": settings["uid"],
                "game_region": settings["game_region"],
                "game_uid": settings["game_uid"],
                "game_nickname": settings["game_nickname"],
                "game_rank": settings["game_rank"],
                "game_location": settings["game_location"],
                "info_confirmed": False,
                "update_ts": update_ts,
            }}
            await self._personal_game_account_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert game account for user:{settings['uid']}.")
            else:
                await perror(f"Failed to upsert game account for user:{settings['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert game account for user:{settings['uid']}, err:{exc}.")
        finally:
            return done

    async def query_personal_game_account(self, uid: str) -> [Dict[str, Any], bool]:
        account = {}
        done = False
        try:
            query = {"uid": uid}
            doc = await self._personal_game_account_store.find_one(query)
            if doc is not None:
                account = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get game account for user:{uid}.")
            else:
                await perror(f"Failed to get game account for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get game account for user:{uid}, err:{exc}.")
        finally:
            return (account, done)

    @retry_decorator
    async def upsert_personal_game_result(self, result: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"uid": result["uid"]}
            update_ts = int(time.time())
            update = {"$set": {
                "uid": result["uid"],
                "play_cnt": result["play_cnt"],
                "winning_play_cnt": result["winning_play_cnt"],
                "win_rate": result["win_rate"],
                "update_ts": update_ts,
            }}
            await self._personal_game_result_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to update game result for user:{result['uid']}.")
            else:
                await perror(f"Failed to update game result for user:{result['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to update game result for user:{result['uid']}, err:{exc}.")
        finally:
            return done

    async def query_personal_game_result(self, uid: str) -> [Dict[str, Any], bool]:
        result = {}
        done = False
        try:
            query = {"uid": uid}
            doc = await self._personal_game_result_store.find_one(query)
            if doc is not None:
                result = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get game result for user:{uid}.")
            else:
                await perror(f"Failed to get game result for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get game result for user:{uid}, err:{exc}.")
        finally:
            return (result, done)

    async def upsert_personal_invite_code(self, icode: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"uid": icode["uid"]}
            create_ts = int(time.time())
            update = {"$set": {
                "uid": icode["uid"],
                "account": icode["account"],
                "code": icode["code"],
                "qr_code": icode["qr_code"],
                "vendor": icode["vendor"],
                "create_ts": create_ts,
            }}
            await self._personal_invite_code_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to add new invite code for user:{icode['uid']}.")
            else:
                await perror(f"Failed to add new invite code for user:{icode['uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to add new invite code for user:{icode['uid']}, err:{exc}.")
        finally:
            return done

    async def get_personal_invite_qr_code(self, uid: str) -> Tuple[Optional[str], bool]:
        qr_code = ""
        done = False
        try:
            query = {"uid": uid}
            doc = await self._personal_invite_code_store.find_one(query)
            if doc is not None:
                qr_code = doc["qr_code"]
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get qrcode for user:{uid}.")
            else:
                await perror(f"Failed to get qrcode for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get qrcode for user:{uid}, err:{exc}.")
        finally:
            return (qr_code, done)
        
    async def query_personal_invite_code(self, code: str) -> Tuple[str, bool]:
        uid = ""
        done = False
        try:
            query = {"code": code}
            doc = await self._personal_invite_code_store.find_one(query)
            if doc is not None:
                uid = doc["uid"]
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query invite code:{code}.")
            else:
                await perror(f"Failed to query invite code:{code}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query invite code:{code}, err:{exc}.")
        finally:
            return (uid, done)

    async def add_invite_code_usage_record(self, uid_f: str, uid_t: str) -> bool:
        done = False
        try:
            create_ts = int(time.time())
            doc = {
                "uid_f": uid_f,
                "uid_t": uid_t,
                "create_ts": create_ts,
            }
            await self._personal_invite_code_usage_store.insert_one(doc)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to add invite code usage record for user:{uid_f}.")
            else:
                await perror(f"Failed to add invite code usage record for user:{uid_f}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to add invite code usage record for user:{uid_f}, err:{exc}.")
        finally:
            return done

    @retry_decorator
    async def add_game_result(self, result: Dict[str, Any] = {}) -> bool:
        done = False
        try:
            create_ts = int(time.time())
            doc = result
            doc["create_ts"] = create_ts
            await self._game_result_store.insert_one(doc)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to add new game result for user:{result['app_uid']}.")
            else:
                await perror(f"Failed to add new game result for user:{result['app_uid']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to add new game result for user:{result['app_uid']}, err:{exc}.")
        finally:
            return done

    async def query_chat_history(self, uid: str, pid: str, offset: int = 0, limit: int = 10) -> Tuple[List[Dict[str, Any]], bool]:
        history: List[Dict[str, Any]] = []
        done = False
        try:
            query = {"uid": uid, "pid": pid}
            async for x in self._chat_store.find(query).sort([("create_ts", 1)]).skip(offset).limit(limit):
                history.append(
                    {
                        "message_id": x["message_id"],
                        "chat_type": x["chat_type"],
                        "chat": x["chat"],
                        "photo": x["photo"],
                        "audio": x["audio"],
                        "video": x["video"],
                        "inline_keyboard": x["inline_keyboard"] if x["inline_keyboard"] is not None else [],
                        "create_ts": x["create_ts"],
                    }
                )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to list chat history for user:{uid}.")
            else:
                await perror(f"Failed to list chat history for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to list chat history for user:{uid}, err:{exc}.")
        finally:
            return (history, done)

    async def query_chat_total_cnt(self, uid: str, pid: str) -> Tuple[int, bool]:
        total_cnt = 0
        done = False
        try:
            query = {"uid": uid, "pid": pid}
            doc = await self._chat_counter_store.find_one(query)
            if doc is not None:
                total_cnt = doc["total_cnt"]
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get chat total cnt for user:{uid}.")
            else:
                await perror(f"Failed to get chat total cnt for user:{uid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get chat total cnt for user:{uid}, err:{exc}.")
        finally:
            return (total_cnt, done)

    async def upsert_game_info(self, game: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"index": game["index"]}
            update_ts = int(time.time())
            update = {"$set": {
                "index": game["index"],
                "en_name": game["en_name"],
                "zh_name": game["zh_name"],
                "logo": game["logo"],
                "slogan": game["slogan"],
                "tags": game["tags"],
                "min_online_user_cnt": game["min_online_user_cnt"],
                "max_online_user_cnt": game["max_online_user_cnt"],
                "extra": game["extra"],
                "update_ts": update_ts,
            }}
            await self._installed_game_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert game:{game['index']}.")
            else:
                await perror(f"Failed to upsert game:{game['index']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert game:{game['index']}, err:{exc}.")
        finally:
            return done

    async def list_games(self, offset: int = 0, limit: int = 5) -> Tuple[List[Dict[str, Any]], bool]:
        game_list: List[Dict[str, Any]] = []
        done = False
        try:
            async for x in self._installed_game_store.find().sort([("update_ts", -1)]).skip(offset).limit(limit):
                game_list.append(
                    {
                        "index": x["index"],
                        "en_name": x["en_name"],
                        "zh_name": x["zh_name"],
                        "logo": x["logo"],
                        "slogan": x["slogan"],
                        "tags": x["tags"],
                        "min_online_user_cnt": x["min_online_user_cnt"],
                        "max_online_user_cnt": x["max_online_user_cnt"],
                        "extra": x["extra"],
                    }
                )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror("Timeout to list games.")
            else:
                await perror(f"Failed to list games, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to list games, err:{exc}.")
        finally:
            return (game_list, done)

    async def query_game(self, game_index: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        game = None
        done = False
        try:
            query = {"index": game_index}
            doc = await self._installed_game_store.find_one(query)
            game = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get game:{game_index}.")
            else:
                await perror(f"Failed to get game:{game_index}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get game:{game_index}, err:{exc}.")
        finally:
            return (game, done)

    async def upsert_ai_player_info(self, ai_player: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"id": ai_player["id"]}
            doc = await self._installed_ai_player_store.find_one(query)
            state = 0
            if doc is not None:
                state = doc["state"]
            update_ts = int(time.time())
            update = {"$set": {
                "id": ai_player["id"],
                "room_id": ai_player["room_id"],
                "is_master": ai_player["is_master"],
                "slave_number": ai_player["slave_number"],
                "nickname": ai_player["nickname"],
                "gendor": ai_player["gendor"],
                "age": ai_player["age"],
                "avatar": ai_player["avatar"],
                "game_index": ai_player["game_index"],
                "self_text_intro": ai_player["self_text_intro"],
                "self_audio_intro": ai_player["self_audio_intro"],
                "self_audio_intro_secs": ai_player["self_audio_intro_secs"],
                "tags": ai_player["tags"],
                "state": state,
                "extra": ai_player["extra"],
                "update_ts": update_ts,
            }}
            await self._installed_ai_player_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert ai_player:{ai_player['id']}.")
            else:
                await perror(f"Failed to upsert ai_player:{ai_player['id']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert ai_player:{ai_player['id']}, err:{exc}.")
        finally:
            return done

    async def query_ai_player(self, aid: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        ai = None
        done = False
        try:
            query = {"id": aid}
            doc = await self._installed_ai_player_store.find_one(query)
            ai = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to get ai:{aid}.")
            else:
                await perror(f"Failed to get ai:{aid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to get ai:{aid}, err:{exc}.")
        finally:
            return (ai, done)

    async def update_ai_player_state(self, aid: str, state: int) -> bool:
        done = False
        try:
            query = {"id": aid}
            update_ts = int(time.time())
            update = {"$set": {
                "state": state,
                "update_ts": update_ts,
            }}
            await self._installed_ai_player_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to update state for ai_player:{aid}.")
            else:
                await perror(f"Failed to update state for ai_player:{aid}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to update state for ai_player:{aid}, err:{exc}.")
        finally:
            return done

    async def upsert_installed_game_room_info(self, room: Dict[str, Any], is_for_master: bool = True) -> bool:
        done = False
        try:
            query = {"id": room["id"]}
            update_ts = int(time.time())
            update = None
            if is_for_master:
                update = {"$set": {
                    "id": room["id"],
                    "game_index": room["game_index"],
                    "rule_title": room["rule_title"],
                    "rule_content": room["rule_content"],
                    "title": room["title"],
                    "cover": room["cover"],
                    "owner_id": room["master_id"],
                    "owner_nickname": room["master_nickname"],
                    "owner_gendor": room["master_gendor"],
                    "owner_avatar": room["master_avatar"],
                    "assistants": [],
                    "tags": room["tags"],
                    "announcement": room["announcement"],
                    "carrying_capacity": room["carrying_capacity"],
                    "queue_symbol": room["queue_symbol"],
                    "ai_player_cnt": room["ai_player_cnt"],
                    "rank_weight": room["rank_weight"],
                    "be_hosting": room["be_hosting"],
                    "update_ts": update_ts,
                }}

                # NOTE: 捞出来的是真实用户的状态, 需要加上每个房间内AI的数量
                n = await self._game_room_online_users_store.count_documents({"room_id": room["id"], "online": True})
                update["$set"]["online_user_cnt"] = n + room["ai_player_cnt"]
                n = await self._game_room_in_game_queue_users_store.count_documents({"room_id": room["id"], "in_game_queue": True})
                update["$set"]["in_game_queue_user_cnt"] = n + room["ai_player_cnt"]
                n = await self._game_room_in_game_queue_be_ready_users_store.count_documents({"room_id": room["id"], "in_game_queue_be_ready": True})
                update["$set"]["in_game_queue_be_ready_user_cnt"] = n + room["ai_player_cnt"]
                n = await self._game_room_in_game_battle_users_store.count_documents({"room_id": room["id"], "in_game_battle": True})
                update["$set"]["in_game_battle_user_cnt"] = n + room["ai_player_cnt"]
            else:
                assistants = [
                    {
                        "assistant_id": room["slave_id"],
                        "assistant_nickname": room["slave_nickname"],
                        "assistant_gendor": room["slave_gendor"],
                        "assistant_avatar": room["slave_avatar"],
                    }
                ]
                doc = await self._installed_game_room_store.find_one(query)
                if (doc is not None) and ("assistants" in doc) and isinstance(doc["assistants"], list) and len(doc["assistants"]) > 0:
                    assistants += doc["assistants"]
                update = {"$set": {
                    "assistants": assistants,
                    "update_ts": update_ts,
                }}

            await self._installed_game_room_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert game room:{room['id']}.")
            else:
                await perror(f"Failed to upsert game room:{room['id']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert game room:{room['id']}, err:{exc}.")
        finally:
            return done

    async def upsert_game_room_info(self, room: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"id": room["id"]}
            update_ts = int(time.time())
            update = {"$set": {
                "id": room["id"],
                "game_index": room["game_index"],
                "rule_title": room["rule_title"],
                "rule_content": room["rule_content"],
                "title": room["title"],
                "tags": room["tags"],
                "announcement": room["announcement"],
                "carrying_capacity": room["carrying_capacity"],
                "queue_symbol": room["queue_symbol"],
                "ai_player_cnt": room["ai_player_cnt"],
                "rank_weight": room["rank_weight"],
                "be_hosting": room["be_hosting"],
                "update_ts": update_ts,
            }}
            await self._game_room_store.update_one(query, update, upsert=True)
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to upsert game room:{room['id']}.")
            else:
                await perror(f"Failed to upsert game room:{room['id']}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to upsert raw game room:{room['id']}, err:{exc}.")
        finally:
            return done

    async def list_game_rooms(self, game_index: str = "lolm", offset: int = 0, limit: int = 10, use_fast_path: bool = False) -> Tuple[List[Dict[str, Any]], bool]:
        room_list: List[Dict[str, Any]] = []
        done = False
        try:
            sort_rules = [
                # 第一优先返回被运营托管的房间 (运营置顶)
                ("be_hosting", pymongo.DESCENDING),
                # 第二优先返回排序权重高的房间 (运营置顶)
                ("rank_weight", pymongo.DESCENDING),
                # 第三优先返回车队有空位的房间
                ("in_game_queue_user_cnt", pymongo.ASCENDING),
                # 第四优先返回在线人数高的房间
                ("online_user_cnt", pymongo.DESCENDING),
                # 第五优先返回最新更新的房间
                ("update_ts", pymongo.DESCENDING),
            ]
            if game_index == "all":
                query = {}
            else:
                query = {"game_index": game_index}
            async for x in self._installed_game_room_store.find(query).sort(sort_rules).skip(offset).limit(limit):
                if use_fast_path:
                    room_list.append({
                        "id": x["id"],
                        "game_index": x["game_index"],
                        "carrying_capacity": x["carrying_capacity"],
                        "queue_symbol": x["queue_symbol"],
                        "ai_player_cnt": x["ai_player_cnt"],
                        "online_user_cnt": x["online_user_cnt"],
                        "in_game_queue_user_cnt": x["in_game_queue_user_cnt"],
                        "in_game_queue_be_ready_user_cnt": x["in_game_queue_be_ready_user_cnt"],
                        "in_game_battle_user_cnt": x["in_game_battle_user_cnt"],
                    })
                else:
                    room = {
                        "id": x["id"],
                        "game_index": x["game_index"],
                        "rule_title": x["rule_title"],
                        "rule_content": x["rule_content"],
                        "title": x["title"],
                        "cover": x["cover"],
                        "tags": x["tags"],
                        "announcement": x["announcement"],
                        "carrying_capacity": x["carrying_capacity"],
                        "queue_symbol": x["queue_symbol"],
                        "ai_player_cnt": x["ai_player_cnt"],
                        "online_user_cnt": x["online_user_cnt"],
                        "in_game_queue_user_cnt": x["in_game_queue_user_cnt"],
                        "in_game_queue_be_ready_user_cnt": x["in_game_queue_be_ready_user_cnt"],
                        "in_game_battle_user_cnt": x["in_game_battle_user_cnt"],
                        "owner_id": x["owner_id"],
                        "owner_nickname": x["owner_nickname"],
                        "owner_avatar": x["owner_avatar"],
                        "be_hosting": x["be_hosting"],
                    }
                    if "assistants" in x:
                        room["assistants"] = x["assistants"]
                    room_list.append(room)
            if not use_fast_path:
                for i in range(len(room_list)):
                    room_id = room_list[i]["id"]
                    ai_master = {
                        "user_id": room_list[i]["owner_id"],
                        "user_nickname": room_list[i]["owner_nickname"],
                        "user_avatar": room_list[i]["owner_avatar"],
                        "is_ai": True,
                    }
                    if "assistants" in room_list[i]:
                        ai_slaves = [
                            {
                                "user_id": assistant["assistant_id"],
                                "user_nickname": assistant["assistant_nickname"],
                                "user_avatar": assistant["assistant_avatar"],
                                "is_ai": True,
                            } for assistant in room_list[i]["assistants"]
                        ]
                    else:
                        ai_slaves = []
                    # 返回N个在线用户
                    online_user_list, ok = await self.list_game_room_online_users(room_id=room_id)
                    if ok:
                        online_user_list = [ai_master] + ai_slaves + online_user_list
                    else:
                        online_user_list = [ai_master] + ai_slaves
                    room_list[i]["online_users"] = online_user_list
                    # 返回N个车队用户
                    # TODO: 针对lolm、wuhu、avalon和CE先暂时写死队形, 后续使用 queue_symbol 提供的模板来编排队形
                    queue_symbol = room_list[i]["queue_symbol"]
                    coord_x_len = len(queue_symbol.split(";"))
                    coord_y_len = len(queue_symbol.split(";")[0].split(","))
                    in_game_queue_list = [[None for _ in range(coord_y_len)] for _ in range(coord_x_len)]
                    in_game_queue_user_list, ok = await self.list_game_room_in_game_queue_users(room_id=room_id)
                    if ok:
                        if room_id == "room_000509":  # 受托管的房间
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[1][0] = ai_slaves[0]
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room_list[i]["game_index"] == "lolm":
                            in_game_queue_list[0][0] = ai_master
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room_list[i]["game_index"] == "wuhu":
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[0][1] = ai_slaves[0]
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room_list[i]["game_index"] == "avalon":
                            in_game_queue_list[0][0] = ai_master
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                    else:
                        if room_id == "room_000509":  # 受托管的房间
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[1][0] = ai_slaves[0]
                        elif room_list[i]["game_index"] == "lolm":
                            in_game_queue_list[0][0] = ai_master
                        elif room_list[i]["game_index"] == "wuhu":
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[0][1] = ai_slaves[0]
                        elif room_list[i]["game_index"] == "avalon":
                            in_game_queue_list[0][0] = ai_master
                    room_list[i]["in_game_queue_users"] = in_game_queue_list
                
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to list rooms for game:{game_index}.")
            else:
                await perror(f"Failed to list rooms for game:{game_index}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to list rooms for game:{game_index}, err:{exc}.")
        finally:
            return (room_list, done)

    async def query_game_room(self, room_id: str, use_fast_path: bool = False) -> Tuple[Optional[Dict[str, Any]], bool]:
        room = None
        done = False
        try:
            query = {"id": room_id}
            doc = await self._installed_game_room_store.find_one(query)
            if doc is not None:
                if use_fast_path:
                    room = {
                        "id": doc["id"],
                        "game_index": doc["game_index"],
                        "carrying_capacity": doc["carrying_capacity"],
                        "queue_symbol": doc["queue_symbol"],
                        "ai_player_cnt": doc["ai_player_cnt"],
                        "online_user_cnt": doc["online_user_cnt"],
                        "in_game_queue_user_cnt": doc["in_game_queue_user_cnt"],
                        "in_game_queue_be_ready_user_cnt": doc["in_game_queue_be_ready_user_cnt"],
                        "in_game_battle_user_cnt": doc["in_game_battle_user_cnt"],
                        "owner_id": doc["owner_id"],
                        "owner_nickname": doc["owner_nickname"],
                        "owner_avatar": doc["owner_avatar"],
                        "be_hosting": doc["be_hosting"],
                    }
                else:
                    room = {
                        "id": doc["id"],
                        "game_index": doc["game_index"],
                        "rule_title": doc["rule_title"],
                        "rule_content": doc["rule_content"],
                        "title": doc["title"],
                        "cover": doc["cover"],
                        "tags": doc["tags"],
                        "announcement": doc["announcement"],
                        "carrying_capacity": doc["carrying_capacity"],
                        "queue_symbol": doc["queue_symbol"],
                        "ai_player_cnt": doc["ai_player_cnt"],
                        "online_user_cnt": doc["online_user_cnt"],
                        "in_game_queue_user_cnt": doc["in_game_queue_user_cnt"],
                        "in_game_queue_be_ready_user_cnt": doc["in_game_queue_be_ready_user_cnt"],
                        "in_game_battle_user_cnt": doc["in_game_battle_user_cnt"],
                        "owner_id": doc["owner_id"],
                        "owner_nickname": doc["owner_nickname"],
                        "owner_avatar": doc["owner_avatar"],
                        "be_hosting": doc["be_hosting"],
                    }
                    if "assistants" in doc:
                        room["assistants"] = doc["assistants"]
                if not use_fast_path:
                    ai_master = {
                        "user_id": room["owner_id"],
                        "user_nickname": room["owner_nickname"],
                        "user_avatar": room["owner_avatar"],
                        "is_ai": True,
                    }
                    if "assistants" in room:
                        ai_slaves = [
                            {
                                "user_id": assistant["assistant_id"],
                                "user_nickname": assistant["assistant_nickname"],
                                "user_avatar": assistant["assistant_avatar"],
                                "is_ai": True,
                            } for assistant in room["assistants"]
                        ]
                    else:
                        ai_slaves = []
                    # 返回N个在线用户
                    online_user_list, ok = await self.list_game_room_online_users(room_id=room_id)
                    if ok:
                        online_user_list = [ai_master] + ai_slaves + online_user_list
                    else:
                        online_user_list = [ai_master] + ai_slaves
                    room["online_users"] = online_user_list
                    # 返回N个车队用户
                    # TODO: 针对lolm、wuhu、avalon和CE先暂时写死队形, 后续使用 queue_symbol 提供的模板来编排队形
                    queue_symbol = room["queue_symbol"]
                    coord_x_len = len(queue_symbol.split(";"))
                    coord_y_len = len(queue_symbol.split(";")[0].split(","))
                    in_game_queue_list = [[None for _ in range(coord_y_len)] for _ in range(coord_x_len)]
                    in_game_queue_user_list, ok = await self.list_game_room_in_game_queue_users(room_id=room_id)
                    if ok:
                        if room_id == "room_000509":  # 受托管的房间
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[1][0] = ai_slaves[0]
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room["game_index"] == "lolm":
                            in_game_queue_list[0][0] = ai_master
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room["game_index"] == "wuhu":
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[0][1] = ai_slaves[0]
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                        elif room["game_index"] == "avalon":
                            in_game_queue_list[0][0] = ai_master
                            for u in in_game_queue_user_list:
                                if isinstance(u["at_game_queue_x_coord"], int) and isinstance(u["at_game_queue_y_coord"], int):
                                    in_game_queue_list[u["at_game_queue_x_coord"]][u["at_game_queue_y_coord"]] = u
                    else:
                        if room_id == "room_000509":  # 受托管的房间
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[1][0] = ai_slaves[0]
                        elif room["game_index"] == "lolm":
                            in_game_queue_list[0][0] = ai_master
                        elif room["game_index"] == "wuhu":
                            in_game_queue_list[0][0] = ai_master
                            in_game_queue_list[0][1] = ai_slaves[0]
                        elif room["game_index"] == "avalon":
                            in_game_queue_list[0][0] = ai_master
                    room["in_game_queue_users"] = in_game_queue_list
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query game room:{room_id}.")
            else:
                await perror(f"Failed to query game room:{room_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query game room:{room_id}, err:{exc}.")
        finally:
            return (room, done)

    async def upsert_game_room_online_users(self, room_user: Dict[str, Any]) -> bool:
        done = False

        while 1:
            should_retry = False
            try:
                async with self._db_session.start_transaction(read_preference=pymongo.ReadPreference.PRIMARY):
                    try:
                        # NOTE: 由于游戏房间在线用户的更新频率非常高, 为了避免频繁的IO操作, 这里使用了事务.
                        # 事务为什么能避免频繁的IO操作? 因为事务内的操作会被缓存, 只有事务提交时才会真正执行.
                        query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                        doc = await self._game_room_online_users_store.find_one(query, session=self._db_session)
                        if (doc is not None) and (doc["online"] == room_user["online"]):
                            # 已经更新过某种状态, 不要重复更新
                            pass
                        elif (doc is None) and (not room_user["online"]):
                            # 从未进入过该房间, 却执行退出房间的操作直接忽略
                            pass
                        else:
                            update_ts = int(time.time())
                            update = {"$set": {
                                "room_id": room_user["room_id"],
                                "user_id": room_user["user_id"],
                                "user_nickname": room_user["user_nickname"],
                                "user_avatar": room_user["user_avatar"],
                                "online": room_user["online"],
                                "update_ts": update_ts,
                            }}
                            await self._game_room_online_users_store.update_one(query, update, upsert=True, session=self._db_session)
                            
                            incr = 0
                            if room_user["online"]:
                                incr = 1
                            else:
                                incr = -1
                            query = {"id": room_user["room_id"]}
                            update_ts = int(time.time())
                            update = {
                                "$set": {"update_ts": update_ts},
                                "$inc": {"online_user_cnt": incr},
                            }
                            await self._installed_game_room_store.update_one(query, update, upsert=True, session=self._db_session)

                        done = True
                    except perrors.PyMongoError as exc:
                        if exc.timeout:
                            await perror(f"Timeout to upsert game room:{room_user['room_id']} online users.")
                        else:
                            await perror(f"Failed to upsert game room:{room_user['room_id']} online users, err:{exc}.")
                    except Exception as exc:
                        await perror(f"Failed to upsert game room:{room_user['room_id']} online users, err:{exc}.")
                    finally:
                        break
            except perrors.PyMongoError as exc:
                if "Transaction already in progress" in str(exc):
                    await asyncio.sleep(0.1)
                    should_retry = True
                    loguru_logger.warning("One transaction already in progress, retrying...")
            finally:
                if not should_retry:
                    break
        
        return done

    async def list_game_room_online_users(self, room_id: str, offset: int = 0, limit: int = 100) -> Tuple[List[Dict[str, Any]], bool]:
        online_user_list: List[Dict[str, Any]] = []
        done = False
        try:
            query = {"room_id": room_id, "online": True}
            sort_rules = [
                # 优先返回进房时间早的用户
                ("update_ts", pymongo.ASCENDING),
            ]
            async for x in self._game_room_online_users_store.find(query).sort(sort_rules).skip(offset).limit(limit):
                online_user_list.append(
                    {
                        "room_id": x["room_id"],
                        "user_id": x["user_id"],
                        "user_nickname": x["user_nickname"],
                        "user_avatar": x["user_avatar"],
                        "is_ai": False,
                    }
                )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to list online users of room:{room_id}.")
            else:
                await perror(f"Failed to list online users of room:{room_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to list online users of room:{room_id}, err:{exc}.")
        finally:
            return (online_user_list, done)

    async def upsert_game_room_in_game_queue_users(self, room_user: Dict[str, Any], force_exit: bool = False) -> Tuple[bool, bool, bool, bool, bool, int, bool]:
        # 用于标识操作是否被允许
        can = False
        # 用于标识坑位是否已被占
        occupied = False
        # 用于标识车队是否已满
        full = False
        # 用于标识操作是否需要被忽略
        filtered = False
        # 用于标识操作是否被冻结
        frozen = False
        # 用于标识操作还须被冻结的时长
        frozen_time_left = 0
        # 用于标识数据库操作是否成功
        done = False

        while 1:
            should_retry = False
            try:
                async with self._db_session.start_transaction(read_preference=pymongo.ReadPreference.PRIMARY):
                    try:
                        query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                        doc1 = await self._game_room_in_game_queue_users_store.find_one(query, session=self._db_session)
                        doc2 = await self._game_room_in_game_battle_users_store.find_one(query, session=self._db_session)
                        if (doc1 is not None) and (doc1["in_game_queue"] == room_user["in_game_queue"]):
                            # 已经更新过该种状态, 不要重复更新
                            filtered = True
                            frozen = False
                            can = False
                        elif (doc1 is None) and (not room_user["in_game_queue"]):
                            # 从未上过该房间的车队, 却执行离开车队的操作直接忽略
                            filtered = True
                            frozen = False
                            can = False
                        elif (doc1 is not None) and (not room_user["in_game_queue"]) and (doc2 is not None) and (doc2["in_game_battle"]):
                            # 游戏中状态不可离开队伍坑位
                            filtered = True
                            frozen = False
                            can = False
                        elif (doc1 is not None) and (room_user["in_game_queue"]) and (doc1["frozen_time"] > 0 and (doc1["frozen_time"] > int(time.time()))):
                            # 被动踢出队伍的用户, 5分钟内无法再次进入队伍
                            filtered = False
                            frozen = True
                            frozen_time_left = doc1["frozen_time"] - int(time.time())
                            can = False
                        else:
                            filtered = False
                            frozen = False

                            query = {"id": room_user["room_id"]}
                            doc = await self._installed_game_room_store.find_one(query, session=self._db_session)
                            if room_user["in_game_queue"]:
                                # 上车前先检查坑位是否已满
                                if doc["in_game_queue_user_cnt"] < doc["carrying_capacity"]:
                                    can = True
                                    full = (doc["carrying_capacity"] - doc["in_game_queue_user_cnt"]) == 1
                                else:
                                    can = False
                                    full = True
                            else:
                                can = True
                                full = False
                            
                            if room_user["in_game_queue"]:
                                # 上车前先检查坑位是否已被占
                                in_game_queue_users, _ = await self.list_game_room_in_game_queue_users(room_id=room_user["room_id"], offset=0, limit=10)
                                for u in in_game_queue_users:
                                    if u["at_game_queue_x_coord"] == room_user["at_game_queue_x_coord"] and u["at_game_queue_y_coord"] == room_user["at_game_queue_y_coord"]:
                                        can = False
                                        occupied = True
                                        break

                            if can:
                                query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                                update_ts = int(time.time())
                                update = None
                                if room_user["in_game_queue"]:
                                    update = {"$set": {
                                        "room_id": room_user["room_id"],
                                        "user_id": room_user["user_id"],
                                        "user_nickname": room_user["user_nickname"],
                                        "user_avatar": room_user["user_avatar"],
                                        "in_game_queue": True,
                                        "at_game_queue_x_coord": room_user["at_game_queue_x_coord"],
                                        "at_game_queue_y_coord": room_user["at_game_queue_y_coord"],
                                        "frozen_time": 0,
                                        "update_ts": update_ts,
                                    }}
                                else:
                                    if force_exit:
                                        update = {"$set": {
                                            "room_id": room_user["room_id"],
                                            "user_id": room_user["user_id"],
                                            "user_nickname": room_user["user_nickname"],
                                            "user_avatar": room_user["user_avatar"],
                                            "in_game_queue": False,
                                            "frozen_time": update_ts + 300,
                                            "update_ts": update_ts,
                                        }}
                                    else:
                                        update = {"$set": {
                                            "room_id": room_user["room_id"],
                                            "user_id": room_user["user_id"],
                                            "user_nickname": room_user["user_nickname"],
                                            "user_avatar": room_user["user_avatar"],
                                            "in_game_queue": False,
                                            "frozen_time": 0,
                                            "update_ts": update_ts,
                                        }}
                                
                                await self._game_room_in_game_queue_users_store.update_one(query, update, upsert=True, session=self._db_session)
                                
                                incr = 0
                                if room_user["in_game_queue"]:
                                    incr = 1
                                else:
                                    incr = -1
                                query = {"id": room_user["room_id"]}
                                update_ts = int(time.time())
                                update = {
                                    "$set": {"update_ts": update_ts},
                                    "$inc": {"in_game_queue_user_cnt": incr},
                                }
                                await self._installed_game_room_store.update_one(query, update, upsert=True, session=self._db_session)
                        
                        done = True
                    except perrors.PyMongoError as exc:
                        if exc.timeout:
                            await perror(f"Timeout to upsert game room:{room_user['room_id']} in-game-queue users.")
                        else:
                            await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-queue users, err:{exc}.")
                    except Exception as exc:
                        await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-queue users, err:{exc}.")
                    finally:
                        break
            except perrors.PyMongoError as exc:
                if "Transaction already in progress" in str(exc):
                    await asyncio.sleep(0.1)
                    should_retry = True
                    loguru_logger.warning("One transaction already in progress, retrying...")
            finally:
                if not should_retry:
                    break

        return (can, occupied, full, filtered, frozen, frozen_time_left, done)

    async def upsert_game_room_in_game_queue_be_ready_users(self, room_user: Dict[str, Any]) -> Tuple[bool, bool, bool]:
        can = False
        all_ready = False
        done = False

        while 1:
            should_retry = False
            try:
                async with self._db_session.start_transaction(read_preference=pymongo.ReadPreference.PRIMARY):
                    try:
                        query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                        doc1 = await self._game_room_in_game_queue_be_ready_users_store.find_one(query, session=self._db_session)
                        doc2 = await self._game_room_in_game_battle_users_store.find_one(query, session=self._db_session)
                        if (doc1 is not None) and (doc1["in_game_queue_be_ready"] == room_user["in_game_queue_be_ready"]):
                            # 已经更新过某种状态, 不要重复更新
                            can = False
                        elif (doc1 is None) and (not room_user["in_game_queue_be_ready"]):
                            # 从未在该房间的车队内就绪, 却执行在车队内不就绪的操作直接忽略
                            can = False
                        elif (doc1 is not None) and (not room_user["in_game_queue_be_ready"]) and (doc2 is not None) and (doc2["in_game_battle"]):
                            # 游戏中状态不可解除准备状态
                            can = False
                        else:
                            query = {"id": room_user["room_id"]}
                            doc = await self._installed_game_room_store.find_one(query)
                            if room_user["in_game_queue_be_ready"]:
                                all_ready = (doc["carrying_capacity"] - doc["in_game_queue_be_ready_user_cnt"]) == 1
                            else:
                                all_ready = False

                            query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                            update_ts = int(time.time())
                            update = {"$set": {
                                "room_id": room_user["room_id"],
                                "user_id": room_user["user_id"],
                                "user_nickname": room_user["user_nickname"],
                                "user_avatar": room_user["user_avatar"],
                                "in_game_queue_be_ready": room_user["in_game_queue_be_ready"],
                                "update_ts": update_ts,
                            }}
                            await self._game_room_in_game_queue_be_ready_users_store.update_one(query, update, upsert=True, session=self._db_session)
                            
                            incr = 0
                            if room_user["in_game_queue_be_ready"]:
                                incr = 1
                            else:
                                incr = -1
                            query = {"id": room_user["room_id"]}
                            update_ts = int(time.time())
                            update = {
                                "$set": {"update_ts": update_ts},
                                "$inc": {"in_game_queue_be_ready_user_cnt": incr},
                            }
                            await self._installed_game_room_store.update_one(query, update, upsert=True, session=self._db_session)

                            can = True
                        
                        done = True
                    except perrors.PyMongoError as exc:
                        if exc.timeout:
                            await perror(f"Timeout to upsert game room:{room_user['room_id']} in-game-queue-be-ready users.")
                        else:
                            await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-queue-be-ready users, err:{exc}.")
                    except Exception as exc:
                        await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-queue-be-ready users, err:{exc}.")
                    finally:
                        break
            except perrors.PyMongoError as exc:
                if "Transaction already in progress" in str(exc):
                    await asyncio.sleep(0.1)
                    should_retry = True
                    loguru_logger.warning("One transaction already in progress, retrying...")
            finally:
                if not should_retry:
                    break

        return (can, all_ready, done)

    async def list_game_room_in_game_queue_users(self, room_id: str, offset: int = 0, limit: int = 10) -> Tuple[List[Dict[str, Any]], bool]:
        in_game_queue_user_list: List[Dict[str, Any]] = []
        done = False
        try:
            query = {"room_id": room_id, "in_game_queue": True}
            sort_rules = [
                # 优先返回上车时间早的用户
                ("update_ts", pymongo.ASCENDING),
            ]
            async for x in self._game_room_in_game_queue_users_store.find(query).sort(sort_rules).skip(offset).limit(limit):
                inner_query = {"room_id": room_id, "user_id": x["user_id"], "in_game_queue_be_ready": True}
                doc = await self._game_room_in_game_queue_be_ready_users_store.find_one(inner_query)
                in_game_queue_user_list.append(
                    {
                        "room_id": x["room_id"],
                        "user_id": x["user_id"],
                        "user_nickname": x["user_nickname"],
                        "user_avatar": x["user_avatar"],
                        "at_game_queue_x_coord": x["at_game_queue_x_coord"],
                        "at_game_queue_y_coord": x["at_game_queue_y_coord"],
                        "is_ai": False,
                        "is_be_ready": doc is not None,
                    }
                )
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to list in-game-queue users of room:{room_id}.")
            else:
                await perror(f"Failed to list in-game-queue users of room:{room_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to list in-game-queue users of room:{room_id}, err:{exc}.")
        finally:
            return (in_game_queue_user_list, done)

    async def upsert_game_room_in_game_battle_users(self, room_user: Dict[str, Any]) -> Tuple[bool, bool]:
        all_in_game_battle = False
        done = False
        
        while 1:
            should_retry = False
            try:
                async with self._db_session.start_transaction(read_preference=pymongo.ReadPreference.PRIMARY):
                    try:
                        query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                        doc = await self._game_room_in_game_battle_users_store.find_one(query, session=self._db_session)
                        if (doc is not None) and (doc["in_game_battle"] == room_user["in_game_battle"]):
                            # 已经更新过某种状态, 不要重复更新
                            pass
                        elif (doc is None) and (not room_user["in_game_battle"]):
                            # 从未在该房间内进入第三方游戏, 却执行结束游戏的操作直接忽略
                            pass
                        else:
                            query = {"id": room_user["room_id"]}
                            doc = await self._installed_game_room_store.find_one(query)
                            if room_user["in_game_battle"]:
                                all_in_game_battle = (doc["carrying_capacity"] - doc["in_game_battle_user_cnt"]) == 1
                            else:
                                all_in_game_battle = False

                            query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                            update_ts = int(time.time())
                            update = {"$set": {
                                "room_id": room_user["room_id"],
                                "user_id": room_user["user_id"],
                                "user_nickname": room_user["user_nickname"],
                                "user_avatar": room_user["user_avatar"],
                                "in_game_battle": room_user["in_game_battle"],
                                "update_ts": update_ts,
                            }}
                            await self._game_room_in_game_battle_users_store.update_one(query, update, upsert=True, session=self._db_session)
                            
                            incr = 0
                            if room_user["in_game_battle"]:
                                incr = 1
                            else:
                                incr = -1
                            query = {"id": room_user["room_id"]}
                            update_ts = int(time.time())
                            update = {
                                "$set": {"update_ts": update_ts},
                                "$inc": {"in_game_battle_user_cnt": incr},
                            }
                            await self._installed_game_room_store.update_one(query, update, upsert=True, session=self._db_session)

                        done = True
                    except perrors.PyMongoError as exc:
                        if exc.timeout:
                            await perror(f"Timeout to upsert game room:{room_user['room_id']} in-game-battle users.")
                        else:
                            await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-battle users, err:{exc}.")
                    except Exception as exc:
                        await perror(f"Failed to upsert game room:{room_user['room_id']} in-game-battle users, err:{exc}.")
                    finally:
                        break
            except perrors.PyMongoError as exc:
                if "Transaction already in progress" in str(exc):
                    await asyncio.sleep(0.1)
                    should_retry = True
                    loguru_logger.warning("One transaction already in progress, retrying...")
            finally:
                if not should_retry:
                    break

        return (all_in_game_battle, done)

    async def query_game_room_in_game_queue_be_ready_user(self, room_id: str, uid: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        in_game_queue_user = None
        done = False
        try:
            query = {"room_id": room_id, "user_id": uid, "in_game_queue_be_ready": True}
            doc = await self._game_room_in_game_queue_be_ready_users_store.find_one(query)
            in_game_queue_user = doc
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query in-game-queue user:{uid} of room:{room_id}.")
            else:
                await perror(f"Failed to query in-game-queue user:{uid} of room:{room_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query in-game-queue user:{uid} of room:{room_id}, err:{exc}.")
        finally:
            return (in_game_queue_user, done)

    async def check_user_in_game_room_and_in_game_battle(self, uid: str, open_explain: bool = False) -> Tuple[Optional[str], bool]:
        room_id = None
        done = False
        try:
            query = {"user_id": uid, "in_game_battle": True}
            doc = await self._game_room_in_game_battle_users_store.find_one(query)
            if doc is not None:
                room_id = doc["room_id"]
            if open_explain:
                # NOTE: 查询计划是为了查看索引使用情况.
                explain = pymongoexplain.ExplainableCollection(
                    self._game_room_in_game_battle_users_store,
                    verbosity="queryPlanner",
                )
                explain_result = await explain.find_one(query)
                del explain_result["$clusterTime"]
                del explain_result["operationTime"]
                del explain_result["serverInfo"]
                del explain_result["serverParameters"]
                loguru_logger.debug("explain_result:")

                loguru_logger.debug(f"\n{json.dumps(explain_result, indent=4, sort_keys=True)}")
            done = True
        except perrors.PyMongoError as exc:
            if exc.timeout:
                await perror(f"Timeout to query in-game-battle user:{uid} of room:{room_id}.")
            else:
                await perror(f"Failed to query in-game-battle user:{uid} of room:{room_id}, err:{exc}.")
        except Exception as exc:
            await perror(f"Failed to query in-game-battle user:{uid} of room:{room_id}, err:{exc}.")
        finally:
            return (room_id, done)

    async def upsert_game_room_users(self, room_user: Dict[str, Any]) -> bool:
        done = False

        while 1:
            should_retry = False
            try:
                async with self._db_session.start_transaction(read_preference=pymongo.ReadPreference.PRIMARY):
                    try:
                        update_ts = int(time.time())

                        query = {"room_id": room_user["room_id"], "user_id": room_user["user_id"]}
                        update = {"$set": {
                            "room_id": room_user["room_id"],
                            "user_id": room_user["user_id"],
                            "user_nickname": room_user["user_nickname"],
                            "user_avatar": room_user["user_avatar"],
                            "online": False,
                            "update_ts": update_ts,
                        }}
                        await self._game_room_online_users_store.update_one(query, update, upsert=True, session=self._db_session)
                        update = {"$set": {
                            "room_id": room_user["room_id"],
                            "user_id": room_user["user_id"],
                            "user_nickname": room_user["user_nickname"],
                            "user_avatar": room_user["user_avatar"],
                            "in_game_queue": False,
                            "frozen_time": 0,
                            "update_ts": update_ts,
                        }}
                        await self._game_room_in_game_queue_users_store.update_one(query, update, upsert=True, session=self._db_session)
                        update = {"$set": {
                            "room_id": room_user["room_id"],
                            "user_id": room_user["user_id"],
                            "user_nickname": room_user["user_nickname"],
                            "user_avatar": room_user["user_avatar"],
                            "in_game_queue_be_ready": False,
                            "update_ts": update_ts,
                        }}
                        await self._game_room_in_game_queue_be_ready_users_store.update_one(query, update, upsert=True, session=self._db_session)

                        query = {"id": room_user["room_id"]}
                        update = {
                            "$set": {"update_ts": update_ts},
                            "$inc": {
                                "online_user_cnt": -1,
                                "in_game_queue_user_cnt": -1,
                                "in_game_queue_be_ready_user_cnt": -1
                            },
                        }
                        await self._installed_game_room_store.update_one(query, update, upsert=True, session=self._db_session)

                        done = True
                    except perrors.PyMongoError as exc:
                        if exc.timeout:
                            await perror(f"Timeout to upsert game room:{room_user['room_id']} users.")
                        else:
                            await perror(f"Failed to upsert game room:{room_user['room_id']} users, err:{exc}.")
                    except Exception as exc:
                        await perror(f"Failed to upsert game room:{room_user['room_id']} users, err:{exc}.")
                    finally:
                        break
            except perrors.PyMongoError as exc:
                if "Transaction already in progress" in str(exc):
                    await asyncio.sleep(0.1)
                    should_retry = True
                    loguru_logger.warning("One transaction already in progress, retrying...")
            finally:
                if not should_retry:
                    break
        
        return done

    async def close(self):
        await self._db_session.end_session()
        self._client.close()


_instance: MongoClient = None


def init_instance(client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
    global _instance
    _instance = MongoClient(client_conf, io_loop)


def instance() -> MongoClient:
    return _instance
