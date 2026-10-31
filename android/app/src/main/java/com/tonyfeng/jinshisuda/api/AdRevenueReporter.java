package com.tonyfeng.jinshisuda.api;

import android.content.Context;
import android.util.Log;

import com.bytedance.sdk.openadsdk.CSJSplashAd;
import com.bytedance.sdk.openadsdk.TTFeedAd;
import com.bytedance.sdk.openadsdk.TTFullScreenVideoAd;
import com.bytedance.sdk.openadsdk.TTNativeExpressAd;
import com.bytedance.sdk.openadsdk.TTRewardVideoAd;

import org.json.JSONObject;

import java.util.LinkedHashSet;
import java.util.Iterator;
import java.util.Set;

/**
 * 广告展示后上报真实 eCPM，后端据此给代理按收益分成。
 *
 * 按 GroMore 官方文档：只能在【展示之后】调用(onAdShow / onSplashAdShow)，
 * 通过 广告对象.getMediationManager().getShowEcpm() 取 MediationAdEcpmInfo，
 * getEcpm() 单位是分/千次；兜底代码位 eCPM 为 0，这种不上报。
 *
 * - 静默上报：失败不提示、不重试，绝不影响广告展示和用户使用；
 * - 按 requestId 去重：文档提示部分 ADN 会多次回调展示，避免重复记收益；
 * - 未登录不上报(后端按 token 识别用户)。
 */
public final class AdRevenueReporter {

    private static final String TAG = "AdRevenueReporter";
    private static final int DEDUP_SIZE = 200;
    private static final Set<String> REPORTED = new LinkedHashSet<>();

    private AdRevenueReporter() {
    }

    public static void reportReward(Context context, TTRewardVideoAd ad) {
        String ecpm = null, sdk = null, reqId = null;
        try {
            ecpm = ad.getMediationManager().getShowEcpm().getEcpm();
            sdk = ad.getMediationManager().getShowEcpm().getSdkName();
            reqId = ad.getMediationManager().getShowEcpm().getRequestId();
        } catch (Throwable t) {
            Log.w(TAG, "激励视频取eCPM失败: " + t);
        }
        report(context, "reward_video", ecpm, sdk, reqId);
    }

    public static void reportFullScreen(Context context, TTFullScreenVideoAd ad) {
        String ecpm = null, sdk = null, reqId = null;
        try {
            ecpm = ad.getMediationManager().getShowEcpm().getEcpm();
            sdk = ad.getMediationManager().getShowEcpm().getSdkName();
            reqId = ad.getMediationManager().getShowEcpm().getRequestId();
        } catch (Throwable t) {
            Log.w(TAG, "插全屏取eCPM失败: " + t);
        }
        report(context, "fullscreen", ecpm, sdk, reqId);
    }

    public static void reportFeed(Context context, TTFeedAd ad) {
        String ecpm = null, sdk = null, reqId = null;
        try {
            ecpm = ad.getMediationManager().getShowEcpm().getEcpm();
            sdk = ad.getMediationManager().getShowEcpm().getSdkName();
            reqId = ad.getMediationManager().getShowEcpm().getRequestId();
        } catch (Throwable t) {
            Log.w(TAG, "信息流取eCPM失败: " + t);
        }
        report(context, "feed", ecpm, sdk, reqId);
    }

    public static void reportBanner(Context context, TTNativeExpressAd ad) {
        String ecpm = null, sdk = null, reqId = null;
        try {
            ecpm = ad.getMediationManager().getShowEcpm().getEcpm();
            sdk = ad.getMediationManager().getShowEcpm().getSdkName();
            reqId = ad.getMediationManager().getShowEcpm().getRequestId();
        } catch (Throwable t) {
            Log.w(TAG, "Banner取eCPM失败: " + t);
        }
        report(context, "banner", ecpm, sdk, reqId);
    }

    public static void reportSplash(Context context, CSJSplashAd ad) {
        String ecpm = null, sdk = null, reqId = null;
        try {
            ecpm = ad.getMediationManager().getShowEcpm().getEcpm();
            sdk = ad.getMediationManager().getShowEcpm().getSdkName();
            reqId = ad.getMediationManager().getShowEcpm().getRequestId();
        } catch (Throwable t) {
            Log.w(TAG, "开屏取eCPM失败: " + t);
        }
        report(context, "splash", ecpm, sdk, reqId);
    }

    private static void report(Context context, String adType, String ecpm, String sdk, String reqId) {
        try {
            if (context == null || ecpm == null) return;
            double value;
            try {
                value = Double.parseDouble(ecpm.trim());
            } catch (NumberFormatException e) {
                return;
            }
            if (!(value > 0)) {
                return;   // 兜底代码位为0、或展示前取的，不上报
            }
            if (!markReported(adType, reqId)) {
                return;   // 同一次展示的重复回调
            }
            String token = UserManager.getToken(context);
            if (token == null) return;
            Log.d(TAG, "上报eCPM type=" + adType + " ecpm=" + ecpm + " sdk=" + sdk);
            ApiClient.reportAdRevenue(token, adType, ecpm.trim(), sdk, new ApiClient.ApiCallback() {
                @Override
                public void onSuccess(JSONObject data) {
                }

                @Override
                public void onError(String message) {
                    Log.w(TAG, "eCPM上报失败(忽略): " + message);
                }
            });
        } catch (Throwable t) {
            Log.w(TAG, "eCPM上报异常(忽略): " + t);
        }
    }

    /** 返回 true 表示首次上报；requestId 为空时无法去重，直接放行 */
    private static synchronized boolean markReported(String adType, String reqId) {
        if (reqId == null || reqId.isEmpty()) return true;
        String key = adType + ":" + reqId;
        if (REPORTED.contains(key)) return false;
        REPORTED.add(key);
        if (REPORTED.size() > DEDUP_SIZE) {
            Iterator<String> it = REPORTED.iterator();
            it.next();
            it.remove();
        }
        return true;
    }
}
