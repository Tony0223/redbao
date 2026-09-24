"""
微信支付 APIv3 最小封装 —— 只覆盖"商家转账·用户授权免确认模式"用到的接口：

1. 发起免确认收款授权    POST /v3/fund-app/mch-transfer/user-confirm-authorization
2. 商户单号查询授权结果  GET  /v3/fund-app/mch-transfer/user-confirm-authorization/out-authorization-no/{no}
3. 用户授权后转账        POST /v3/fund-app/mch-transfer/transfer-bills/transfer
4. 商户单号查询转账单    GET  /v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{no}
外加：应答/回调验签（微信支付公钥）、回调报文解密（APIv3密钥，AES-256-GCM）。

所有密钥参数从环境变量读取（.env），这个文件里不写死任何密钥。
自检：在后端根目录执行  venv/bin/python -m app.wxpay
"""
import base64
import json
import os
import secrets
import time
from functools import lru_cache
from urllib.parse import quote

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOST = "https://api.mch.weixin.qq.com"

# 佣金报酬场景（本商户号唯一已开通的场景，ID 1005）。
# 收款感知只能传：劳务报酬 / 报销款 / 企业补贴 / 开工利是
# 报备信息必须固定两条：岗位类型、报酬说明（各≤32字）
TRANSFER_SCENE_ID = "1005"
USER_RECV_PERCEPTION = "劳务报酬"
SCENE_REPORT_INFOS = [
    {"info_type": "岗位类型", "info_content": "广告任务推广员"},
    {"info_type": "报酬说明", "info_content": "完成广告任务报酬提现"},
]


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}，请在 .env 里配置")
    return value


class WxPayError(Exception):
    """调用微信失败。用 is_uncertain 判断结果是否不明确。"""

    def __init__(self, status_code: int, code: str, message: str, body: str = ""):
        super().__init__(f"[{status_code}] {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.body = body

    @property
    def is_uncertain(self) -> bool:
        """
        结果不明确：系统错误、限频、网络异常、应答验签失败。
        这种情况钱可能已经转出去了——必须保持原单号，靠查单确认，绝不能换单号重发。
        """
        return (
            self.status_code == 0
            or self.status_code >= 500
            or self.status_code == 429
            or self.code in ("SYSTEM_ERROR", "NETWORK_ERROR", "RESPONSE_SIGN_INVALID")
        )


class WxPayClient:
    def __init__(self):
        self.mchid = _env("WXPAY_MCHID")
        self.appid = _env("WXPAY_APPID")
        self.cert_serial_no = _env("WXPAY_CERT_SERIAL_NO")
        self.public_key_id = _env("WXPAY_PUBLIC_KEY_ID")
        self.apiv3_key = _env("WXPAY_APIV3_KEY").encode("utf-8")
        if len(self.apiv3_key) != 32:
            raise RuntimeError("WXPAY_APIV3_KEY 必须是32位字符串")

        with open(_env("WXPAY_PRIVATE_KEY_PATH"), "rb") as f:
            self._private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(_env("WXPAY_PUBLIC_KEY_PATH"), "rb") as f:
            self._wechat_public_key = serialization.load_pem_public_key(f.read())

    # ---------------- 签名 / 验签 / 解密 ----------------

    def _build_authorization(self, method: str, path: str, body: str) -> str:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64encode(
            self._private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        ).decode("ascii")
        return (
            "WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.mchid}",nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{self.cert_serial_no}"'
        )

    def verify_signature(self, headers, body: str, max_skew_seconds: int = 300) -> bool:
        """验证微信的应答/回调确实来自微信（headers 大小写不敏感的 dict 即可）。"""
        timestamp = headers.get("Wechatpay-Timestamp")
        nonce = headers.get("Wechatpay-Nonce")
        signature = headers.get("Wechatpay-Signature")
        serial = headers.get("Wechatpay-Serial")
        if not (timestamp and nonce and signature):
            return False
        if serial and serial != self.public_key_id:
            return False
        try:
            if abs(time.time() - int(timestamp)) > max_skew_seconds:
                return False
            self._wechat_public_key.verify(
                base64.b64decode(signature),
                f"{timestamp}\n{nonce}\n{body}\n".encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except (InvalidSignature, ValueError):
            return False

    def decrypt_resource(self, resource: dict) -> dict:
        """解密回调报文里的 resource 字段。"""
        aad = resource.get("associated_data") or ""
        plaintext = AESGCM(self.apiv3_key).decrypt(
            resource["nonce"].encode("utf-8"),
            base64.b64decode(resource["ciphertext"]),
            aad.encode("utf-8") if aad else None,
        )
        return json.loads(plaintext)

    # ---------------- HTTP ----------------

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload is not None else ""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Wechatpay-Serial": self.public_key_id,
            "Authorization": self._build_authorization(method, path, body),
            "User-Agent": "redpacket-backend/1.0",
        }
        try:
            resp = requests.request(
                method, HOST + path,
                data=body.encode("utf-8") if body else None,
                headers=headers, timeout=15,
            )
        except requests.RequestException as e:
            raise WxPayError(0, "NETWORK_ERROR", str(e))

        resp.encoding = "utf-8"
        text = resp.text
        if 200 <= resp.status_code < 300:
            if text and not self.verify_signature(resp.headers, text):
                raise WxPayError(resp.status_code, "RESPONSE_SIGN_INVALID", "微信应答验签失败", text)
            return json.loads(text) if text else {}

        try:
            err = json.loads(text)
        except ValueError:
            err = {}
        raise WxPayError(resp.status_code, err.get("code", "UNKNOWN"), err.get("message", text[:200]), text)

    # ---------------- 业务接口 ----------------

    def apply_authorization(self, out_authorization_no: str, openid: str,
                            user_display_name: str, notify_url: str,
                            client_ip: str | None = None) -> dict:
        """发起免确认收款授权。返回里的 package_info 交给 App 拉起授权页，24小时内有效。"""
        payload = {
            "out_authorization_no": out_authorization_no,
            "appid": self.appid,
            "openid": openid,
            "transfer_scene_id": TRANSFER_SCENE_ID,
            "user_display_name": user_display_name[:32],
            "user_recv_perception": USER_RECV_PERCEPTION,
            "authorization_notify_url": notify_url,
        }
        if client_ip:
            payload["scene_info"] = {"client_ip": client_ip, "device_type": "ANDROID"}
        return self._request("POST", "/v3/fund-app/mch-transfer/user-confirm-authorization", payload)

    def query_authorization(self, out_authorization_no: str) -> dict:
        return self._request(
            "GET",
            f"/v3/fund-app/mch-transfer/user-confirm-authorization/out-authorization-no/{quote(out_authorization_no)}",
        )

    def transfer(self, out_bill_no: str, out_authorization_no: str,
                 amount_fen: int, remark: str = "金币提现") -> dict:
        """
        用户授权后转账。out_bill_no 必须每笔提现固定不变：
        结果不明确时只能用同一个单号重试/查单，换单号可能重复打款。
        """
        payload = {
            "appid": self.appid,
            "out_bill_no": out_bill_no,
            "transfer_scene_id": TRANSFER_SCENE_ID,
            "transfer_amount": amount_fen,
            "transfer_remark": remark[:32],
            "user_recv_perception": USER_RECV_PERCEPTION,
            "transfer_scene_report_infos": SCENE_REPORT_INFOS,
            "out_authorization_no": out_authorization_no,
        }
        return self._request("POST", "/v3/fund-app/mch-transfer/transfer-bills/transfer", payload)

    def query_transfer(self, out_bill_no: str) -> dict:
        return self._request(
            "GET",
            f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{quote(out_bill_no)}",
        )


@lru_cache(maxsize=1)
def get_client() -> WxPayClient:
    return WxPayClient()


if __name__ == "__main__":
    # 配置自检：查一个不存在的授权单。不花钱、不影响任何用户。
    # 返回 404 之类"单据不存在" => 证书、签名、IP白名单都通了
    # 返回 401 SIGN_ERROR       => 证书序列号或私钥不对
    # 返回 403 且提到IP         => 服务器IP没加进安全IP白名单
    try:
        print(get_client().query_authorization("SELFTEST" + secrets.token_hex(4)))
    except WxPayError as e:
        print("微信返回：", e)