# -*- coding: utf-8 -*-
import asyncio
import jsonschema
import time

from internal.infra.alarm import perror
from internal.singleton import Singleton
from loguru import logger as loguru_logger
from kafka import KafkaProducer
from kafka.errors import KafkaError
from routers.proto_gens.messages_pb2 import GameResult
from routers.proto_gens.messages_pb2 import RoomEvent, \
    RoomEventType, \
    EnterRoomEvent, \
    LeaveRoomEvent, \
    EnterQueueEvent, \
    LeaveQueueEvent, \
    InQueueBeReadyEvent, \
    InQueueNotBeReadyEvent, \
    Start3rdPartyGameEvent, \
    End3rdPartyGameEvent
from typing import Any, \
    Dict, \
    Optional


class kafkaProducerSetupException(Exception):
    pass


class kafkaProducer(metaclass=Singleton):
    '''
    自定义Kafka Producer客户端
    '''

    KAFKA_PRODUCER_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "brokers": {"type": "array", "items": {"type": "string"}},
            "client_id": {"type": "string"},
            "default_topic": {"type": "string"},
            "default_room_event_topic": {"type": "string"},
        },
        "required": [
            "brokers",
            "client_id",
            "default_topic",
            "default_room_event_topic",
        ],
    }

    def __init__(self, conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None) -> None:
        if not self._validate_config(conf):
            raise kafkaProducerSetupException("Please provide valid kafka producer config file.")

        self._producer = KafkaProducer(
            bootstrap_servers=conf["brokers"],
            client_id=conf["client_id"],
            api_version=(0, 10, 2),
            request_timeout_ms=5000,
        )
        self.default_topic = conf["default_topic"]
        self.default_room_event_topic = conf["default_room_event_topic"]

    def _validate_config(self, conf: Optional[Dict[str, Any]] = None) -> bool:
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=self.KAFKA_PRODUCER_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid kafka producer config:{conf}.")
        finally:
            return valid

    async def is_connected(self) -> bool:
        connected = False
        try:
            connected = True
            await asyncio.sleep(0.1)
        except KafkaError:
            raise kafkaProducerSetupException("Please check connectivity with kafka server.")
        finally:
            return connected

    async def send_msg(self, topic: Optional[str] = None, key: str = "", result: Dict[str, Any] = {}) -> bool:
        done = False
        try:
            _topic = topic if topic else self.default_topic
            loguru_logger.debug(f"Try to send one message to topic:{_topic}...")

            msg = GameResult()
            if result["err_code"] != 0:
                msg.trace_id = result["request_id"]
                msg.status_code = result["err_code"]
                msg.app_user_id = result["app_uid"]
                msg.app_user_nickname = result["app_user_nickname"]
                msg.app_user_avatar = result["app_user_avatar"]
                msg.app_ai_player_id = result["app_aid"]
                msg.app_ai_player_nickname = result["app_ai_player_nickname"]
                msg.app_ai_player_avatar = result["app_ai_player_avatar"]
                msg.app_room_id = result["app_room_id"]
                msg.app_game_index = result["app_game_index"]
                msg.game_region = result["game_region"]
                msg.game_uid = result["uid"]
                msg.game_bid = result["bot_id"]
                msg.order_id = result["order_id"]
                msg.result_type = result["result_type"]
                msg.receive_time = int(time.time() * 1000)
            else:
                if "result" in result:
                    result_game_idx = result["result"]["game_idx"] if isinstance(result["result"], dict) and "game_idx" in result["result"] else -1
                else:
                    result_game_idx = -1
                if "result" in result:
                    result_win = result["result"]["win"] if isinstance(result["result"], dict) and "win" in result["result"] else False
                else:
                    result_win = False
                if "result" in result:
                    result_screenshots = result["result"]["screenshots"] if isinstance(result["result"], dict) and "screenshots" in result["result"] else []
                else:
                    result_screenshots = []
                msg.trace_id = result["request_id"]
                msg.status_code = 0
                msg.app_user_id = result["app_uid"]
                msg.app_user_nickname = result["app_user_nickname"]
                msg.app_user_avatar = result["app_user_avatar"]
                msg.app_ai_player_id = result["app_aid"]
                msg.app_ai_player_nickname = result["app_ai_player_nickname"]
                msg.app_ai_player_avatar = result["app_ai_player_avatar"]
                msg.app_room_id = result["app_room_id"]
                msg.app_game_index = result["app_game_index"]
                msg.game_region = result["game_region"]
                msg.game_uid = result["uid"]
                msg.game_bid = result["bot_id"]
                msg.order_id = result["order_id"]
                msg.result_type = result["result_type"]
                msg.result_game_idx = result_game_idx
                msg.result_win = result_win
                msg.result_screenshots.extend(result_screenshots)
                msg.receive_time = int(time.time() * 1000)
            future = self._producer.send(
                _topic,
                key=key.encode("utf-8"),
                value=msg.SerializeToString(),
            )
            future.get(timeout=5)

            done = True
            loguru_logger.debug(f"Send one message to topic:{_topic}.")
        except KafkaError as e:
            await perror(f"Failed to send message to topic:{_topic}, kafka-err:{e}.")
        except Exception as e:
            await perror(f"Failed to send message to topic:{_topic}, err:{e}.")
        finally:
            return done

    async def send_room_event(self, topic: Optional[str] = None, key: str = "", raw_event: Dict[str, Any] = {}) -> bool:
        done = False
        try:
            _topic = topic if topic else self.default_room_event_topic
            loguru_logger.debug(f"Try to send one message to topic:{_topic}...")

            if raw_event["type"] == RoomEventType.EVENT_TYPE_USER_ENTER_ROOM:
                event = EnterRoomEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_LEAVE_ROOM:
                event = LeaveRoomEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_ENTER_QUEUE:
                event = EnterQueueEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_full = raw_event["queue_is_full"]
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_LEAVE_QUEUE:
                event = LeaveQueueEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_full = False
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_IN_QUEUE_BE_READY:
                event = InQueueBeReadyEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_ready = raw_event["queue_is_ready"]
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_IN_QUEUE_NOT_BE_READY:
                event = InQueueNotBeReadyEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_ready = False
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_START_3RD_PARTY_GAME:
                event = Start3rdPartyGameEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_in_game_battle = raw_event["queue_is_in_game_battle"]
            elif raw_event["type"] == RoomEventType.EVENT_TYPE_USER_END_3RD_PARTY_GAME:
                event = End3rdPartyGameEvent()
                event.room_id = raw_event["room_id"]
                event.game_index = raw_event["game_index"]
                event.be_hosting = raw_event["be_hosting"]
                event.uid = raw_event["uid"]
                event.nickname = raw_event["nickname"]
                event.avatar = raw_event["avatar"]
                event.owner_id = raw_event["owner_id"]
                event.owner_nickname = raw_event["owner_nickname"]
                event.owner_avatar = raw_event["owner_avatar"]
                event.queue_is_in_game_battle = False

            msg = RoomEvent()
            msg.event_type = raw_event["type"]
            msg.event_body = event.SerializeToString()
            msg.trace_id = raw_event["trace_id"]
            msg.timestamp = int(time.time() * 1000)
            future = self._producer.send(
                _topic,
                key=key.encode("utf-8"),
                value=msg.SerializeToString(),
            )
            future.get(timeout=5)

            done = True
            loguru_logger.debug(f"Send one message to topic:{_topic}.")
        except KafkaError as e:
            await perror(f"Failed to send message to topic:{_topic}, kafka-err:{e}.")
        except Exception as e:
            await perror(f"Failed to send message to topic:{_topic}, err:{e}.")
        finally:
            return done

    async def close(self):
        self._producer.close()
        await asyncio.sleep(0.1)


_instance: kafkaProducer = None


def init_instance(conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
    global _instance
    _instance = kafkaProducer(conf, io_loop)


def instance() -> kafkaProducer:
    return _instance
