# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import os
import struct
import time

from typing import Optional
from urllib.parse import urlencode


def generate_secret_key(length: int = 16) -> str:
    """
    Generates a secret key of specified length.

    Args:
        length (int): The length of the secret key. Default is 16.

    Returns:
        str: The generated secret key.

    Raises:
        TypeError: If the length is less than 8 or greater than 128.
    """

    def _generate_random_bytes() -> bytes:
        sha_hash = hashlib.sha512()
        sha_hash.update(os.urandom(8192))
        byte_hash = sha_hash.digest()

        for _ in range(6):
            sha_hash = hashlib.sha512()
            sha_hash.update(byte_hash)
            byte_hash = sha_hash.digest()

        return byte_hash
    
    if length < 8 or length > 128:
        raise TypeError('Secret key length is invalid.')

    byte_hash = _generate_random_bytes()
    if length > 102:
        byte_hash += _generate_random_bytes()
    
    text = base64.b32encode(byte_hash)[:length]
    text = str(text.decode('latin1'))

    return text


def validate_secret(secret: str) -> bool:
    """
    Validates a secret by checking if it is a valid base32 encoded string.

    Args:
        secret (str): The secret to be validated.

    Returns:
        bool: True if the secret is valid, False otherwise.
    """
    token = secret.replace(' ', '').upper()
    try:
        base64.b32decode(token)
    except Exception:
        return False
    return True


def generate_code(secret: str, value: Optional[int] = None) -> bytes:
    """
    Generates a time-based one-time password (TOTP) code using the given secret and value.

    Args:
        secret (str): The secret key used for generating the code.
        value (Optional[int]): The value used for generating the code. If not provided, the current time is used.

    Returns:
        bytes: The generated TOTP code.

    Raises:
        ValueError: If there is an error decoding the secret key.
    """
    if value is None:
        value = int(time.time() / 30)
    value = struct.pack('>q', value)
    token = secret.replace(' ', '').upper()
    try:
        secretkey = base64.b32decode(token)
    except Exception:
        raise ValueError('BASE32-DECODING-ERROR')

    hash = hmac.new(secretkey, value, hashlib.sha1).digest()

    offset = struct.unpack('>B', hash[-1:])[0] & 0xf
    truncated_hash = hash[offset:offset + 4]

    truncated_hash = struct.unpack('>L', truncated_hash)[0]
    truncated_hash &= 0x7fffffff
    truncated_hash %= 1000000

    return '%06d' % truncated_hash


def verify_counter_based(secret: str, code: str, counter: int, window: int = 3) -> Optional[int]:
    """
    Verifies a counter-based one-time password (OTP) code.

    Args:
        secret (str): The secret key used to generate the OTP.
        code (str): The OTP code to be verified.
        counter (int): The counter value used to generate the OTP.
        window (int, optional): The number of future counter values to check. Defaults to 3.

    Returns:
        Optional[int]: The counter value if the code is valid, None otherwise.
    """
    if (not isinstance(code, str)) and (not isinstance(code, bytes)):
        raise TypeError('code must be a string')

    for offset in range(1, window + 1):
        valid_code = generate_code(secret, counter + offset)
        if code == valid_code:
            return counter + offset
    
    return None


def verify_time_based(secret: str, code: str) -> Optional[int]:
    """
    Verifies a time-based one-time password (TOTP) code.

    Args:
        secret (str): The secret key used for generating TOTP codes.
        code (str): The TOTP code to be verified.

    Returns:
        Optional[int]: The current epoch time if the code is valid, None otherwise.
    """
    if (not isinstance(code, str)) and (not isinstance(code, bytes)):
        raise TypeError('code must be a string')

    epoch = int(time.time() / 30)
    offset = 0
    valid_code = generate_code(secret, epoch + offset)
    if code == valid_code:
        return epoch + offset
    
    return None


def get_otpauth_url(user: str, domain: str, secret: str) -> str:
    """
    Generate the OTPAuth URL for the given user, domain, and secret.

    Args:
        user (str): The user identifier.
        domain (str): The domain or service name.
        secret (str): The secret key for generating the OTP.

    Returns:
        str: The OTPAuth URL.
    """
    return 'otpauth://totp/' + user + '@' + domain + '?secret=' + secret


def get_barcode_url(user: str, domain: str, secret: str) -> str:
    """
    Generates a barcode URL for the given user, domain, and secret.

    Args:
        user (str): The user identifier.
        domain (str): The domain or service name.
        secret (str): The secret key for generating the OTP.

    Returns:
        str: The generated barcode URL.
    """
    url = 'https://www.google.com/chart?chs=200x200&chld=M|0&cht=qr&'
    opt_url = get_otpauth_url(user, domain, secret)
    url += urlencode({'chl': opt_url})
    return url
