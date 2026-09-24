package com.tonyapp.djxplugin;

import android.app.Activity;
import android.util.Log;
import android.view.View;

import com.bytedance.sdk.openadsdk.AdSlot;
import com.bytedance.sdk.openadsdk.TTAdNative;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.TTFeedAd;
import com.bytedance.sdk.openadsdk.TTNativeAd;
import com.bytedance.sdk.openadsdk.mediation.ad.MediationAdSlot;

import java.util.List;

public class NativeAdHelper {

    private static final String TAG = "NativeAdHelper";

    /** 红包群聊天列表信息流广告位 */
    private static final String FEED_AD_CODE_ID = "104505022";
    /** 福利页信息流广告位 */
    private static final String FEED_AD_CODE_ID_WELFARE = "104580163";

    /**
     * 模板整体尺寸（尤其视频/图片高度）跟宽度成比例：
     * 宽度给小一点，整个卡片就按比例缩小，高度自然矮，不用裁切。
     * 红包群聊天气泡用 240dp，福利页卡片稍宽一点用 300dp。
     */
    private static final float WIDTH_CHAT_BUBBLE_DP = 240f;
    private static final float WIDTH_WELFARE_DP = 300f;

    public interface NativeAdCallback {
        void onAdReady(TTFeedAd feedAd, View adView);
        void onAdFail(String reason);
    }

    /** 红包群聊天列表用 */
    public static void loadFeedAd(Activity activity, NativeAdCallback callback) {
        loadFeedAd(activity, FEED_AD_CODE_ID, WIDTH_CHAT_BUBBLE_DP, 0f, callback);
    }

    /** 福利页用 */
    public static void loadBottomBannerAd(Activity activity, NativeAdCallback callback) {
        loadFeedAd(activity, FEED_AD_CODE_ID_WELFARE, WIDTH_WELFARE_DP, 0f, callback);
    }

    /**
     * 指定广告位和模板尺寸加载信息流。
     * heightDp 传 0 表示高度由服务端按宽度比例决定，这样内容完整、不用裁切。
     */
    public static void loadFeedAd(Activity activity, String codeId, float widthDp, float heightDp,
                                  NativeAdCallback callback) {
        AdSlot adSlot = new AdSlot.Builder()
                .setCodeId(codeId)
                .setExpressViewAcceptedSize(widthDp, heightDp) // 关键：告诉服务端按这个宽度渲染模板
                .setAdCount(1)
                .setMediationAdSlot(
                        new MediationAdSlot.Builder()
                                .setMuted(false)
                                .build()
                )
                .build();

        TTAdNative adNativeLoader = TTAdSdk.getAdManager().createAdNative(activity);

        adNativeLoader.loadFeedAd(adSlot, new TTAdNative.FeedAdListener() {
            @Override
            public void onError(int errorCode, String errorMsg) {
                Log.e(TAG, "信息流广告加载失败: code=" + errorCode + " msg=" + errorMsg);
                if (callback != null) {
                    callback.onAdFail("加载失败: " + errorMsg);
                }
            }

            @Override
            public void onFeedAdLoad(List<TTFeedAd> list) {
                if (list == null || list.isEmpty()) {
                    Log.e(TAG, "信息流广告无填充");
                    if (callback != null) {
                        callback.onAdFail("无广告返回");
                    }
                    return;
                }
                TTFeedAd feedAd = list.get(0);
                Log.d(TAG, "信息流广告加载成功，开始渲染");

                feedAd.setExpressRenderListener(new TTNativeAd.ExpressRenderListener() {
                    @Override
                    public void onRenderSuccess(View view, float v, float v1, boolean b) {
                        View adView = view != null ? view : feedAd.getAdView();
                        if (adView == null) {
                            if (callback != null) {
                                callback.onAdFail("广告View为空");
                            }
                            return;
                        }
                        Log.d(TAG, "信息流广告渲染成功");
                        if (callback != null) {
                            callback.onAdReady(feedAd, adView);
                        }
                    }
                });

                feedAd.render(); // 触发真正的渲染，渲染完才会回调onRenderSuccess
            }
        });
    }
}