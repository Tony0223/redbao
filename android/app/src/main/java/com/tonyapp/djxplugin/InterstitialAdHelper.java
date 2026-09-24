package com.tonyapp.djxplugin;

import android.app.Activity;
import android.util.Log;

import com.bytedance.sdk.openadsdk.AdSlot;
import com.bytedance.sdk.openadsdk.TTAdNative;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.TTFullScreenVideoAd;

/**
 * 新插屏广告。用在"签到成功、结果弹窗关掉之后"这种时机，
 * 不跟按钮叠在一起，避免诱导点击（穿山甲判违规会扣量封号）。
 *
 * 用法：InterstitialAdHelper.show(activity, null);
 */
public class InterstitialAdHelper {

    private static final String TAG = "InterstitialAdHelper";

    /**
     * 半屏插全屏代码位（穿山甲后台“广告铺开大小”设为半屏，全站插屏统一用这个）。
     * 半屏由后台配置决定，SDK 会渲染成一个不铺满屏幕的卡片，右上角带自带的✕。
     */
    private static final String AD_SLOT_ID = "104590993";

    public interface InterstitialCallback {
        /** 广告关闭或加载失败都会回调，不阻塞主流程 */
        void onFinish();
    }

    public static void show(Activity activity, InterstitialCallback callback) {
        if (activity == null || activity.isFinishing()) {
            if (callback != null) callback.onFinish();
            return;
        }

        AdSlot adSlot = new AdSlot.Builder()
                .setCodeId(AD_SLOT_ID)
                .setOrientation(TTAdConstantAdapter.VERTICAL)
                .build();

        TTAdNative adNative = TTAdSdk.getAdManager().createAdNative(activity);
        adNative.loadFullScreenVideoAd(adSlot, new TTAdNative.FullScreenVideoAdListener() {
            @Override
            public void onError(int code, String message) {
                Log.e(TAG, "插屏加载失败: " + code + " " + message);
                if (callback != null) callback.onFinish();
            }

            @Override
            public void onFullScreenVideoAdLoad(TTFullScreenVideoAd ad) {
                ad.setFullScreenVideoAdInteractionListener(
                        new TTFullScreenVideoAd.FullScreenVideoAdInteractionListener() {
                            @Override
                            public void onAdShow() {
                            }

                            @Override
                            public void onAdVideoBarClick() {
                            }

                            @Override
                            public void onAdClose() {
                                if (callback != null) callback.onFinish();
                            }

                            @Override
                            public void onVideoComplete() {
                            }

                            @Override
                            public void onSkippedVideo() {
                            }
                        });
                if (!activity.isFinishing()) {
                    ad.showFullScreenVideoAd(activity);
                } else if (callback != null) {
                    callback.onFinish();
                }
            }

            @Override
            public void onFullScreenVideoCached() {
            }

            @Override
            public void onFullScreenVideoCached(TTFullScreenVideoAd ad) {
            }
        });
    }

    /** 竖屏常量，抽出来避免不同SDK版本常量类名不一致 */
    private static class TTAdConstantAdapter {
        static final int VERTICAL = 1;
    }
}