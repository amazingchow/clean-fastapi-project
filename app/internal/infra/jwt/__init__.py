# -*- coding: utf-8 -*-
import datetime
import jwt

PrivatePem = b'''-----BEGIN RSA PRIVATE KEY-----
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
-----END RSA PRIVATE KEY-----'''

PublicPem = b'''-----BEGIN PUBLIC KEY-----
MIICITANBgkqhkiG9w0BAQEFAAOCAg4AMIICCQKCAgBjZ07FP8xa3I9KcCBdrIet
3lhhWB9+tcI8jC6ApofLBlYbwPONKqvFtDDdaIjMSy/rqXG7zFHKYoudfeEidhDi
7INumq3y68ISplcsCgZr9FOceNOdT/xLQDCxIcsCu2fjGE+00/XyuOszyNV5r1Lr
IWKMRRkXoGDSjxX3nI15kD6HfPFzm1mhna4E2RjpzzUtidEnHgVSKNft2RcH5UR5
PcMoZmhjMcu9fnZiZ74tyKEkkIO08XKHxrWstAo339ccdrnTRMXUV8UTxNfuZpwA
ERsDec7040yggHDbDJJiTFxGp7UaP409PU+qmhE08TIXPrxHAEcKuT+yRQUrgyf+
n8sRneTiyBG9SYCqixDmt4oksT33SFxqoA+wpO+oLTqVBXwH8tblJS0qj0t4mNcv
X2VKQydrtQzV+HL0KNfSUPShnBc4BP42zbpPu2dzOHLTG6bA+BZJypuQ3/dfIvg+
H17mVsStiEjVPjuZZcbFE2lbcAWlcQFdcsKGWFy/gAlro/gwkbQViltR67e2H7KI
rd+T0tVsk5z6zeyFy3JasIpTsBC8M0caAAfkG9qbwq7kkLeqQ//TOoJ/uZrr0yx8
lCiB1wnwmvhv0rewbFyRS2nl0+bNhk/dW+2X68TNTrWcy9cQxoeoB+8mLg3nHLSx
gxYuG/9SV/sgcIYt32HDGQIDAQAB
-----END PUBLIC KEY-----'''

SYS_ACCOUNT = "ums-admin"
SYS_DEVICE_ID = "ABCDEF12-34567890ABCDEF12"
SYS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2NvdW50IjoidW1zLWFkbWluIiwiZGV2aWNlX2lkIjoiQUJDREVGMTItMzQ1Njc4OTBBQkNERUYxMiIsImV4cCI6MTcyODk4NTQ3M30.AAvjyrHx0nLp2HzeZig8S0D43Pq1nSvldC7JYgelv-MQqpzOhG7JGq0MT54m19cxUgb2iH_Gpxd_yNPnvlr6HsFUq-jUy1Ns51VFgF60dQBENTLTdYPWfV92494bWwjc6AckNN0O9WOdwRAeBs_jnlC_idzqRVdQ2zzEdgZptBDlVkphholDIRSM_f9dBs8Ye2_IIyoDighpbOQLZnse4lCY0ndXrqES_s8ZRSJ12-N3apo81EbnwV6U115bPbdfU72Ae1Ms7YctGMphsa5tKsMiETi3r9ANehHPhWLt_lhPHvo3pLVX8egeqvkI1O-R0lMwugdfsj-pyFY2KTuAQP2yZtGTveXJNrt0DikpQBfSKq9I_DIL6lfgrOdsem7DNReAK_M3IYkgrllRtCy1cfukuJhcGlLTJvRgfRAwp_Tuy5iXoMJkZa_Swi8_RWm11dYc3L9zl4ZCyG35HqKCHBxjyEa2bKGteA5Qb9qexn0X-aTh_3KeGOQv5cwZBJibazIFGGZ3J-Sspt8W8bJAlEQVm_sgIakmfjkYFN3GhJUscXnZ31RPEjpfDs-XZq2OB3YYlauiFnSXERupc75UEDQdgZDv09cX0uaFj541GXPWSzsI8G-7MAz0-m-vCfDue2zEYaybyJaM3WAqkfJf4WbwtEXp7kpM98zYyDPlr-g"


def generate_access_token(account: str, device_id: str) -> str:
    encoded = jwt.encode(
        payload={
            "account": account,
            "device_id": device_id,
            "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=365 * 24 * 3600),
        },
        key=PrivatePem,
        algorithm="RS256",
    )
    return encoded


def verify_access_token(account: str, device_id: str, access_token: str) -> bool:
    try:
        decoded = jwt.decode(
            jwt=access_token,
            key=PublicPem,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "require": ["exp"],
            },
            leeway=datetime.timedelta(seconds=3600),
        )
    except jwt.ExpiredSignatureError:
        return False

    if isinstance(decoded, dict) and \
        ("account" in decoded and decoded["account"] == account) and \
        ("device_id" in decoded and decoded["device_id"] == device_id):
        return True
    return False


if __name__ == "__main__":
    token = generate_access_token(SYS_ACCOUNT, SYS_DEVICE_ID)
    print(token)
    print(verify_access_token(SYS_ACCOUNT, SYS_DEVICE_ID, token))
