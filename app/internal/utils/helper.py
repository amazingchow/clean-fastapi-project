# -*- coding: utf-8 -*-
import datetime
import hashlib
import random
import re
import sys
import time

from typing import Any, List, Tuple


def get_midnight_timestamp() -> int:
    tm = datetime.date.today() + datetime.timedelta(days=1)
    midnight = datetime.datetime.combine(tm, datetime.datetime.min.time())
    return int(midnight.timestamp())


def async_wrapper(func):
    async def inner(*args, **kwargs):
        func(*args, **kwargs)
    return inner


def new_uid() -> str:
    return f"User_{int(time.time())}{random.randint(1000, 9999)}"


def new_request_id() -> str:
    return hashlib.md5("{}_{}".format(time.time(), random.randint(0, 10000)).encode()).hexdigest()


ALL_DIGIT_NUMS_AND_LETTERS = [str(i) for i in range(0, 10)] + \
    [str(chr(i)) for i in range(ord('a'), ord('z') + 1)] + \
    [str(chr(i)) for i in range(ord('A'), ord('Z') + 1)]
ALL_DIGIT_NUMS_AND_LETTERS_TOTAL = len(ALL_DIGIT_NUMS_AND_LETTERS)


def gen_n_digit_nums_and_letters(n: int) -> str:
    seed = random.randrange(sys.maxsize)
    random.seed(seed)
    for i in range(len(ALL_DIGIT_NUMS_AND_LETTERS) - 1, 0, -1):
        j = random.randrange(i + 1)
        ALL_DIGIT_NUMS_AND_LETTERS[i], ALL_DIGIT_NUMS_AND_LETTERS[j] = ALL_DIGIT_NUMS_AND_LETTERS[j], ALL_DIGIT_NUMS_AND_LETTERS[i]
    nums_and_letters = [ALL_DIGIT_NUMS_AND_LETTERS[random.randrange(ALL_DIGIT_NUMS_AND_LETTERS_TOTAL)] for _ in range(n)]
    return "".join(nums_and_letters)


def check_phone_number(number: str) -> bool:
    return re.search(r'^((13[0-9])|(14[0-9])|(15[0-9])|(16[0-9])|(17[0-9])|(18[0-9])|(19[0-9]))\d{8}$', number) is not None


def remove_one_item_from_list(arr: List[Any], target: Any) -> List[Any]:
    if len(arr) == 0:
        return []
    i = -1
    for j in range(len(arr)):
        if arr[j] == target:
            i = j
            break
    if i >= 0:
        if i == 0:
            return arr[1:]
        elif i == len(arr) - 1:
            return arr[:-1]
        else:
            return arr[:i] + arr[i + 1:]
    return arr


def remove_duplicates_from_list(arr: List[Any]) -> Tuple[List[Any], bool]:
    new_arr = list(set(arr))
    return (new_arr, len(new_arr) == len(arr))


if __name__ == "__main__":
    print(f"get_midnight_timestamp() == {get_midnight_timestamp()}")
    print(f"new_uid() == {new_uid()}")
    print(f"new_request_id() == {new_request_id()}")
    print(f"gen_n_digit_nums_and_letters(7) == {gen_n_digit_nums_and_letters(7)}")
    print(f"check_phone_number('15527011768') == {check_phone_number('15527011768')}")
    print(f"remove_one_item_from_list(['a', 'b', 'c', 'a', 'd'], 'b') == {remove_one_item_from_list(['a', 'b', 'c', 'a', 'd'], 'b')}")
    print(f"remove_duplicates_from_list(['a', 'b', 'c', 'a', 'd']) == {remove_duplicates_from_list(['a', 'b', 'c', 'a', 'd'])}")
