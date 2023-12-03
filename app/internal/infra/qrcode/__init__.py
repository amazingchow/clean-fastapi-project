# -*- coding: utf-8 -*-
import qrcode.constants as qrcode_constants
import time
from PIL import Image
from qrcode.main import QRCode
from typing import Optional

qr = None


def init_qr_instance():
    ''''
    使用说明:
    
    The version parameter is an integer from 1 to 40 that controls the size of
    the QR Code (the smallest, version 1, is a 21x21 matrix). Set to None and
    use the fit parameter when making the code to determine this automatically.

    The error_correction parameter controls the error correction used for the
    QR Code. The following four constants are made available on the qrcode package:

    ERROR_CORRECT_L
    About 7% or less errors can be corrected.

    ERROR_CORRECT_M (default)
    About 15% or less errors can be corrected.

    ERROR_CORRECT_Q
    About 25% or less errors can be corrected.

    ERROR_CORRECT_H.
    About 30% or less errors can be corrected.

    The box_size parameter controls how many pixels each “box” of the QR code is.

    The border parameter controls how many boxes thick the border should be (the
    default is 4, which is the minimum according to the specs).
    '''
    global qr
    qr = QRCode(
        version=None,
        error_correction=qrcode_constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )


def new_qr_code(url: str) -> Optional[Image.Image]:
    img = None
    if qr is not None:
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
    return img


if __name__ == "__main__":
    init_qr_instance()
    t1 = time.time()
    img = new_qr_code("https://go.onelink.me/?af_siteid=6467121828&deep_link_value=JZfGzoj&af_referrer_uid=1697437223454-2299504&c=app_invite&pid=af_app_invites&af_sub1=app_invite_code")
    img.save("link.png")
    t2 = time.time()
    print(f"used {t2 - t1:.3f}s")
