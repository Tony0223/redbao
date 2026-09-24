package com.tonyfeng.jinshisuda.api;

import android.content.ClipDescription;
import android.content.ClipboardManager;
import android.content.Context;
import android.util.Log;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 待绑定的邀请码。
 *
 * 流程：好友打开落地页点下载 → 网页把"邀请码口令"写进剪贴板 → 新用户装好首次打开App
 * → 这里从剪贴板读出邀请码存起来 → 微信登录注册时带给服务端，自动绑定邀请关系。
 *
 * 只对没登录过的新用户生效；已经登录过的老用户不读剪贴板（邀请关系只在注册时绑定一次）。
 */
public class InviteCodeStore {

    private static final String TAG = "InviteCodeStore";
    private static final String PREFS = "invite_code";
    private static final String KEY_PENDING = "pending_code";
    private static final String KEY_CLIPBOARD_CHECKED = "clipboard_checked";

    /** 口令格式：金石速答邀请码:ABC123 —— 要和落地页写进剪贴板的内容保持一致 */
    private static final Pattern TOKEN = Pattern.compile("邀请码[:：]\\s*([A-Za-z0-9]{4,16})");

    /**
     * 首次启动时调一次：没登录过就尝试从剪贴板读邀请码。
     * Android 10 以上只有 App 在前台且有焦点时才能读剪贴板，所以要在界面可见后调用。
     */
    public static void tryReadFromClipboard(Context context) {
        Context app = context.getApplicationContext();
        if (UserManager.isLoggedIn(app)) return;                 // 老用户不处理
        if (prefs(app).getBoolean(KEY_CLIPBOARD_CHECKED, false)) return;  // 只读一次

        prefs(app).edit().putBoolean(KEY_CLIPBOARD_CHECKED, true).apply();
        try {
            ClipboardManager cm = (ClipboardManager) app.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm == null || !cm.hasPrimaryClip()) return;
            ClipDescription desc = cm.getPrimaryClipDescription();
            if (desc == null || !desc.hasMimeType(ClipDescription.MIMETYPE_TEXT_PLAIN)) return;
            CharSequence text = cm.getPrimaryClip().getItemAt(0).coerceToText(app);
            if (text == null) return;

            Matcher m = TOKEN.matcher(text.toString());
            if (m.find()) {
                String code = m.group(1);
                prefs(app).edit().putString(KEY_PENDING, code).apply();
                Log.d(TAG, "从剪贴板读到邀请码: " + code);
            }
        } catch (Exception e) {
            Log.w(TAG, "读剪贴板失败: " + e.getMessage());
        }
    }

    /** 取出待绑定的邀请码，没有就返回 null */
    public static String peek(Context context) {
        return prefs(context).getString(KEY_PENDING, null);
    }

    /** 登录成功后调用，用掉就清掉 */
    public static void consume(Context context) {
        prefs(context).edit().remove(KEY_PENDING).apply();
    }

    private static android.content.SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}