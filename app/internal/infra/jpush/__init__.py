# -*- coding: utf-8 -*-
import base64
import ujson as json

from dependencies import settings
from internal.extensions.ext_redis import instance as cache_instance
from internal.extensions.ext_redis.keys import CKEY_USER_DEVICE_ID, \
    CKEY_APP_PERMISSION_RECORD, \
    CKEY_USER_DEVICE_TYPE, \
    CKEY_USER_JPUSH_REGISTRATION_ID
from internal.infra.http_session import get_aio_session
from loguru import logger as loguru_logger

_HTTP_BASIC_AUTH = None


async def init_jpush_vars():
    global _HTTP_BASIC_AUTH
    _HTTP_BASIC_AUTH = f"Basic {base64.b64encode(f'{settings.JPUSH_APP_KEY}:{settings.JPUSH_MASTER_SECRET}'.encode('utf-8')).decode('utf-8')}"


async def clear_jpush_vars():
    pass


async def send_jpush(uid: str, push_title: str, push_content: str = "") -> bool:
    """Doc: https://docs.jiguang.cn/jpush/server/push/rest_api_v3_push"""
    done = False
    loguru_logger.debug("Try to send JPush for user.")
                    
    device_id, _, ok = await cache_instance().exist_or_get_string(key=CKEY_USER_DEVICE_ID.format(
        env=settings.DEPLOY_ENV, uid=uid
    ))
    if not ok:
        loguru_logger.error("Failed to send JPush for user, since we cannot get his/her device_id.")
        return False
    if len(device_id) == 0:
        loguru_logger.error("Failed to send JPush for user, since his/her device_id is empty.")
        return False    
    app_push_permission, _, ok = await cache_instance().exist_or_get_integer(key=CKEY_APP_PERMISSION_RECORD.format(
        env=settings.DEPLOY_ENV, device_id=device_id, permission_type=100
    ))
    if not ok:
        loguru_logger.error("Failed to send JPush for user, since we cannot get his/her app_push_permission.")
        return False
    if app_push_permission == 0:
        loguru_logger.warning("No need to push for user.")
        return True
    device_type, _, ok = await cache_instance().exist_or_get_integer(key=CKEY_USER_DEVICE_TYPE.format(
        env=settings.DEPLOY_ENV, uid=uid
    ))
    if not ok:
        loguru_logger.error("Failed to send JPush for user, since we cannot get his/her device_type.")
        return False
    if device_type == 0:
        device_type_symbol = "ios"
    elif device_type == 1:
        device_type_symbol = "android"
    else:
        device_type_symbol = "ios"
    registration_id, _, ok = await cache_instance().exist_or_get_string(key=CKEY_USER_JPUSH_REGISTRATION_ID.format(
        env=settings.DEPLOY_ENV, uid=uid
    ))
    if not ok:
        loguru_logger.error("Failed to send JPush for user, since we cannot get his/her registration_id.")
        return False
    if len(registration_id) == 0:
        loguru_logger.error("Failed to send JPush for user, since his/her registration_id is empty.")
        return False   

    session = get_aio_session()
    try:
        if device_type_symbol == "ios":
            notification = {
                "alert": push_title,
                "ios": {
                    "alert": push_title,
                    "badge": "+1"
                }
            }
        elif device_type_symbol == "android":
            notification = {
                "alert": push_title,
                "android": {
                    "alert": push_title,
                    "builder_id": 1
                }
            }
        payload = {
            "platform": [device_type_symbol],
            "audience": {
                "registration_id": [registration_id]
            },
            "notification": notification,
            "options": {
                "apns_production": settings.JPUSH_APNS_PRODUCTION_FLAG,
                "time_to_live": settings.JPUSH_TTL
            },
            "callback": {
                "url": "",
                "type": 8
            }
        }

        async with session.post(
            url="https://api.jpush.cn/v3/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": _HTTP_BASIC_AUTH,
            },
            data=json.dumps(payload),
            timeout=10,
        ) as response:
            response_body = await response.text()
            try:
                data = json.loads(response_body)
                if "error" not in data:
                    done = done
                    loguru_logger.debug("Pushed for user.")
                else:
                    loguru_logger.error(f"Failed api https://api.jpush.cn/v3/push, err_code:{data['error']['code']}, err_msg:{data['error']['message']}.")
            except json.JSONDecodeError as e:
                loguru_logger.error(f"Failed api https://api.jpush.cn/v3/push, JSONDecodeError:{e}.")
            except Exception:
                loguru_logger.error(f"Failed api https://api.jpush.cn/v3/push, err:{json.loads(response_body)}.")
    except Exception as e:
        loguru_logger.error(f"Failed api https://api.jpush.cn/v3/push, err:{e}.")

    return done
