package com.tonyfeng.jinshisuda.view;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.FrameLayout;

import com.bytedance.sdk.openadsdk.TTFeedAd;
import com.tonyapp.djxplugin.NativeAdHelper;
import com.tonyfeng.jinshisuda.R;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * 底部抽屉式信息流广告。
 *
 * 由 MyApplication 的 ActivityLifecycleCallbacks 自动挂到每个自家页面上，
 * 业务代码一行都不用写。MainActivity 挂一次就覆盖了底部5个 tab。
 *
 * 节奏：
 * - 进页面 2 秒后加载，加载好从底部滑上来（先给用户看清页面内容的时间）
 * - 点关闭滑下去，10 秒后重新拉一条滑上来
 * - 显示期间每 30 秒换一条（穿山甲要求信息流刷新不低于30秒，调更短会被判无效流量）
 * - 页面不在前台时停掉所有定时器，不在看不见的地方刷广告
 *
 * 底部导航避让：页面里有 bottom_nav 的（就是 MainActivity），
 * 抽屉会自动垫高一个导航栏的高度，不会盖住底部tab。
 */
public final class FeedAdDrawer {

    private static final String TAG = "FeedAdDrawer";

    /** 进页面多久后开始展示 */
    private static final long SHOW_DELAY_MS = 2000;
    /** 用户关闭后多久重新出现 */
    private static final long REOPEN_DELAY_MS = 10000;
    /** 展示期间多久换一条 */
    private static final long REFRESH_MS = 30000;
    /** 加载失败后多久重试 */
    private static final long RETRY_MS = 20000;
    /** 滑入滑出动画时长 */
    private static final long ANIM_MS = 320;

    /** 只给自家页面挂，穿山甲SDK自己的Activity、微信回调页都要排除 */
    private static final String OUR_PACKAGE = "com.tonyfeng.jinshisuda";

    private static final Map<Activity, FeedAdDrawer> INSTANCES = new WeakHashMap<>();

    private final Activity activity;
    private final Handler handler = new Handler(Looper.getMainLooper());

    private View root;
    private FrameLayout adContainer;
    private TTFeedAd currentAd;

    private boolean loading = false;
    private boolean shown = false;
    private boolean userClosed = false;   // 用户主动关过，10秒内不再打扰
    private boolean destroyed = false;
    private boolean suspended = false;  // 被 suspend() 收起了，期间不加载不展示

    private FeedAdDrawer(Activity activity) {
        this.activity = activity;
    }

    // ================= 生命周期入口，MyApplication 调这几个 =================

    public static void attach(Activity activity) {
        if (!shouldAttach(activity)) {
            Log.d(TAG, "跳过挂载: " + (activity == null ? "null" : activity.getClass().getSimpleName()));
            return;
        }
        if (INSTANCES.containsKey(activity)) return;
        Log.d(TAG, "挂载到: " + activity.getClass().getSimpleName());
        FeedAdDrawer drawer = new FeedAdDrawer(activity);
        INSTANCES.put(activity, drawer);
        drawer.install();
    }

    public static void onResume(Activity activity) {
        FeedAdDrawer drawer = INSTANCES.get(activity);
        if (drawer != null) drawer.resume();
    }

    public static void onPause(Activity activity) {
        FeedAdDrawer drawer = INSTANCES.get(activity);
        if (drawer != null) drawer.pause();
    }

    public static void detach(Activity activity) {
        FeedAdDrawer drawer = INSTANCES.remove(activity);
        if (drawer != null) drawer.destroy();
    }

    /**
     * 临时收起抽屉。给"页面里本来就有信息流"的场景用：
     * 比如红包群那个 tab，聊天气泡里已经有信息流了，再叠一条底部抽屉
     * 容易被穿山甲判成广告堆叠，扣量。
     *
     * 在 RedPacketFragment 里这么用：
     *   onHiddenChanged(false) / onResume -> FeedAdDrawer.suspend(getActivity());
     *   切走的时候            -> FeedAdDrawer.resumeFrom(getActivity());
     */
    public static void suspend(Activity activity) {
        FeedAdDrawer drawer = INSTANCES.get(activity);
        if (drawer != null) drawer.suspendSelf();
    }

    /** 跟 suspend 配对，恢复抽屉 */
    public static void resumeFrom(Activity activity) {
        FeedAdDrawer drawer = INSTANCES.get(activity);
        if (drawer != null) drawer.resumeSelf();
    }

    private void suspendSelf() {
        handler.removeCallbacksAndMessages(null);
        suspended = true;
        if (shown) {
            hideDrawer(null);
        }
    }

    private void resumeSelf() {
        if (destroyed) return;
        suspended = false;
        if (!userClosed && !shown) {
            scheduleLoad(SHOW_DELAY_MS);
        }
    }

    private static boolean shouldAttach(Activity activity) {
        if (activity == null) return false;
        String name = activity.getClass().getName();
        // 不是自家的页面（穿山甲激励视频、落地页这些）直接跳过，
        // 总不能在人家全屏广告上面再盖一条信息流
        if (!name.startsWith(OUR_PACKAGE)) return false;
        // 微信回调页是个透明的中转页，停留不到一秒，挂了也是白挂
        if (name.contains("wxapi")) return false;
        return true;
    }

    // ================= 安装 =================

    private void install() {
        // 先尝试挂载，如果 parent 还没布局完成就等布局完成再挂
        if (ensureAttached()) {
            Log.d(TAG, "抽屉已装入 " + activity.getClass().getSimpleName()
                    + "，" + SHOW_DELAY_MS + "ms 后开始加载");
            scheduleLoad(SHOW_DELAY_MS);
        } else {
            // 等 content 完成第一次布局
            View content = activity.findViewById(android.R.id.content);
            if (content != null) {
                content.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() {
                    @Override
                    public void onGlobalLayout() {
                        content.getViewTreeObserver().removeOnGlobalLayoutListener(this);
                        if (destroyed) return;
                        if (ensureAttached()) {
                            Log.d(TAG, "布局完成后挂载成功，" + SHOW_DELAY_MS + "ms 后开始加载");
                            scheduleLoad(SHOW_DELAY_MS);
                        } else {
                            Log.e(TAG, "布局完成后仍挂载失败");
                        }
                    }
                });
            } else {
                Log.e(TAG, "首次挂载失败，且找不到 content");
            }
        }
    }

    /**
     * 确保抽屉挂在界面上，没挂就（重新）挂。
     * 关键改动：必须等 parent 有真实尺寸后再 addView，并且强制校验 isAttachedToWindow。
     */
    private boolean ensureAttached() {
        if (destroyed) return false;
        if (activity.isFinishing() || activity.isDestroyed()) return false;

        // 已经正确挂在窗口上
        if (root != null && root.getParent() != null && root.isAttachedToWindow()) {
            return true;
        }

        ViewGroup parent = resolveParent();
        if (parent == null) {
            Log.e(TAG, "找不到可挂载的容器");
            return false;
        }

        // parent 还没布局完成，先返回 false，让调用方 post 或等 OnGlobalLayout
        if (parent.getWidth() <= 0 || parent.getHeight() <= 0) {
            Log.w(TAG, "parent 尺寸仍为 0，暂不挂载 parent=" + parent.getClass().getSimpleName());
            return false;
        }

        if (root == null) {
            root = LayoutInflater.from(activity)
                    .inflate(R.layout.layout_feed_ad_drawer, parent, false);
            adContainer = root.findViewById(R.id.drawer_ad_container);
            root.findViewById(R.id.drawer_close).setOnClickListener(v -> onUserClose());
            root.setVisibility(View.GONE);
        }

        // 如果之前有残留 parent，先彻底摘掉
        if (root.getParent() instanceof ViewGroup) {
            ((ViewGroup) root.getParent()).removeView(root);
        }

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM);
        lp.bottomMargin = bottomNavHeight();
        parent.addView(root, lp);

        boolean ok = root.getParent() != null;
        Log.d(TAG, "挂载完成: parent=" + parent.getClass().getSimpleName()
                + " parent尺寸=" + parent.getWidth() + "x" + parent.getHeight()
                + " bottomMargin=" + lp.bottomMargin
                + " 挂上了吗=" + ok
                + " attached=" + root.isAttachedToWindow());
        return ok;
    }

    /** 优先挂 content，拿不到就挂 decorView */
    private ViewGroup resolveParent() {
        View content = activity.findViewById(android.R.id.content);
        if (content instanceof ViewGroup) return (ViewGroup) content;
        View decor = activity.getWindow() == null ? null : activity.getWindow().getDecorView();
        if (decor instanceof ViewGroup) {
            Log.d(TAG, "content 拿不到，改挂 decorView");
            return (ViewGroup) decor;
        }
        return null;
    }

    /** 有底部导航的页面（MainActivity）要垫高，别盖住 tab */
    private int bottomNavHeight() {
        View nav = activity.findViewById(R.id.bottom_nav);
        int h = nav == null ? 0 : nav.getHeight();
        if (nav != null && h == 0) {
            // 还没测量出来，按常见高度估一个，之后 showDrawer 里还会再校正
            h = Math.round(56 * activity.getResources().getDisplayMetrics().density);
        }
        return h;
    }

    private void resume() {
        if (destroyed || suspended) return;
        if (shown) {
            scheduleRefresh();          // 已经在显示，继续按30秒换
        } else if (!userClosed) {
            scheduleLoad(SHOW_DELAY_MS);
        }
    }

    private void pause() {
        handler.removeCallbacksAndMessages(null);
    }

    private void destroy() {
        destroyed = true;
        handler.removeCallbacksAndMessages(null);
        if (adContainer != null) adContainer.removeAllViews();
        releaseAdSafely();
        if (root != null && root.getParent() instanceof ViewGroup) {
            ((ViewGroup) root.getParent()).removeView(root);
        }
        root = null;
        adContainer = null;
    }

    // ================= 加载与展示 =================

    private void scheduleLoad(long delay) {
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(this::load, delay);
    }

    private void scheduleRefresh() {
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(this::load, REFRESH_MS);
    }

    private void load() {
        if (destroyed || suspended || loading) return;
        if (activity.isFinishing() || activity.isDestroyed()) return;
        loading = true;
        Log.d(TAG, "发起加载 (" + activity.getClass().getSimpleName() + ")");

        NativeAdHelper.loadBottomBannerAd(activity, new NativeAdHelper.NativeAdCallback() {
            @Override
            public void onAdReady(TTFeedAd feedAd, View adView) {
                handler.post(() -> {
                    loading = false;
                    if (destroyed || adView == null || adContainer == null) return;
                    if (userClosed) return;          // 等待期间用户关了，这条就不展示了

                    // 顺序很重要：先把旧广告的 View 从容器上摘下来，再销毁旧广告对象
                    adContainer.removeAllViews();
                    releaseAdSafely();

                    currentAd = feedAd;

                    // 给广告 View 明确的 LayoutParams（解决尺寸 0x0 的关键）
                    if (adView.getParent() instanceof ViewGroup) {
                        ((ViewGroup) adView.getParent()).removeView(adView);
                    }
                    FrameLayout.LayoutParams adLp = new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT);
                    adContainer.addView(adView, adLp);

                    // 强制重新测量
                    adContainer.requestLayout();
                    if (root != null) root.requestLayout();

                    Log.d(TAG, "广告已塞进容器，adView尺寸=" + adView.getWidth() + "x" + adView.getHeight());

                    showDrawer();
                    scheduleRefresh();
                });
            }

            @Override
            public void onAdFail(String reason) {
                handler.post(() -> {
                    loading = false;
                    Log.d(TAG, "信息流没拿到，稍后重试: " + reason);
                    if (!destroyed && !userClosed) {
                        scheduleLoad(RETRY_MS);
                    }
                });
            }
        });
    }

    /** 从底部滑上来 */
    private void showDrawer() {
        if (root == null) {
            Log.e(TAG, "showDrawer 时 root 是 null");
            return;
        }
        // 展示前再确认一次有没有挂在界面上，掉了就补挂
        if (!ensureAttached()) {
            Log.e(TAG, "展示时仍未挂上，这次先跳过");
            return;
        }

        // 底部导航的高度这时候才量得准，校正一下
        if (root.getLayoutParams() instanceof FrameLayout.LayoutParams) {
            FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) root.getLayoutParams();
            int navH = bottomNavHeight();
            if (navH > 0 && lp.bottomMargin != navH) {
                lp.bottomMargin = navH;
                root.setLayoutParams(lp);
            }
        }

        root.setVisibility(View.VISIBLE);
        Log.d(TAG, "showDrawer: 已设为VISIBLE"
                + " attached=" + root.isAttachedToWindow()
                + " parent=" + (root.getParent() == null ? "null" : root.getParent().getClass().getSimpleName()));

        // 用 root.post 保证在真正 attach 后再做动画
        root.post(() -> {
            if (destroyed || root == null) return;

            int height = root.getHeight();
            Log.d(TAG, "准备滑出: root尺寸=" + root.getWidth() + "x" + height
                    + " 可见性=" + root.getVisibility()
                    + " attached=" + root.isAttachedToWindow()
                    + " 广告子View数=" + (adContainer == null ? -1 : adContainer.getChildCount())
                    + " 广告尺寸=" + adChildSize());

            if (height <= 0) {
                // 高度没量出来，说明广告View没把容器撑起来。
                // 硬做动画也看不见，直接摆到原位，至少让它显示出来。
                Log.w(TAG, "root高度为0，跳过动画直接显示，并再等一帧");
                root.setTranslationY(0);
                shown = true;
                // 再等一帧看看能不能量出高度
                root.postDelayed(() -> {
                    if (root != null && root.getHeight() > 0) {
                        Log.d(TAG, "延迟后高度变为: " + root.getHeight());
                    }
                    logFinalState();
                }, 100);
                return;
            }

            if (!shown) {
                root.setTranslationY(height);    // 先藏到屏幕外
            }
            root.animate().translationY(0).setDuration(ANIM_MS)
                    .withEndAction(this::logFinalState)
                    .start();
            shown = true;
        });
    }

    private String adChildSize() {
        if (adContainer == null || adContainer.getChildCount() == 0) return "无";
        View child = adContainer.getChildAt(0);
        return child.getWidth() + "x" + child.getHeight();
    }

    /** 动画结束后再量一次，这时候尺寸才是最终的 */
    private void logFinalState() {
        if (root == null) return;
        Log.d(TAG, "最终状态: root尺寸=" + root.getWidth() + "x" + root.getHeight()
                + " translationY=" + root.getTranslationY()
                + " 可见性=" + root.getVisibility()
                + " 广告尺寸=" + adChildSize());
    }

    /** 滑下去藏起来 */
    private void hideDrawer(Runnable onEnd) {
        if (root == null) {
            if (onEnd != null) onEnd.run();
            return;
        }
        int height = root.getHeight();
        if (height <= 0) height = 400;
        root.animate().translationY(height).setDuration(ANIM_MS)
                .withEndAction(() -> {
                    if (root != null) root.setVisibility(View.GONE);
                    shown = false;
                    if (onEnd != null) onEnd.run();
                }).start();
    }

    private void onUserClose() {
        userClosed = true;
        handler.removeCallbacksAndMessages(null);
        hideDrawer(() -> {
            // 同样先摘 View 再销毁，顺序不能反
            if (adContainer != null) adContainer.removeAllViews();
            releaseAdSafely();
            // 关掉10秒后重新拉一条
            handler.postDelayed(() -> {
                userClosed = false;
                load();
            }, REOPEN_DELAY_MS);
        });
    }

    /** 安全销毁广告，防止 NativeExpressView 抛异常 */
    private void releaseAdSafely() {
        if (currentAd != null) {
            try {
                currentAd.destroy();
            } catch (Throwable t) {
                Log.w(TAG, "destroy ad 异常（已忽略）", t);
            }
            currentAd = null;
        }
    }
}