package com.tonyapp.djxplugin;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

import com.bytedance.sdk.openadsdk.AdSlot;
import com.bytedance.sdk.openadsdk.TTAdConstant;
import com.bytedance.sdk.openadsdk.TTAdNative;
import com.bytedance.sdk.openadsdk.TTAdSdk;
import com.bytedance.sdk.openadsdk.TTRewardVideoAd;
import com.bytedance.sdk.openadsdk.mediation.ad.MediationAdSlot;

import java.util.concurrent.atomic.AtomicBoolean;

public class RewardAdHelper {

    private static final String TAG = "RewardAdHelper";

    // 红包功能专用的激励视频广告位ID
    private static final String RED_PACKET_AD_CODE_ID = "104502063";

    public interface RewardCallback {
        void onRewardSuccess(int rewardAmount, String rewardName); // 用户完整看完，给奖励
        void onRewardFail(String reason); // 加载失败/播放出错/跳过/未通过校验
    }

    /**
     * 加载并展示红包激励视频广告
     */
    public static void loadAndShowRewardAd(Activity activity, RewardCallback callback) {
        AdSlot adSlot = new AdSlot.Builder()
                .setCodeId(RED_PACKET_AD_CODE_ID)
                .setOrientation(TTAdConstant.VERTICAL)
                .setMediationAdSlot(
                        new MediationAdSlot.Builder()
                                .setMuted(false)
                                .setRewardName("红包金币")
                                .setRewardAmount(10)
                                .setExtraObject("show_adn_load_error_detail", true) // 打开各ADN详细报错开关，方便排查填充失败原因
                                .build()
                )
                .build();

        TTAdNative adNativeLoader = TTAdSdk.getAdManager().createAdNative(activity);

        adNativeLoader.loadRewardVideoAd(adSlot, new TTAdNative.RewardVideoAdListener() {
            @Override
            public void onError(int errorCode, String errorMsg) {
                Log.e(TAG, "广告加载失败: code=" + errorCode + " msg=" + errorMsg);
                if (callback != null) {
                    callback.onRewardFail("广告加载失败: " + errorMsg);
                }
            }

            @Override
            public void onRewardVideoAdLoad(TTRewardVideoAd ttRewardVideoAd) {
                Log.d(TAG, "广告加载成功");
            }

            @Override
            public void onRewardVideoCached() {
                // 已废弃，不用管
            }

            @Override
            public void onRewardVideoCached(TTRewardVideoAd ttRewardVideoAd) {
                Log.d(TAG, "广告缓存成功，准备展示");
                showRewardAd(activity, ttRewardVideoAd, callback);
            }
        });
    }

    private static void showRewardAd(Activity activity, TTRewardVideoAd ttRewardVideoAd, RewardCallback callback) {
        if (activity == null || ttRewardVideoAd == null) {
            if (callback != null) {
                callback.onRewardFail("广告对象为空");
            }
            return;
        }

        // 一次播放只回调一次：SDK 有时会既回调"奖励有效"又回调"跳过"，
        // 或者重复回调奖励，用这两个标志把结果定死。
        final AtomicBoolean finished = new AtomicBoolean(false);   // 已经给过最终结果了吗
        final AtomicBoolean skipped = new AtomicBoolean(false);    // 用户跳过了吗

        ttRewardVideoAd.setRewardAdInteractionListener(new TTRewardVideoAd.RewardAdInteractionListener() {
            @Override
            public void onAdShow() {
                Log.d(TAG, "广告展示");
            }

            @Override
            public void onAdVideoBarClick() {
                Log.d(TAG, "广告被点击");
            }

            @Override
            public void onAdClose() {
                Log.d(TAG, "广告关闭");
                // 关闭时还没给过结果，说明既没看完也没明确跳过（比如中途按返回），按失败处理
                if (finished.compareAndSet(false, true)) {
                    Log.d(TAG, "关闭时未获得有效奖励，判为失败");
                    if (callback != null) {
                        callback.onRewardFail("未看完广告");
                    }
                }
            }

            @Override
            public void onVideoComplete() {
                Log.d(TAG, "视频播放完成");
            }

            @Override
            public void onVideoError() {
                Log.e(TAG, "视频播放出错");
                if (finished.compareAndSet(false, true) && callback != null) {
                    callback.onRewardFail("视频播放出错");
                }
            }

            @Override
            public void onRewardVerify(boolean rewardVerify, int rewardAmount, String rewardName, int errorCode, String errorMsg) {
                // 已废弃，不用管，实际逻辑走 onRewardArrived
            }

            @Override
            public void onRewardArrived(boolean isRewardValid, int rewardType, Bundle extraInfo) {
                // 用户跳过了，就算SDK说奖励有效也不认：没看完不能拿奖励
                if (skipped.get()) {
                    Log.d(TAG, "用户已跳过，忽略奖励回调");
                    return;
                }
                if (!finished.compareAndSet(false, true)) {
                    Log.d(TAG, "结果已确定，忽略重复的奖励回调");
                    return;
                }
                if (isRewardValid) {
                    Log.d(TAG, "奖励发放成功");
                    if (callback != null) {
                        callback.onRewardSuccess(10, "红包金币");
                    }
                } else {
                    Log.e(TAG, "奖励未通过验证");
                    if (callback != null) {
                        callback.onRewardFail("奖励未通过验证");
                    }
                }
            }

            @Override
            public void onSkippedVideo() {
                Log.d(TAG, "广告被跳过（未完整观看）");
                skipped.set(true);
                if (finished.compareAndSet(false, true) && callback != null) {
                    callback.onRewardFail("未看完广告，不能领取奖励");
                }
            }
        });

        ttRewardVideoAd.showRewardVideoAd(activity);
    }
}