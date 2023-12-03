# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import os
import sys
sys.path.append(os.path.join(os.path.abspath(os.curdir), "internal", "proto_gens"))

import asyncio
# More info: https://github.com/aio-libs/aiohttp/discussions/6044.
setattr(asyncio.sslproto._SSLProtocolTransport, "_start_tls_compatible", True)
import collections
import random
import time
import ujson as json

from dependencies import settings
from fastapi import FastAPI, \
    Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from internal.extensions.ext_kafka.producer import init_instance as init_kafka_producer_instance
from internal.extensions.ext_kafka.producer import instance as kafka_producer_instance
from internal.extensions.ext_mongo.ha import init_instance as init_db_instance
from internal.extensions.ext_mongo.ha import instance as db_instance
from internal.extensions.ext_redis import init_instance as init_cache_instance
from internal.extensions.ext_redis import instance as cache_instance
from internal.extensions.ext_redis.keys import CKEY_TOTAL_USER_CNT_KEY, \
    CKEY_USER_DEVICE_ID_EXT
from internal.infra.alarm import init_alarm_vars, \
    clear_alarm_vars, \
    request_oss_access_token, \
    send_alarm, \
    perror
from internal.infra.http_session import init_session_mgr, \
    deinit_session_mgr
from internal.infra.jpush import init_jpush_vars, \
    clear_jpush_vars
from internal.infra.jwt import verify_access_token, \
    SYS_ACCOUNT, \
    SYS_DEVICE_ID
from internal.infra.qrcode import init_qr_instance
from internal.infra.redlock import init_instance as init_redlock_instance
from internal.infra.redlock import instance as redlock_instance
from internal.infra.sms import init_sms_vars, \
    clear_sms_vars
from internal.rpc_client import setup_oss_client, \
    close_oss_client
from internal.rpc_client import setup_cas_client, \
    close_cas_client
from internal.rpc_client import setup_uss_client, \
    close_uss_client
from internal.logger.loguru_logger import init_global_logger
from loguru import logger as loguru_logger
from routers import h_activate
from routers import h_app_permissions
from routers import h_chat
from routers import h_config
from routers import h_feedback
from routers import h_game_ai
from routers import h_game_result
from routers import h_game
from routers import h_logon
from routers import h_personal_settings
from routers import h_product_operation_rules
from routers import h_profile
from routers import h_room
from routers import h_sms
from routers import h_storage
from routers import h_task
from routers import h_url
from routers.h_config import load_business_conf, \
    get_business_conf
from routers.model import Response
from starlette.middleware.base import RequestResponseEndpoint
from typing import Dict


app = FastAPI(
    title="Game Companion Platform Api Gateway Service",
    description="AI玩伴 - API网关服务",
    version="1.0.0",
    debug=False
)
app.include_router(h_activate.router)
app.include_router(h_app_permissions.router)
app.include_router(h_chat.router)
app.include_router(h_config.router)
app.include_router(h_feedback.router)
app.include_router(h_game_ai.router)
app.include_router(h_game_result.router)
app.include_router(h_game.router)
app.include_router(h_logon.router)
app.include_router(h_personal_settings.router)
app.include_router(h_product_operation_rules.router)
app.include_router(h_profile.router)
app.include_router(h_room.router)
app.include_router(h_sms.router)
app.include_router(h_storage.router)
app.include_router(h_task.router)
app.include_router(h_url.router)
allowed_origins = [
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    # Setup global logger.
    init_global_logger()
    loguru_logger.info("--------------------------------------------------------------------------")
    loguru_logger.info("Starting GameCompanionPlatformApiGatewayService Server...")
    random.seed(int(time.time()))

    # Setup mongodb connection (pool).
    try:
        init_db_instance(
            client_conf={
                "endpoints": settings.MONGODB_SERVER_ENDPOINTS,
                "username": settings.MONGODB_USERNAME,
                "password": settings.MONGODB_PASSWORD,
                "auth_mechanism": settings.MONGODB_AUTH_MECHANISM,
                "database": settings.MONGODB_DATABASE,
                "replica_set": settings.MONGODB_REPLICA_SET,
            }
        )
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    connected = await db_instance().is_connected()
    if connected:
        ok = await db_instance().init_indexes()
        if ok:
            loguru_logger.info("Done db.init_indexes stage.")
        else:
            loguru_logger.error("Failed db.init_indexes stage.")
            sys.exit(-1)

        ok = await db_instance().init()
        if ok:
            loguru_logger.info("Done db.init stage.")
        else:
            loguru_logger.error("Failed db.init stage.")
            sys.exit(-1)
        
        loguru_logger.info("Setup mongodb connection (pool).")
    else:
        loguru_logger.error("Cannot setup mongodb connection (pool).")
        sys.exit(-1)
    # Setup redis connection (pool).
    try:
        init_cache_instance(
            client_conf={
                "endpoint": settings.REDIS_SERVER_ENDPOINT,
                "password": settings.REDIS_PASSWORD,
                "db": settings.REDIS_DB,
            }
        )
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    connected = await cache_instance().is_connected()
    if connected:
        loguru_logger.info("Setup redis connection (pool).")
    else:
        loguru_logger.error("Cannot setup redis connection (pool).")
        sys.exit(-1)
    init_redlock_instance(connections=[cache_instance().get_connection()])
    ok, dlock = await redlock_instance().alock(resource="test_redlock_key", ttl=50)
    if not ok:
        loguru_logger.error("Cannot acquire redlock.")
        sys.exit(-1)
    ok = await redlock_instance().aunlock(lock=dlock)
    if not ok:
        loguru_logger.error("Cannot release redlock.")
        sys.exit(-1)
    loguru_logger.info("Redlock is ready.")
    # Setup kafka producer.
    try:
        init_kafka_producer_instance(
            conf={
                "brokers": settings.KAFKA_BROKERS,
                "client_id": settings.KAFKA_PRODUCER_CLIENT_ID,
                "default_topic": settings.KAFKA_PRODUCER_TOPIC,
                "default_room_event_topic": settings.KAFKA_PRODUCER_ROOM_EVENT_TOPIC,
            }
        )
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    connected = await kafka_producer_instance().is_connected()
    if connected:
        loguru_logger.info("Setup kafka producer.")
    else:
        loguru_logger.error("Cannot setup kafka producer.")
        sys.exit(-1)
    # Setup oss grpc client connection (pool).
    try:
        setup_oss_client(endpoint=settings.OSS_GRPC_ENDPOINT)
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    loguru_logger.info("Setup oss grpc client connection (pool).")
    # Setup tfs grpc client connection (pool).
    try:
        setup_cas_client(endpoint=settings.CAS_GRPC_ENDPOINT)
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    loguru_logger.info("Setup tfs grpc client connection (pool).")
    # Setup uss grpc client connection (pool).
    try:
        setup_uss_client(endpoint=settings.USS_GRPC_ENDPOINT)
    except Exception as e:
        loguru_logger.error(f"Failed to start GameCompanionPlatformApiGatewayService Server, err{e}.")
        sys.exit(-1)
    loguru_logger.info("Setup uss grpc client connection (pool).")
    # Setup global http connection (pool).
    await init_session_mgr()
    loguru_logger.info("Setup global http connection (pool).")
    # Setup http connection (pool) for sms.
    await init_sms_vars()
    loguru_logger.info("Setup http connection (pool) for sms.")
    # Setup http connection (pool) for jpush.
    await init_jpush_vars()
    loguru_logger.info("Setup http connection (pool) for jpush.")
    # Setup http connection (pool) for alarm service.
    await init_alarm_vars()
    loguru_logger.info("Setup http connection (pool) for alarm service.")
    # Setup oss access token.
    ok = await request_oss_access_token()
    if ok:
        loguru_logger.info("Setup oss access token.")
    else:
        loguru_logger.error("Cannot setup oss access token.")
        sys.exit(-1)
    # Load business conf.
    ok = load_business_conf()
    if ok:
        loguru_logger.info("Load business conf.")
    else:
        loguru_logger.error("Cannot load business conf.")
        sys.exit(-1)
    # Setup qrcode.
    init_qr_instance()
    
    if not settings.SKIP_APP_VERSION_CHECK:
        loguru_logger.info(f"开启APP版本检测, app_version:{settings.APP_VERSION}.")
    else:
        loguru_logger.info("关闭APP版本检测.")

    # Init database.
    ok = await init_db()
    if not ok:
        sys.exit(-1)
    # Init cache.
    ok = await init_cache()
    if not ok:
        sys.exit(-1)

    await send_alarm(msg="Started GameCompanionPlatformApiGatewayService Server 🤘.", level="INFO")
    loguru_logger.info("Started GameCompanionPlatformApiGatewayService Server 🤘.")


async def init_db():
    business_conf = get_business_conf()

    # 初始化游戏信息库
    loguru_logger.debug("Try to write game_list data into database.")
    game_list_data = business_conf["game_list"]
    for game in game_list_data:
        ok = await db_instance().upsert_game_info(game={
            "index": game["index"],
            "en_name": game["en_name"],
            "zh_name": game["zh_name"],
            "logo": game["logo"],
            "slogan": game["slogan"],
            "tags": game["tags"],
            "min_online_user_cnt": game["min_online_user_cnt"],
            "max_online_user_cnt": game["max_online_user_cnt"],
            "extra": json.dumps(game["extra"]) if "extra" in game else "",
        })
        if not ok:
            loguru_logger.error("Failed to write game_list data into database.")
            return False
    loguru_logger.debug("Writed game_list data into database.")

    # 初始化AI角色信息库
    loguru_logger.debug("Try to write ai_player_list data into database.")
    ai_player_list_data = business_conf["ai_player_list"]
    room_owner_candidates = collections.defaultdict(list)
    be_hosting_room_ai_players = collections.defaultdict(list)
    for ai_player in ai_player_list_data:
        tags = [ai_player["game_index"], str(ai_player["age"])] + \
            ai_player["character_tags"] + \
            [ai_player["occupation"]] + \
            ai_player["hobby_tags"] + \
            ai_player["game_tags"]
        ok = await db_instance().upsert_ai_player_info(ai_player={
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
            "tags": tags,
            "extra": json.dumps(ai_player["extra"]) if "extra" in ai_player else "",
        })
        if not ok:
            loguru_logger.error("Failed to write ai_player_list data into database.")
            return False
        if not ai_player["be_hosting"] and ai_player["installed"]:
            room_owner_candidates[ai_player["game_index"]].append({
                "id": ai_player["id"],
                "room_id": ai_player["room_id"],
                "is_master": ai_player["is_master"],
                "slave_number": ai_player["slave_number"],
                "nickname": ai_player["nickname"],
                "gendor": ai_player["gendor"],
                "avatar": ai_player["avatar"],
            })
        elif ai_player["be_hosting"] and ai_player["installed"]:
            be_hosting_room_ai_players[ai_player["game_index"]].append({
                "id": ai_player["id"],
                "room_id": ai_player["room_id"],
                "be_hosting_room_id": ai_player["be_hosting_room_id"],
                "is_master": ai_player["is_master"],
                "slave_number": ai_player["slave_number"],
                "nickname": ai_player["nickname"],
                "gendor": ai_player["gendor"],
                "avatar": ai_player["avatar"],
            })
    loguru_logger.debug("Writed ai_player_list data into database.")

    # 把同一个房间内的AI组合到一起
    new_room_owner_candidates = {}
    for game_index, candidates in room_owner_candidates.items():
        candidates = sorted(candidates, key=lambda x: x["room_id"], reverse=False)

        new_candidates = []
        combined_candidates = []
        prev = candidates[0]
        combined_candidates.append(prev)
        for i in range(1, len(candidates)):
            if candidates[i]["room_id"] == prev["room_id"]:
                combined_candidates.append(candidates[i])
            else:
                prev = candidates[i]
                # 把房主排在最前头
                combined_candidates = sorted(combined_candidates, key=lambda x: x["is_master"], reverse=True)
                new_candidates.append(combined_candidates)
                combined_candidates = []
                combined_candidates.append(candidates[i])
        if len(combined_candidates) > 0:
            # 把房主排在最前头
            combined_candidates = sorted(combined_candidates, key=lambda x: x["is_master"], reverse=True)
            new_candidates.append(combined_candidates)
        new_room_owner_candidates[game_index] = new_candidates
    room_owner_candidates = new_room_owner_candidates
    new_be_hosting_room_ai_players = {}
    for game_index, candidates in be_hosting_room_ai_players.items():
        candidates = sorted(candidates, key=lambda x: x["room_id"], reverse=False)

        new_candidates = []
        combined_candidates = []
        prev = candidates[0]
        combined_candidates.append(prev)
        for i in range(1, len(candidates)):
            if candidates[i]["room_id"] == prev["room_id"]:
                combined_candidates.append(candidates[i])
            else:
                prev = candidates[i]
                # 把房主排在最前头
                combined_candidates = sorted(combined_candidates, key=lambda x: x["is_master"], reverse=True)
                new_candidates.append(combined_candidates)
                combined_candidates = []
                combined_candidates.append(candidates[i])
        if len(combined_candidates) > 0:
            # 把房主排在最前头
            combined_candidates = sorted(combined_candidates, key=lambda x: x["is_master"], reverse=True)
            new_candidates.append(combined_candidates)
        new_be_hosting_room_ai_players[game_index] = new_candidates
    be_hosting_room_ai_players = new_be_hosting_room_ai_players

    # 初始化房间信息库
    loguru_logger.debug("Try to write game_room_list data into database.")
    game_room_list_data = business_conf["game_room_list"]
    available_rooms = collections.defaultdict(list)
    be_hosting_rooms = collections.defaultdict(list)
    for inner_ai_player_list_data in game_room_list_data:
        game_index = inner_ai_player_list_data["game_index"]
        announcement = inner_ai_player_list_data["platform_announcement"]
        rule_title = inner_ai_player_list_data["room_rule_title"]
        rule = inner_ai_player_list_data["room_rule"]
        for room in inner_ai_player_list_data["rooms_information"]:
            room["game_index"] = game_index
            room["rule_title"] = rule_title
            room["rule_content"] = rule
            room["announcement"] = announcement
            
            ok = await db_instance().upsert_game_room_info(room={
                "id": room["id"],
                "game_index": game_index,
                "rule_title": rule_title,
                "rule_content": rule,
                "title": room["title"],
                "tags": room["tags"],
                "announcement": announcement,
                "carrying_capacity": room["carrying_capacity"],
                "queue_symbol": room["queue_symbol"],
                "ai_player_cnt": room["ai_player_cnt"],
                "rank_weight": room["rank_weight"],
                "be_hosting": room["be_hosting"],
            })
            if not ok:
                loguru_logger.error("Failed to write game_room_list data into database.")
                return False
            
            if not room["be_hosting"]:
                available_rooms[game_index].append(room)
            else:
                be_hosting_rooms[game_index].append(room)
    loguru_logger.debug("Writed game_room_list data into database.")

    # 每个AI都开设一个专属的房间
    loguru_logger.debug("Try to write installed_game_room_list data into database.")
    for game_index, combined_candidates in room_owner_candidates.items():
        rooms = available_rooms[game_index]
        random.shuffle(rooms)
        for i in range(len(combined_candidates)):
            for j in range(len(combined_candidates[i])):
                if combined_candidates[i][j]["is_master"]:
                    ok = await db_instance().upsert_installed_game_room_info(room={
                        "id": combined_candidates[i][j]["room_id"],
                        "game_index": rooms[i]["game_index"],
                        "rule_title": rooms[i]["rule_title"],
                        "rule_content": rooms[i]["rule_content"],
                        "title": rooms[i]["title"],
                        "cover": combined_candidates[i][j]["avatar"],
                        "master_id": combined_candidates[i][j]["id"],
                        "master_nickname": combined_candidates[i][j]["nickname"],
                        "master_gendor": combined_candidates[i][j]["gendor"],
                        "master_avatar": combined_candidates[i][j]["avatar"],
                        "tags": rooms[i]["tags"],
                        "announcement": rooms[i]["announcement"],
                        "carrying_capacity": rooms[i]["carrying_capacity"],
                        "queue_symbol": rooms[i]["queue_symbol"],
                        "ai_player_cnt": rooms[i]["ai_player_cnt"],
                        "rank_weight": rooms[i]["rank_weight"],
                        "be_hosting": rooms[i]["be_hosting"],
                    }, is_for_master=True)
                else:
                    ok = await db_instance().upsert_installed_game_room_info(room={
                        "id": combined_candidates[i][j]["room_id"],
                        "slave_id": combined_candidates[i][j]["id"],
                        "slave_nickname": combined_candidates[i][j]["nickname"],
                        "slave_gendor": combined_candidates[i][j]["gendor"],
                        "slave_avatar": combined_candidates[i][j]["avatar"],
                    }, is_for_master=False)
                if not ok:
                    loguru_logger.error("Failed to write installed_game_room_list data into database.")
                    return False
    loguru_logger.debug("Writed installed_game_room_list data into database.")

    # 开设运营托管房间
    loguru_logger.debug("Try to write installed_game_room_list data into database.")
    for game_index, combined_candidates in new_be_hosting_room_ai_players.items():
        rooms = be_hosting_rooms[game_index]
        room = None
        for r in rooms:
            if combined_candidates[0][0]["be_hosting_room_id"] == r["id"]:
                room = r
                break
        if room is None:
            continue

        for i in range(len(combined_candidates)):
            for j in range(len(combined_candidates[i])):
                if combined_candidates[i][j]["is_master"]:
                    ok = await db_instance().upsert_installed_game_room_info(room={
                        "id": combined_candidates[i][j]["room_id"],
                        "game_index": room["game_index"],
                        "rule_title": room["rule_title"],
                        "rule_content": room["rule_content"],
                        "title": room["title"],
                        "cover": combined_candidates[i][j]["avatar"],
                        "master_id": combined_candidates[i][j]["id"],
                        "master_nickname": combined_candidates[i][j]["nickname"],
                        "master_gendor": combined_candidates[i][j]["gendor"],
                        "master_avatar": combined_candidates[i][j]["avatar"],
                        "tags": room["tags"],
                        "announcement": room["announcement"],
                        "carrying_capacity": room["carrying_capacity"],
                        "queue_symbol": room["queue_symbol"],
                        "ai_player_cnt": room["ai_player_cnt"],
                        "rank_weight": room["rank_weight"],
                        "be_hosting": room["be_hosting"],
                    }, is_for_master=True)
                else:
                    ok = await db_instance().upsert_installed_game_room_info(room={
                        "id": combined_candidates[i][j]["room_id"],
                        "slave_id": combined_candidates[i][j]["id"],
                        "slave_nickname": combined_candidates[i][j]["nickname"],
                        "slave_gendor": combined_candidates[i][j]["gendor"],
                        "slave_avatar": combined_candidates[i][j]["avatar"],
                    }, is_for_master=False)
                if not ok:
                    loguru_logger.error("Failed to write installed_game_room_list data into database.")
                    return False
    loguru_logger.debug("Writed installed_game_room_list data into database.")
    
    loguru_logger.info("Inited database data.")
    return True


async def init_cache() -> bool:
    pairs = [
        (CKEY_TOTAL_USER_CNT_KEY.format(env=settings.DEPLOY_ENV), db_instance().user_cnt),
    ]
    ok = await cache_instance().init_cache(pairs)
    if not ok:
        loguru_logger.error("Failed to init cache data.")
        return False
    loguru_logger.info("Inited cache data.")
    return True


@app.on_event("shutdown")
async def shutdown_event():
    loguru_logger.info("Stoping GameCompanionPlatformApiGatewayService Server...")
    # Release mongodb connection (pool).
    await db_instance().close()
    loguru_logger.info("Release mongodb connection (pool).")
    # Release redis connection (pool).
    await cache_instance().close()
    loguru_logger.info("Release redis connection (pool).")
    # Release kafka producer.
    await kafka_producer_instance().close()
    loguru_logger.info("Release kafka producer.")
    # Release oss grpc client.
    close_oss_client()
    loguru_logger.info("Release oss grpc client connection (pool).")
    # Release tfs grpc client.
    close_cas_client()
    loguru_logger.info("Release tfs grpc client connection (pool).")
    # Release uss grpc client.
    close_uss_client()
    loguru_logger.info("Release uss grpc client connection (pool).")
    # Release http connection (pool) for sms.
    await clear_sms_vars()
    loguru_logger.info("Release http connection (pool) for sms.")
    # Release http connection (pool) for jpush.
    await clear_jpush_vars()
    loguru_logger.info("Release http connection (pool) for jpush.")
    # Release http connection (pool) for alarm service.
    await send_alarm(msg="Stopped GameCompanionPlatformApiGatewayService Server 🤘.", level="WARN")
    await clear_alarm_vars()
    loguru_logger.info("Release http connection (pool) for alarm service.")
    # Release global http connection (pool).
    await deinit_session_mgr()
    loguru_logger.info("Release global http connection (pool).")
    loguru_logger.info("Stopped GameCompanionPlatformApiGatewayService Server 🤘.")


@app.head("/")
async def index():
    return Response(code=0, msg="OK")


@app.middleware("http")
async def recover_panic_and_report_latency_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if (request.method == "HEAD" and request.url.path == "/") or \
        (request.method == "GET" and request.url.path == "/favicon.ico") or \
        (request.method == "GET" and request.url.path == "/docs") or \
        (request.method == "GET" and request.url.path == "/openapi.json"):
        response = await call_next(request)
        return response
    else:
        try:
            st = time.time()
            response = await call_next(request)
            ed = time.time()
            loguru_logger.debug(f"{request.method} {request.url.path} - request latency: {ed - st:.3f}s")
            return response
        except Exception as e:
            await perror(f"Recover from internal server panic, err:{e}.")
            return JSONResponse(
                content={"code": 10500, "msg": "服务器内部错误"},
                status_code=200,
            )


def check_app_version_core(method: str, api: str, headers: Dict[str, str]) -> bool:
    # The following paths are always allowed:
    if api == "/" or api[1:] in ["docs", "openapi.json", "favicon.ico"]:
        return True
    if api.split("?")[0] in [
        "/api/v1/game/result",
        "/api/v1/task",
    ]:
        return True
    account = headers.get("x-sec-account", "")
    if account == "ums-admin":
        # NOTE: ums-admin is a special account, it can do anything.
        return True

    if len(headers.get("app-version", "")) == 0 or headers.get("app-version", "") != settings.APP_VERSION:
        return False

    return True


@app.middleware("http")
async def check_app_version_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if not settings.SKIP_APP_VERSION_CHECK:
        if not check_app_version_core(request.method, request.url.path, request.headers):
            return JSONResponse(
                content={"code": 200001, "msg": "【内测】非法请求，请升级APP版本"},
                status_code=200,
            )
    return await call_next(request)


async def check_authentication_core(method: str, api: str, headers: Dict[str, str]) -> bool:
    if api == "/" or api[1:] in ["docs", "openapi.json", "favicon.ico"]:
        return True
    if api.split("?")[0] in [
        "/api/v1/sms",
        "/api/v1/sms/verify",
    ]:
        return True
    
    account, token = headers.get("x-sec-account", ""), headers.get("x-sec-token", "")
    if len(account) == 0 or len(token) == 0:
        return False
    
    if account == SYS_ACCOUNT:
        device_id = SYS_DEVICE_ID
    else:
        device_id, _, _ = await cache_instance().exist_or_get_string(key=CKEY_USER_DEVICE_ID_EXT.format(
            env=settings.DEPLOY_ENV, account=account))
    if device_id is None or (not isinstance(device_id, str)) or len(device_id) == 0:
        return False
    return verify_access_token(account=account, device_id=device_id, access_token=token)


@app.middleware("http")
async def check_authentication_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    flag = await check_authentication_core(request.method, request.url.path, request.headers)
    if not flag:
        return JSONResponse(
            content={"code": 10401, "msg": "Unauthorized"},
            status_code=200,
        )
    return await call_next(request)
