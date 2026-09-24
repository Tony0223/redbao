package com.tonyfeng.jinshisuda.view;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.tonyapp.djxplugin.InterstitialAdHelper;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * 全站插屏调度器。
 *
 * 产品要求：主页面 + 每个子页面都要有插屏，右上角可关闭，关闭之后等 20 秒再出现。
 *
 * 插屏本体用穿山甲“半屏插全屏”代码位（{@link InterstitialAdHelper}，104590993），
 * 半屏卡片和右上角的✕都是 SDK 按后台配置渲染的。这个类只负责“节奏”：
 * - 进页面 {@link #FIRST_SHOW_DELAY_MS} 后弹第一次；
 * - 广告关闭（或加载失败）后 {@link #REOPEN_DELAY_MS}=20 秒再弹一次，循环往复；
 * - 页面不在前台时停掉计时，不在看不见的地方弹。
 *
 * 挂载方式跟 FeedAdDrawer 一样，由 MyApplication 的 ActivityLifecycleCallbacks
 * 自动挂到每个自家页面，业务代码不用改。
 */
public final class InterstitialAdManager {

    private static final String TAG = "InterstitialAdManager";

    /** 进页面多久后弹第一次 */
    private static final long FIRST_SHOW_DELAY_MS = 3000;
    /** 关闭（或失败）后多久再弹 */
    private static final long REOPEN_DELAY_MS = 20000;

    /** 只给自家页面挂，穿山甲SDK自己的Activity、微信回调页要排除 */
    private static final String OUR_PACKAGE = "com.tonyfeng.jinshisuda";

    private static final Map<Activity, InterstitialAdManager> INSTANCES = new WeakHashMap<>();

    private final Activity activity;
    private final Handler handler = new Handler(Looper.getMainLooper());

    private boolean destroyed = false;
    private boolean waiting = false;       // 已排了一次待弹的计时
    private boolean adInProgress = false;  // 插屏正在加载/展示中

    private InterstitialAdManager(Activity activity) {
        this.activity = activity;
    }

    // ================= 生命周期入口，MyApplication 调这几个 =================

    public static void attach(Activity activity) {
        if (!shouldAttach(activity)) return;
        if (INSTANCES.containsKey(activity)) return;
        Log.d(TAG, "挂载插屏调度到: " + activity.getClass().getSimpleName());
        INSTANCES.put(activity, new InterstitialAdManager(activity));
    }

    public static void onResume(Activity activity) {
        InterstitialAdManager m = INSTANCES.get(activity);
        if (m != null) m.resume();
    }

    public static void onPause(Activity activity) {
        InterstitialAdManager m = INSTANCES.get(activity);
        if (m != null) m.pause();
    }

    public static void detach(Activity activity) {
        InterstitialAdManager m = INSTANCES.remove(activity);
        if (m != null) m.destroy();
    }

    private static boolean shouldAttach(Activity activity) {
        if (activity == null) return false;
        String name = activity.getClass().getName();
        // 不是自家的页面（穿山甲广告页、落地页这些）直接跳过
        if (!name.startsWith(OUR_PACKAGE)) return false;
        // 微信回调页是个透明中转页，停留不到一秒，挂了也白挂
        if (name.contains("wxapi")) return false;
        return true;
    }

    // ================= 节奏控制 =================

    private void resume() {
        // 广告正在放（此时是从广告页返回）或已经排好了下一次，就不重复安排
        if (destroyed || adInProgress || waiting) return;
        scheduleShow(FIRST_SHOW_DELAY_MS);
    }

    private void pause() {
        // 广告正在展示时的 pause 是因为切到了穿山甲广告页，不能取消，
        // 否则关闭回调后就接不上 20 秒再弹了
        if (adInProgress) return;
        handler.removeCallbacksAndMessages(null);
        waiting = false;
    }

    private void destroy() {
        destroyed = true;
        handler.removeCallbacksAndMessages(null);
    }

    private void scheduleShow(long delay) {
        if (destroyed) return;
        handler.removeCallbacksAndMessages(null);
        waiting = true;
        handler.postDelayed(this::show, delay);
    }

    private void show() {
        waiting = false;
        if (destroyed || activity.isFinishing() || activity.isDestroyed()) return;
        adInProgress = true;
        Log.d(TAG, "弹插屏 (" + activity.getClass().getSimpleName() + ")");
        InterstitialAdHelper.show(activity, () -> {
            // 关闭或加载失败都会回调到这里，隔 20 秒再弹一次
            adInProgress = false;
            if (destroyed) return;
            scheduleShow(REOPEN_DELAY_MS);
        });
    }
}
