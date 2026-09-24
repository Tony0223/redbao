package com.tonyapp.djxplugin;

import android.app.Application;
import android.util.Log;

import com.bytedance.sdk.openadsdk.TTAdConfig;
import com.bytedance.sdk.openadsdk.TTAdConstant;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.TTCustomController;

public class DjxSdkHolder {

    private static final String TAG = "DjxSdkHolder";

    private static volatile boolean sAdSdkInited = false;

    public interface StartCallback {
        void onResult(boolean success, String message);
    }

    public static synchronized void initAdSdk(Application application, String siteId, String appName) {
        if (sAdSdkInited) {
            return;
        }
        TTAdConfig config = new TTAdConfig.Builder()
                .appId(siteId)
                .appName(appName)
                .useMediation(true)
                .titleBarTheme(TTAdConstant.TITLE_BAR_THEME_DARK)
                .allowShowNotify(true)
                .supportMultiProcess(true)
                .debug(true)
                .customController(new TTCustomController() {
                    @Override
                    public boolean isCanUseLocation() {
                        return false;
                    }

                    @Override
                    public boolean isCanUsePhoneState() {
                        return false;
                    }

                    @Override
                    public boolean isCanUseWifiState() {
                        return false;
                    }
                })
                .build();
        TTAdSdk.init(application, config);
        sAdSdkInited = true;
    }

    /**
     * 只启动广告SDK，不启动短剧内容SDK。红包功能这类纯广告场景用这个。
     */
    public static void startAdOnly(final StartCallback callback) {
        TTAdSdk.start(new TTAdSdk.Callback() {
            @Override
            public void success() {
                Log.d(TAG, "GroMore ad sdk start success (ad only)");
                if (callback != null) {
                    callback.onResult(true, "广告SDK启动成功");
                }
            }

            @Override
            public void fail(int code, String msg) {
                Log.e(TAG, "GroMore ad sdk start fail: code=" + code + " msg=" + msg);
                if (callback != null) {
                    callback.onResult(false, "广告SDK启动失败 code=" + code + " msg=" + msg);
                }
            }
        });
    }
}