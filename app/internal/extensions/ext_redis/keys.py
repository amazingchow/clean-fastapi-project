# -*- coding: utf-8 -*-

# 用户总数
CKEY_TOTAL_USER_CNT_KEY = "gcp_ags_{env}_total_user_cnt"
# 应用权限
CKEY_APP_PERMISSION_RECORD = "gcp_ags_{env}_app_permission_{device_id}_{permission_type}"
# 设备类型
CKEY_USER_DEVICE_TYPE = "gcp_ags_{env}_device_type_{uid}"
# 设备ID
CKEY_USER_DEVICE_ID = "gcp_ags_{env}_device_id_{uid}"
# 设备ID
CKEY_USER_DEVICE_ID_EXT = "gcp_ags_{env}_device_id_{account}"
# 用于极光推送的注册ID
CKEY_USER_JPUSH_REGISTRATION_ID = "gcp_ags_{env}_jpush_registration_id_{uid}"
# 用于极光推送的注册ID
CKEY_USER_JPUSH_REGISTRATION_ID_EXT = "gcp_ags_{env}_jpush_registration_id_{account}"
# 用于判断用户是否在线
CKEY_USER_ONLINE = "gcp_ags_{env}_user_{uid}_online"
# 用户所在房间的ID
CKEY_USER_ENTERED_ROOM = "gcp_ags_{env}_user_{uid}_entered_room"
# 房间内的在线用户ID列表
CKEY_ROOM_ONLINE_USERS = "gcp_ags_{env}_room_{room_id}_online_users"
# 房间内的车队用户ID列表
CKEY_ROOM_IN_GAME_QUEUE_USERS = "gcp_ags_{env}_room_{room_id}_in_game_queue_users"
# 房间内处于准备状态的车队用户ID列表
CKEY_ROOM_IN_GAME_QUEUE_BE_READY_USERS = "gcp_ags_{env}_room_{room_id}_in_game_queue_be_ready_users"
# 房间内的车队锁
CKEY_ROOM_GAME_QUEUE_LOCK = "gcp_ags_{env}_room_{room_id}_game_queue_lock"
# 房间内用户是否需要发送游戏卡片
CKEY_ROOM_USER_SEND_GAME_CARD = "gcp_ags_{env}_user_{uid}_send_game_card"
# 用户专属的后台101任务
CKEY_USER_BACKGROUND_101_DELAY_TASK = "gcp_ags_{env}_user_{uid}_background_101_delay_task"
# 用户专属的后台102任务
CKEY_USER_BACKGROUND_102_DELAY_TASK = "gcp_ags_{env}_user_{uid}_background_102_delay_task"
