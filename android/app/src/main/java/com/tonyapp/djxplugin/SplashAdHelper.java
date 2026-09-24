package com.tonyapp.djxplugin;

import android.app.Activity;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;

import com.bytedance.sdk.openadsdk.AdSlot;
import com.bytedance.sdk.openadsdk.CSJAdError;
import com.bytedance.sdk.openadsdk.CSJSplashAd;
import com.bytedance.sdk.openadsdk.TTAdNative;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.mediation.ad.MediationAdSlot;

/**
 * 开屏广告。登录成功后、进首页前展示一次；广告自带倒计时/跳过，
 * 倒计时结束或用户跳过/点击后回调 onFinish()，由调用方跳首页。
 *
 * 加载失败、无填充、渲染失败都会回调 onFinish()，绝不卡在开屏页。
 */
public class SplashAdHelper {

    private static final String TAG = "SplashAdHelper";

    /** app开屏广告代码位 */
    private static final String SPLASH_CODE_ID = "104592999";

    /** 拉取超时，超过就走 onFinish 直接进首页，别让用户等 */
    private static final int LOAD_TIMEOUT_MS = 3500;

    public interface SplashCallback {
        /** 广告结束（关闭/跳过/失败/超时）都回调，调用方在这里进首页 */
        void onFinish();
    }

    public static void loadAndShow(Activity activity, ViewGroup container, SplashCallback callback) {
        if (activity == null || activity.isFinishing() || activity.isDestroyed() || container == null) {
            if (callback != null) callback.onFinish();
            return;
        }

        DisplayMetrics dm = activity.getResources().getDisplayMetrics();
        int widthPx = dm.widthPixels;
        int heightPx = dm.heightPixels;
        float density = dm.density <= 0 ? 1f : dm.density;

        AdSlot adSlot = new AdSlot.Builder()
                .setCodeId(SPLASH_CODE_ID)
                .setImageAcceptedSize(widthPx, heightPx)              // 非模板开屏按像素
                .setExpressViewAcceptedSize(widthPx / density, heightPx / density) // 模板开屏按dp
                .setMediationAdSlot(
                        new MediationAdSlot.Builder()
                                .setMuted(true)   // 开屏静音，别一进来就外放
                                .build())
                .build();

        TTAdNative adNative = TTAdSdk.getAdManager().createAdNative(activity);
        adNative.loadSplashAd(adSlot, new TTAdNative.CSJSplashAdListener() {
            @Override
            public void onSplashLoadSuccess(CSJSplashAd ad) {
                // 等 onSplashRenderSuccess 再展示
            }

            @Override
            public void onSplashLoadFail(CSJAdError error) {
                Log.e(TAG, "开屏加载失败: " + (error == null ? "" : error.getCode() + " " + error.getMsg()));
                finish(callback);
            }

            @Override
            public void onSplashRenderSuccess(CSJSplashAd ad) {
                if (ad == null || activity.isFinishing() || activity.isDestroyed()) {
                    finish(callback);
                    return;
                }
                ad.setSplashAdListener(new CSJSplashAd.SplashAdListener() {
                    @Override
                    public void onSplashAdShow(CSJSplashAd a) {
                    }

                    @Override
                    public void onSplashAdClick(CSJSplashAd a) {
                    }

                    @Override
                    public void onSplashAdClose(CSJSplashAd a, int closeType) {
                        // 倒计时结束、点跳过、点广告返回，都走这里进首页
                        finish(callback);
                    }
                });
                View splashView = ad.getSplashView();
                if (splashView == null) {
                    finish(callback);
                    return;
                }
                container.removeAllViews();
                if (splashView.getParent() instanceof ViewGroup) {
                    ((ViewGroup) splashView.getParent()).removeView(splashView);
                }
                container.addView(splashView,
                        new ViewGroup.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.MATCH_PARENT));
            }

            @Override
            public void onSplashRenderFail(CSJSplashAd ad, CSJAdError error) {
                Log.e(TAG, "开屏渲染失败: " + (error == null ? "" : error.getCode() + " " + error.getMsg()));
                finish(callback);
            }
        }, LOAD_TIMEOUT_MS);
    }

    private static void finish(SplashCallback callback) {
        if (callback != null) callback.onFinish();
    }
}
