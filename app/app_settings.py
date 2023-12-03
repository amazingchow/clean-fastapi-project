# -*- coding: utf-8 -*-
import os

from pydantic_settings import BaseSettings
from typing import List

DEFAULTS = {
    "SKIP_APP_VERSION_CHECK": "false",
    "APP_VERSION": "0.1.0",
    "DEPLOY_ENV": "dev",
    "LOG_SERVICE_NAME": "GameCompanionPlatformApiGatewayService",
    "LOG_LEVEL": "debug",
    "LOG_PRINTER": "disk",  # or "console"
    "LOG_PRINTER_FILENAME": "./GameCompanionPlatformApiGatewayService.dev.log",
    "NICKNAME_FILE_LOCKER": "./user_nickname.txt.lock",
    "NICKNAME_FILE_STORE": "./user_nickname.txt",
    "MONGODB_SERVER_ENDPOINTS": "localhost:27117,localhost:27118,localhost:27119",
    "MONGODB_USERNAME": "root",
    "MONGODB_PASSWORD": "aExc_NlfDrs_PXsL",
    "MONGODB_AUTH_MECHANISM": "SCRAM-SHA-256",
    "MONGODB_DATABASE": "ai_play",
    "MONGODB_REPLICA_SET": "replicaset",
    "REDIS_SERVER_ENDPOINT": "localhost:6379",
    "REDIS_PASSWORD": "sOmE_sEcUrE_pAsS",
    "REDIS_DB": "0",
    "CELERY_BROKER_URL": "redis://:sOmE_sEcUrE_pAsS@localhost:6379/2",
    "CELERY_BROKER_USE_SSL": "false",
    "CELERY_RESULT_BACKEND_URL": "redis://:sOmE_sEcUrE_pAsS@localhost:6379/2",
    "CELERY_RESULT_BACKEND_USE_SSL": "false",
    "KAFKA_BROKERS": "localhost:9092",
    "KAFKA_PRODUCER_CLIENT_ID": "GameCompanionPlatformApiGatewayService_dev",
    "KAFKA_PRODUCER_TOPIC": "game-companion-platform-game-result-dev",
    "KAFKA_PRODUCER_ROOM_EVENT_TOPIC": "game-companion-platform-room-event-dev",
    "OSS_GRPC_ENDPOINT": "localhost:17774",
    "OSS_BUCKET": "go",
    "CAS_GRPC_ENDPOINT": "localhost:17375",
    "USS_GRPC_ENDPOINT": "localhost:17778",
    "TOKEN_VALID_DURATION": "365",
    "SMS_APP_KEY": "65d5c97cc6330f8e702d91fb",
    "SMS_MASTER_SECRET": "99ef7ed0f1706087c9626178",
    "SMS_SIGN_ID": "26211",
    "SMS_TEMP_ID": "221148",
    "SM_PERIOD_OF_VALIDITY": "60",
    "JPUSH_APP_KEY": "fe175316f2fbba4f06c555e4",
    "JPUSH_MASTER_SECRET": "bd008f7f890615a93acea456",
    "JPUSH_APNS_PRODUCTION_FLAG": "false",
    "JPUSH_TTL": "60",
    "GOOG_AUTH_DOMAIN": "AiPlay",
    "GOOG_AUTH_SEC_KEY": "XCR5YUHYRGVTJLV4",
}


def get_env(key: str) -> str:
    return os.environ.get(key, DEFAULTS.get(key))


def get_bool_env(key: str) -> bool:
    return get_env(key).lower() == "true"


def get_int_env(key: str) -> int:
    return int(get_env(key))


def get_array_env(key: str) -> List[str]:
    return get_env(key).split(",")


class AppSettings(BaseSettings):
    SKIP_APP_VERSION_CHECK: bool = get_bool_env("SKIP_APP_VERSION_CHECK")
    APP_VERSION: str = get_env("APP_VERSION")
    DEPLOY_ENV: str = get_env("DEPLOY_ENV")
    LOG_SERVICE_NAME: str = get_env("LOG_SERVICE_NAME")
    LOG_LEVEL: str = get_env("LOG_LEVEL")
    LOG_PRINTER: str = get_env("LOG_PRINTER")
    LOG_PRINTER_FILENAME: str = get_env("LOG_PRINTER_FILENAME")
    NICKNAME_FILE_LOCKER: str = get_env("NICKNAME_FILE_LOCKER")
    NICKNAME_FILE_STORE: str = get_env("NICKNAME_FILE_STORE")
    MONGODB_SERVER_ENDPOINTS: List[str] = get_array_env("MONGODB_SERVER_ENDPOINTS")
    MONGODB_USERNAME: str = get_env("MONGODB_USERNAME")
    MONGODB_PASSWORD: str = get_env("MONGODB_PASSWORD")
    MONGODB_AUTH_MECHANISM: str = get_env("MONGODB_AUTH_MECHANISM")
    MONGODB_DATABASE: str = get_env("MONGODB_DATABASE")
    MONGODB_REPLICA_SET: str = get_env("MONGODB_REPLICA_SET")
    REDIS_SERVER_ENDPOINT: str = get_env("REDIS_SERVER_ENDPOINT")
    REDIS_PASSWORD: str = get_env("REDIS_PASSWORD")
    REDIS_DB: int = get_int_env("REDIS_DB")
    CELERY_BROKER_URL: str = get_env("CELERY_BROKER_URL")
    CELERY_BROKER_USE_SSL: bool = get_bool_env("CELERY_BROKER_USE_SSL")
    CELERY_RESULT_BACKEND_URL: str = get_env("CELERY_RESULT_BACKEND_URL")
    CELERY_RESULT_BACKEND_USE_SSL: bool = get_bool_env("CELERY_RESULT_BACKEND_USE_SSL")
    KAFKA_BROKERS: List[str] = get_array_env("KAFKA_BROKERS")
    KAFKA_PRODUCER_CLIENT_ID: str = get_env("KAFKA_PRODUCER_CLIENT_ID")
    KAFKA_PRODUCER_TOPIC: str = get_env("KAFKA_PRODUCER_TOPIC")
    KAFKA_PRODUCER_ROOM_EVENT_TOPIC: str = get_env("KAFKA_PRODUCER_ROOM_EVENT_TOPIC")
    OSS_GRPC_ENDPOINT: str = get_env("OSS_GRPC_ENDPOINT")
    OSS_BUCKET: str = get_env("OSS_BUCKET")
    CAS_GRPC_ENDPOINT: str = get_env("CAS_GRPC_ENDPOINT")
    USS_GRPC_ENDPOINT: str = get_env("USS_GRPC_ENDPOINT")
    TOKEN_VALID_DURATION: int = get_int_env("TOKEN_VALID_DURATION")
    SMS_APP_KEY: str = get_env("SMS_APP_KEY")
    SMS_MASTER_SECRET: str = get_env("SMS_MASTER_SECRET")
    SMS_SIGN_ID: int = get_int_env("SMS_SIGN_ID")
    SMS_TEMP_ID: int = get_int_env("SMS_TEMP_ID")
    SM_PERIOD_OF_VALIDITY: int = get_int_env("SM_PERIOD_OF_VALIDITY")
    JPUSH_APP_KEY: str = get_env("JPUSH_APP_KEY")
    JPUSH_MASTER_SECRET: str = get_env("JPUSH_MASTER_SECRET")
    JPUSH_APNS_PRODUCTION_FLAG: bool = get_bool_env("JPUSH_APNS_PRODUCTION_FLAG")
    JPUSH_TTL: int = get_int_env("JPUSH_TTL")
    GOOG_AUTH_DOMAIN: str = get_env("GOOG_AUTH_DOMAIN")
    GOOG_AUTH_SEC_KEY: str = get_env("GOOG_AUTH_SEC_KEY")
    CCS_OSS_SERVER: str = get_env("CCS_OSS_SERVER")
    CCS_OSS_AUTH_SID: str = get_env("CCS_OSS_AUTH_SID")
    CCS_OSS_AUTH_SKEY: str = get_env("CCS_OSS_AUTH_SKEY")
    ALARM_RECEIVERS: str = get_env("ALARM_RECEIVERS")
    BUSINESS_CONF_FILES: str = get_env("BUSINESS_CONF_FILES")
    GAME_AI_API_SERVER_ENDPOINT: str = get_env("GAME_AI_API_SERVER_ENDPOINT")
    GANE_RESULT_CALLBACK_URL: str = get_env("GANE_RESULT_CALLBACK_URL")
    SECS_OF_BEING_KICKED_OUT_FROM_THE_GAME_QUEUE: int = get_int_env("SECS_OF_BEING_KICKED_OUT_FROM_THE_GAME_QUEUE")
    SECS_OF_BEING_TURNED_OFF_IN_GAME_BATTLE: int = get_int_env("SECS_OF_BEING_TURNED_OFF_IN_GAME_BATTLE")


app_settings = AppSettings()
