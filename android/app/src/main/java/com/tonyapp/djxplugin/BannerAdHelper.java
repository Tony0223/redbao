package com.tonyapp.djxplugin;

import android.app.Activity;
import android.util.Log;
import android.view.View;

import com.bytedance.sdk.openadsdk.AdSlot;
import com.bytedance.sdk.openadsdk.TTAdNative;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.TTNativeExpressAd;
import com.bytedance.sdk.openadsdk.mediation.ad.MediationAdSlot;

import java.util.List;

/**
 * 首页 Banner 广告（模板渲染）。
 * 用来盖在首页橙色横幅上：广告拉到并渲染成功就展示，拿不到就留橙色横幅兜底。
 */
public class BannerAdHelper {

    private static final String TAG = "BannerAdHelper";

    /** app banner 广告位 */
    private static final String BANNER_CODE_ID = "104592836";

    public interface BannerCallback {
        void onAdReady(TTNativeExpressAd ad, View adView);
        void onAdFail(String reason);
    }

    /**
     * widthDp 传横幅实际宽度（dp），heightDp 传 0 让服务端按宽度等比出高度。
     */
    public static void load(Activity activity, float widthDp, float heightDp, BannerCallback callback) {
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            if (callback != null) callback.onAdFail("activity 不可用");
            return;
        }

        AdSlot adSlot = new AdSlot.Builder()
                .setCodeId(BANNER_CODE_ID)
                .setExpressViewAcceptedSize(widthDp, heightDp)
                .setAdCount(1)
                .setMediationAdSlot(
                        new MediationAdSlot.Builder()
                                .setMuted(true)
                                .build())
                .build();

        TTAdNative adNative = TTAdSdk.getAdManager().createAdNative(activity);
        adNative.loadBannerExpressAd(adSlot, new TTAdNative.NativeExpressAdListener() {
            @Override
            public void onError(int code, String message) {
                Log.e(TAG, "Banner加载失败: " + code + " " + message);
                if (callback != null) callback.onAdFail(message);
            }

            @Override
            public void onNativeExpressAdLoad(List<TTNativeExpressAd> ads) {
                if (ads == null || ads.isEmpty()) {
                    if (callback != null) callback.onAdFail("无广告返回");
                    return;
                }
                TTNativeExpressAd ad = ads.get(0);
                ad.setExpressInteractionListener(new TTNativeExpressAd.ExpressAdInteractionListener() {
                    @Override
                    public void onAdClicked(View view, int type) {
                    }

                    @Override
                    public void onAdShow(View view, int type) {
                    }

                    @Override
                    public void onRenderFail(View view, String msg, int code) {
                        Log.e(TAG, "Banner渲染失败: " + code + " " + msg);
                        if (callback != null) callback.onAdFail(msg);
                    }

                    @Override
                    public void onRenderSuccess(View view, float width, float height) {
                        View adView = view != null ? view : ad.getExpressAdView();
                        if (adView == null) {
                            if (callback != null) callback.onAdFail("广告View为空");
                            return;
                        }
                        if (callback != null) callback.onAdReady(ad, adView);
                    }
                });
                ad.render();
            }
        });
    }
}
