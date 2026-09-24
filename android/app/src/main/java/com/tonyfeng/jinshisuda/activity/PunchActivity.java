package com.tonyfeng.jinshisuda.activity;

import android.app.Dialog;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.Window;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.tonyapp.djxplugin.RewardAdHelper;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 每日打卡页。
 * 流程：7:00-11:00 点"立即打卡" → 激励视频 → 看完上报服务端 → 记下名次
 * 每天11:10服务端统一算排名发奖，前120名按四档瓜分当日奖金池
 */
public class PunchActivity extends AppCompatActivity {

    private TextView tvPunchTime;
    private TextView tvPoolCoins;
    private TextView tvMyStatus;
    private TextView btnPunch;
    private TextView tvRankTip;
    private TextView tvRankEmpty;
    private LinearLayout layoutRankList;

    private boolean punching = false;
    private String rulesText = "";

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(R.layout.activity_punch);

        tvPunchTime = findViewById(R.id.tv_punch_time);
        tvPoolCoins = findViewById(R.id.tv_pool_coins);
        tvMyStatus = findViewById(R.id.tv_my_status);
        btnPunch = findViewById(R.id.btn_punch);
        tvRankTip = findViewById(R.id.tv_rank_tip);
        tvRankEmpty = findViewById(R.id.tv_rank_empty);
        layoutRankList = findViewById(R.id.layout_rank_list);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());
        findViewById(R.id.btn_rules).setOnClickListener(v -> showRules());
        btnPunch.setOnClickListener(v -> onPunchClick());
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadInfo();
        loadRank();
    }

    // ================= 数据 =================

    private void loadInfo() {
        String token = UserManager.getToken(this);
        ApiClient.getPunchInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> renderInfo(d));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast("打卡数据加载失败：" + message));
            }
        });
    }

    private void renderInfo(JSONObject d) {
        rulesText = d.optString("rules", "");

        String start = d.optString("start_time", "07:00:00");
        String end = d.optString("end_time", "11:00:00");
        tvPunchTime.setText("开始时间：" + start + "-" + end);

        tvPoolCoins.setText(String.format("%,d 金币", d.optLong("pool_coins", 0)));

        String status = d.optString("status", "closed");
        int myRank = d.optInt("my_rank", 0);
        long myReward = d.optLong("my_reward_coins", 0);
        int punchCount = d.optInt("punch_count", 0);

        switch (status) {
            case "open":
                btnPunch.setText("立即打卡");
                btnPunch.setEnabled(true);
                btnPunch.setAlpha(1f);
                tvMyStatus.setText("今日已有 " + punchCount + " 人打卡");
                break;
            case "done":
                btnPunch.setText("今日已打卡");
                btnPunch.setEnabled(false);
                btnPunch.setAlpha(0.6f);
                if (myReward > 0) {
                    tvMyStatus.setText("今日第 " + myRank + " 名，已获得 " + myReward + " 金币");
                } else {
                    tvMyStatus.setText("今日第 " + myRank + " 名，11:10 公布奖励");
                }
                break;
            case "before":
                btnPunch.setText("还没到打卡时间");
                btnPunch.setEnabled(false);
                btnPunch.setAlpha(0.6f);
                tvMyStatus.setText("每天 " + start + " 开始，越早打卡爆得越多");
                break;
            default:   // closed
                btnPunch.setText("今日打卡已结束");
                btnPunch.setEnabled(false);
                btnPunch.setAlpha(0.6f);
                tvMyStatus.setText(myRank > 0
                        ? "今日第 " + myRank + " 名"
                        : "今天没有参与打卡，明天早点来");
                break;
        }
    }

    private void loadRank() {
        String token = UserManager.getToken(this);
        ApiClient.getPunchRank(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> renderRank(d));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    layoutRankList.removeAllViews();
                    tvRankEmpty.setText("排行榜加载失败");
                    tvRankEmpty.setVisibility(View.VISIBLE);
                });
            }
        });
    }

    private void renderRank(JSONObject d) {
        boolean published = d.optBoolean("published", false);
        tvRankTip.setText(published ? "今日奖励已发放" : "每日11:10公布排名与奖励");

        JSONArray arr = d.optJSONArray("list");
        layoutRankList.removeAllViews();

        if (arr == null || arr.length() == 0) {
            tvRankEmpty.setText("还没有人打卡，抢第一名");
            tvRankEmpty.setVisibility(View.VISIBLE);
            return;
        }
        tvRankEmpty.setVisibility(View.GONE);

        LayoutInflater inflater = LayoutInflater.from(this);
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            View row = inflater.inflate(R.layout.item_punch_rank, layoutRankList, false);

            int rank = o.optInt("rank", i + 1);
            boolean isMe = o.optBoolean("is_me", false);
            long reward = o.optLong("reward_coins", 0);

            TextView tvNo = row.findViewById(R.id.tv_rank_no);
            TextView tvName = row.findViewById(R.id.tv_rank_name);
            TextView tvReward = row.findViewById(R.id.tv_rank_reward);

            tvNo.setText("No." + rank);
            tvName.setText(o.optString("nickname", "") + (isMe ? "（我）" : ""));
            tvReward.setText(reward > 0 ? "+" + reward + " 金币" : "待公布");

            if (isMe) {
                row.setBackgroundColor(Color.parseColor("#FFF3E0"));
                tvName.setTextColor(Color.parseColor("#E8261F"));
            }
            layoutRankList.addView(row);
        }
    }

    // ================= 打卡 =================

    private void onPunchClick() {
        if (punching) return;
        punching = true;

        // 看完激励视频才算打卡；跳过或中途退出都不算
        RewardAdHelper.loadAndShowRewardAd(this, new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                doPunch();
            }

            @Override
            public void onRewardFail(String reason) {
                runOnUiThread(() -> {
                    punching = false;
                    toast(reason);
                });
            }
        });
    }

    private void doPunch() {
        String token = UserManager.getToken(this);
        ApiClient.punch(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                int rank = d.optInt("rank", 0);
                runOnUiThread(() -> {
                    punching = false;
                    toast("打卡成功！今日第 " + rank + " 名");
                    loadInfo();
                    loadRank();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    punching = false;
                    toast(message);
                    loadInfo();
                });
            }
        });
    }

    // ================= 规则 =================

    private void showRules() {
        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_punch_rules, null);
        dialog.setContentView(view);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }

        ((TextView) view.findViewById(R.id.tv_rules_content))
                .setText(rulesText.isEmpty() ? "规则加载中，请稍后再试" : rulesText);
        view.findViewById(R.id.btn_rules_ok).setOnClickListener(v -> dialog.dismiss());

        dialog.show();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }
}