package com.tonyfeng.jinshisuda.api;

import android.content.Context;
import android.util.Log;

import org.json.JSONObject;

public class UserManager {

    private static final String TAG = "UserManager";
    private static final String PREFS_NAME = "redpacket_user";
    private static final String KEY_USER_ID = "user_id";
    private static final String KEY_TOKEN = "token";

    public static int getUserId(Context context) {
        return context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getInt(KEY_USER_ID, -1);
    }

    public static String getToken(Context context) {
        return context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(KEY_TOKEN, null);
    }

    public static boolean isLoggedIn(Context context) {
        return getUserId(context) != -1 && getToken(context) != null;
    }

    /**
     * 存登录状态。改成 public：现在 code换token 在 WXEntryActivity 里完成，需要它来落地。
     */
    public static void saveLogin(Context context, int userId, String token) {
        context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putInt(KEY_USER_ID, userId)
                .putString(KEY_TOKEN, token)
                .apply();
    }

    private static void clearLogin(Context context) {
        context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(KEY_USER_ID)
                .remove(KEY_TOKEN)
                .apply();
    }

    /**
     * 需要登录才能做的操作，调用前用它兜底：
     * - 已登录：直接执行 onReady。
     * - 未登录：拉起微信授权。注意——授权和换token 会在 WXEntryActivity 里独立走完，
     *   本次【不保证】回调 onReady（因为登录过程中进程可能被系统回收，续跑不可靠）。
     *   正确姿势：发起操作的界面在 onResume 里用 isLoggedIn() 兜底刷新，
     *   用户登录完回到界面后重新点一次操作即可。
     */
    public static void ensureLoggedIn(Context context, Runnable onReady) {
        if (isLoggedIn(context)) {
            onReady.run();
            return;
        }
        Log.d(TAG, "未登录，发起微信登录");
        WeChatLoginManager.login(context);
    }

    public interface LogoutCallback {
        void onDone();
    }

    /**
     * 退出登录：先尝试通知服务端作废token（失败也无所谓），本地登录状态一定会清掉。
     */
    public static void logout(Context context, LogoutCallback callback) {
        String token = getToken(context);
        if (token == null) {
            clearLogin(context);
            callback.onDone();
            return;
        }
        ApiClient.logout(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                clearLogin(context);
                callback.onDone();
            }

            @Override
            public void onError(String message) {
                Log.e(TAG, "退出登录时通知服务端失败(不影响本地退出): " + message);
                clearLogin(context);
                callback.onDone();
            }
        });
    }
}