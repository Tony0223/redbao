"""
邀请落地页：https://hongbao.zero-start.online/i/{邀请码}

好友打开这个页面 → 点"立即下载" → 网页把"邀请码口令"写进剪贴板 → 跳下载地址
→ 新用户装好首次打开 App，从剪贴板读出邀请码 → 微信登录注册时自动绑定邀请关系。

口令格式要和 App 端 InviteCodeStore 的解析规则保持一致：金石速答邀请码:ABC123
下载地址在后台"App/客服设置 → 下载链接"里配，没配就提示"开发中"。
"""
import html

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import crud, models
from app.database import get_db

router = APIRouter(tags=["landing"])

APP_NAME = "金石速答"
TOKEN_PREFIX = f"{APP_NAME}邀请码:"


def _page(invite_code: str, download_url: str, valid: bool) -> str:
    code = html.escape(invite_code)
    token = html.escape(TOKEN_PREFIX + invite_code)
    url_js = html.escape(download_url, quote=True)

    if not valid:
        header = f'<div class="code">邀请码不存在</div><div class="tip">请向好友重新获取邀请链接</div>'
        button = f'<a class="btn disabled">邀请码无效</a>'
    else:
        header = (f'<div class="code">我的邀请码：<b>{code}</b>'
                  f'<span class="copy" onclick="copyCode()">复制</span></div>')
        button = '<a class="btn" onclick="download()">立即下载</a>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>{APP_NAME} - 邀请好友赚取收益</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif;
         background:linear-gradient(180deg,#F5333F 0%,#FF6B4A 32%,#F6F6F6 60%,#F6F6F6 100%);
         min-height:100vh; display:flex; flex-direction:column; }}
  .top {{ padding:28px 20px 40px; color:#fff; }}
  .applogo {{ width:72px; height:72px; border-radius:16px; margin-bottom:14px;
             background:#fff; box-shadow:0 4px 12px rgba(0,0,0,.15); display:block; }}
  .name {{ font-size:22px; font-weight:700; margin-bottom:10px; }}
  .code {{ font-size:17px; display:flex; align-items:center; flex-wrap:wrap; gap:8px; }}
  .code b {{ font-size:20px; letter-spacing:1px; }}
  .copy {{ background:#fff; color:#F5333F; border-radius:20px; padding:4px 16px;
           font-size:14px; font-weight:600; cursor:pointer; }}
  .tip {{ font-size:14px; margin-top:8px; opacity:.9; }}
  .card {{ margin:0 20px; background:#fff; border-radius:16px; padding:24px 20px;
           box-shadow:0 6px 20px rgba(0,0,0,.08); }}
  .card h2 {{ font-size:17px; color:#222; margin-bottom:14px; }}
  .card li {{ list-style:none; font-size:15px; color:#555; line-height:2; }}
  .card li span {{ display:inline-block; width:22px; height:22px; line-height:22px;
                   text-align:center; background:#FFE9D2; color:#D9480F;
                   border-radius:50%; font-size:13px; margin-right:8px; }}
  .bottom {{ margin-top:auto; padding:28px 20px 40px; text-align:center; }}
  .btn {{ display:block; background:linear-gradient(180deg,#FFD84D,#FFAA00);
          color:#8A4B00; font-size:22px; font-weight:800; padding:16px;
          border-radius:40px; box-shadow:0 6px 16px rgba(255,170,0,.4); cursor:pointer; }}
  .btn.disabled {{ background:#ddd; color:#888; box-shadow:none; }}
  .note {{ font-size:12px; color:#999; margin-top:14px; line-height:1.8; }}
  .toast {{ position:fixed; left:50%; top:50%; transform:translate(-50%,-50%);
            background:rgba(0,0,0,.8); color:#fff; padding:12px 22px; border-radius:8px;
            font-size:15px; display:none; z-index:99; }}
</style>
</head>
<body>
  <div class="top">
    <img class="applogo" src="/static/app_icon.png" alt="{APP_NAME}">
    <div class="name">{APP_NAME}</div>
    {header}
  </div>

  <div class="card">
    <h2>三步开始赚钱</h2>
    <ul>
      <li><span>1</span>下载并安装 App</li>
      <li><span>2</span>微信登录，自动绑定邀请关系</li>
      <li><span>3</span>看广告领金币，提现到微信零钱</li>
    </ul>
  </div>

  <div class="bottom">
    {button}
    <div class="note">安装后打开 App 用微信登录，即可自动绑定<br>如未自动绑定，可在 App 内手动填写上方邀请码</div>
  </div>

  <div class="toast" id="toast"></div>

<script>
var TOKEN = "{token}";
var DOWNLOAD_URL = "{url_js}";

function toast(msg) {{
  var t = document.getElementById('toast');
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(function () {{ t.style.display = 'none'; }}, 2000);
}}

function copyText(text) {{
  var input = document.createElement('textarea');
  input.value = text;
  input.style.position = 'fixed';
  input.style.opacity = '0';
  document.body.appendChild(input);
  input.select();
  input.setSelectionRange(0, text.length);
  var ok = false;
  try {{ ok = document.execCommand('copy'); }} catch (e) {{ ok = false; }}
  document.body.removeChild(input);
  return ok;
}}

function copyCode() {{
  toast(copyText(TOKEN) ? '邀请码已复制' : '复制失败，请手动记下邀请码');
}}

function download() {{
  copyText(TOKEN);   // 先把口令写进剪贴板，App 首次启动会读它自动绑定
  if (!DOWNLOAD_URL) {{
    toast('下载功能开发中，敬请期待');
    return;
  }}
  setTimeout(function () {{ location.href = DOWNLOAD_URL; }}, 300);
}}
</script>
</body>
</html>"""


@router.get("/i/{invite_code}", response_class=HTMLResponse)
def invite_landing(invite_code: str, db: Session = Depends(get_db)):
    invite_code = (invite_code or "").strip()[:16]
    inviter = crud.get_user_by_invite_code(db, invite_code) if invite_code else None
    # 下载地址：邀请落地页专用，后台“App/客服设置 → App下载地址”可配，默认 fir.im 分发
    download_url = crud.get_setting(db, "app_download_url", "https://fir.xcxwo.com/sd9efqvp").strip()
    return HTMLResponse(content=_page(invite_code, download_url, inviter is not None))