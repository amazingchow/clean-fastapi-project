# -*- coding: utf-8 -*-
import base64
import time
import ujson as json

from dependencies import settings
from internal.extensions.ext_redis import instance as cache_instance
from internal.infra.alarm import perror
from internal.infra.http_session import get_aio_session
from loguru import logger as loguru_logger
from typing import Tuple

_HTTP_BASIC_AUTH = None


async def init_sms_vars():
    global _HTTP_BASIC_AUTH
    _HTTP_BASIC_AUTH = f"Basic {base64.b64encode(f'{settings.SMS_APP_KEY}:{settings.SMS_MASTER_SECRET}'.encode('utf-8')).decode('utf-8')}"

async def clear_sms_vars():
    pass


async def send_short_message(phone_number: str) -> Tuple[int, bool]:
    done = False
    invalid_mobile = False
    
    remaining, _ = await cache_instance().get_daily_token(key=f"ai_play_user_{phone_number}_daily_tokens")
    if remaining == 0:
        return (0, False)

    session = get_aio_session()
    try:
        url = "https://api.sms.jpush.cn/v1/codes"
        loguru_logger.debug(f"Try to invoke api {url}.")
        async with session.post(
            url=url,
            headers={
                "Content-Type": "application/json",
                "Authorization": _HTTP_BASIC_AUTH,
            },
            data=json.dumps({
                "mobile": phone_number,
                "sign_id": settings.SMS_SIGN_ID,
                "temp_id": settings.SMS_TEMP_ID,
            }),
            timeout=10,
        ) as response:
            response_body = await response.text()
            try:
                data = json.loads(response_body)
                if "error" not in data:
                    msg_id = data["msg_id"]
                    done = await cache_instance().cache_string(
                        key=phone_number, value=json.dumps({"msg_id": msg_id, "expired": int(time.time())}))
                else:
                    if data["error"]["message"] == "invalid mobile":
                        invalid_mobile = True
                    else:
                        await perror(f"Failed api {url}, err_code:{data['error']['code']}, err_msg:{data['error']['message']}.")
            except json.JSONDecodeError as e:
                await perror(f"Failed api {url}, JSONDecodeError:{e}.")
            except Exception:
                await perror(f"Failed api {url}, err:{json.loads(response_body)}.")
    except Exception as e:
        await perror(f"Failed api {url}, err:{e}.")
    
    if invalid_mobile:
        return (-2, False)
    if not done:
        return (-1, False)
    
    if done:
        remaining, _ = await cache_instance().take_daily_token(key=f"ai_play_user_{phone_number}_daily_tokens")
    else:
        remaining = 1
    return (remaining, done)


async def verify_short_message(phone_number: str, code: str) -> Tuple[bool, bool]:
    is_valid = False
    done = False

    value, existed, _ = await cache_instance().exist_or_get_string(key=phone_number)
    if not existed:
        done = True
        loguru_logger.error(f"Failed SM verify, phone_number:{phone_number} has not appeared.")
        return (is_valid, done)
    msg_data = json.loads(value)
    msg_id, ts = msg_data["msg_id"], msg_data["expired"]
    if int(time.time()) - ts > settings.SM_PERIOD_OF_VALIDITY:
        done = True
        loguru_logger.error(f"Failed SM verify, phone_number:{phone_number}, code:{code} has been expired.")
        return (is_valid, done)

    session = get_aio_session()
    try:
        url = f"https://api.sms.jpush.cn/v1/codes/{msg_id}/valid"
        loguru_logger.debug(f"Try to invoke api {url}.")
        async with session.post(
            url=url,
            headers={
                "Content-Type": "application/json",
                "Authorization": _HTTP_BASIC_AUTH,
            },
            data=json.dumps({
                "code": code,
            }),
            timeout=10,
        ) as response:
            response_body = await response.text()
            try:
                data = json.loads(response_body)
                is_valid = data["is_valid"]
                if not is_valid:
                    await perror(f"Failed SM verify, err_code:{data['error']['code']}, err_msg:{data['error']['message']}.")
                else:
                    loguru_logger.debug("Done SM verify.")
                done = True
            except json.JSONDecodeError as e:
                await perror(f"Failed api {url}, err:{e}.")
    except Exception as e:
        await perror(f"Failed api {url}, err:{e}.")

    return (is_valid, done)
