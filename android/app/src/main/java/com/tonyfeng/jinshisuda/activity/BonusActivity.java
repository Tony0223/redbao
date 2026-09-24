package com.tonyfeng.jinshisuda.activity;

import android.app.Dialog;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.Window;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.tonyapp.djxplugin.RewardAdHelper;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONObject;

/**
 * 福利活动页：今日看满 N 次激励视频 → 服务端当场发 M 金币。
 * 流程：点"立即观看" → 激励视频 → 完整看完才上报计数 → 满N次服务端发币并弹恭喜
 * N、M、提示文案都在后台 /admin/bonus 配，进度按自然日零点重置。
 */
public class BonusActivity extends AppCompatActivity {

    private TextView tvTitle;
    private TextView tvSubtitle;
    private TextView tvProgress;
    private TextView tvTips;
    private TextView btnWatch;
    private ProgressBar progressBar;

    /** 正在走"拉广告 → 上报"这一整套，防止连点 */
    private boolean watching = false;
    private boolean enabled = true;
    private boolean completed = false;
    private int targetCount = 20;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(R.layout.activity_bonus);

        tvTitle = findViewById(R.id.tv_bonus_title);
        tvSubtitle = findViewById(R.id.tv_bonus_subtitle);
        tvProgress = findViewById(R.id.tv_bonus_progress);
        tvTips = findViewById(R.id.tv_bonus_tips);
        btnWatch = findViewById(R.id.btn_bonus_watch);
        progressBar = findViewById(R.id.progress_bonus);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());
        btnWatch.setOnClickListener(v -> onWatchClick());
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadInfo();
    }

    // ================= 数据 =================

    private void loadInfo() {
        String token = UserManager.getToken(this);
        ApiClient.getBonusInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> render(d));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast("活动数据加载失败：" + message));
            }
        });
    }

    /** info 和 watch 的返回字段是同一套，两边都用这个渲染 */
    private void render(JSONObject d) {
        enabled = d.optBoolean("enabled", true);
        targetCount = Math.max(1, d.optInt("target_count", 20));
        completed = d.optBoolean("completed", false);
        int watchCount = d.optInt("watch_count", 0);

        tvTitle.setText(d.optString("title", "看满" + targetCount + "次视频 · 领金币"));
        tvSubtitle.setText(d.optString("subtitle", "进度实时保存 · 看完即计数"));
        tvProgress.setText(watchCount + "/" + targetCount);

        progressBar.setMax(targetCount);
        progressBar.setProgress(Math.min(watchCount, targetCount));

        String tips = d.optString("tips_text", "");
        tvTips.setText(tips);
        findViewById(R.id.layout_bonus_tips)
                .setVisibility(tips.isEmpty() ? View.GONE : View.VISIBLE);

        if (!enabled) {
            btnWatch.setText("活动未开启");
            btnWatch.setEnabled(false);
            btnWatch.setAlpha(0.6f);
        } else if (completed) {
            btnWatch.setText("今日已完成");
            btnWatch.setEnabled(false);
            btnWatch.setAlpha(0.6f);
        } else {
            btnWatch.setText("▶ 立即观看");
            btnWatch.setEnabled(!watching);
            btnWatch.setAlpha(watching ? 0.6f : 1f);
        }
    }

    // ================= 看广告 =================

    private void onWatchClick() {
        if (watching) return;
        if (!enabled) {
            toast("活动未开启");
            return;
        }
        if (completed) {
            toast("今日任务已完成，明天再来");
            return;
        }
        setWatching(true);

        // 看完激励视频才计数；跳过或中途退出都不算
        RewardAdHelper.loadAndShowRewardAd(this, new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                reportWatch();
            }

            @Override
            public void onRewardFail(String reason) {
                runOnUiThread(() -> {
                    setWatching(false);
                    toast(reason);
                });
            }
        });
    }

    private void reportWatch() {
        String token = UserManager.getToken(this);
        ApiClient.reportBonusWatch(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    setWatching(false);
                    render(d);
                    if (d.optBoolean("just_rewarded", false)) {
                        showResultDialog(d.optLong("reward_got", 0));
                    } else {
                        toast(d.optString("message", ""));
                    }
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    setWatching(false);
                    toast(message);
                    loadInfo();
                });
            }
        });
    }

    private void setWatching(boolean value) {
        watching = value;
        if (btnWatch == null) return;
        if (!enabled || completed) return;   // 这两种情况按钮状态由 render 决定
        btnWatch.setEnabled(!value);
        btnWatch.setAlpha(value ? 0.6f : 1f);
        btnWatch.setText(value ? "广告加载中…" : "▶ 立即观看");
    }

    // ================= 结果弹窗 =================

    private void showResultDialog(long coins) {
        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_signin_result, null);
        dialog.setContentView(view);
        dialog.setCanceledOnTouchOutside(false);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }

        ((TextView) view.findViewById(R.id.tv_result_coins)).setText("+" + coins + " 金币");
        ((TextView) view.findViewById(R.id.tv_result_tip))
                .setText("今日福利活动已完成\n明天再来还能领");

        view.findViewById(R.id.btn_result_ok).setOnClickListener(v -> dialog.dismiss());
        dialog.show();
    }

    private void toast(String msg) {
        if (msg != null && !msg.isEmpty()) {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        }
    }
}
