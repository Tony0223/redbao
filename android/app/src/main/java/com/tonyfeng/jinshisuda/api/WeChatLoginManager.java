package com.tonyfeng.jinshisuda.api;

import android.content.Context;
import android.util.Log;
import android.widget.Toast;

import com.tencent.mm.opensdk.modelmsg.SendAuth;
import com.tencent.mm.opensdk.openapi.IWXAPI;
import com.tencent.mm.opensdk.openapi.WXAPIFactory;

public class WeChatLoginManager {

    private static final String TAG = "WeChatLoginManager";
    public static final String WECHAT_APP_ID = "wx259037e95e377617";

    private static IWXAPI api;
    private static boolean isLoggingIn = false;
    private static long lastLoginAttemptTime = 0;
    private static final long LOGIN_DEBOUNCE_MS = 8000; // 8秒内不允许重复发起

    public static void init(Context context) {
        if (api == null) {
            api = WXAPIFactory.createWXAPI(context.getApplicationContext(), WECHAT_APP_ID, false);
            api.registerApp(WECHAT_APP_ID);
        }
    }

    public static boolean isWeChatInstalled() {
        return api != null && api.isWXAppInstalled();
    }

    /**
     * 只负责"发起微信授权请求"。
     * 拿到 code 之后的 code换token、存本地，全部挪到 WXEntryActivity 里当场完成，
     * 不再靠这个类的静态回调传递——那样跳回来时进程若被回收，链路就断了。
     */
    public static void login(Context context) {
        long now = System.currentTimeMillis();
        Log.d(TAG, "login() 被调用, isLoggingIn=" + isLoggingIn + ", 距上次=" + (now - lastLoginAttemptTime) + "ms");

        if (api == null) {
            init(context);
        }

        if (!isWeChatInstalled()) {
            Toast.makeText(context.getApplicationContext(), "未安装微信，无法登录", Toast.LENGTH_SHORT).show();
            return;
        }

        // 双重防护：锁 + 时间防抖
        if (isLoggingIn || (now - lastLoginAttemptTime < LOGIN_DEBOUNCE_MS)) {
            Log.w(TAG, "忽略重复登录请求（锁或防抖）");
            return;
        }

        isLoggingIn = true;
        lastLoginAttemptTime = now;

        SendAuth.Req req = new SendAuth.Req();
        req.scope = "snsapi_userinfo";
        req.state = "redpacket_login_" + now;

        boolean sent = api.sendReq(req);
        Log.d(TAG, "sendReq 结果 = " + sent);

        if (!sent) {
            isLoggingIn = false;
            Toast.makeText(context.getApplicationContext(), "发起微信登录失败", Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * WXEntryActivity 收到授权结果后调用，释放登录锁，允许下次登录。
     */
    public static void forceResetLoginState() {
        isLoggingIn = false;
        lastLoginAttemptTime = 0;
        Log.d(TAG, ">>> 重置登录锁");
    }
}