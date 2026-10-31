"""
自己托管 APK 下载，不依赖 fir/蒲公英（第三方会插广告劫持下载页）。
apk 放在 app/download/jinshisuda.apk，这个路由带安卓包 MIME 头发出去，
浏览器会当成下载而不是当文本打开。
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["download"])

APK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "download")
APK_NAME = "jinshisuda.apk"


@router.api_route("/download/jinshisuda.apk", methods=["GET", "HEAD"])
def download_apk():
    path = os.path.join(APK_DIR, APK_NAME)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="安装包暂未上传")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename="jinshisuda.apk",
    )