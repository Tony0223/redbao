package com.tonyfeng.jinshisuda.fragment;

import android.app.Dialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.tonyapp.djxplugin.InterstitialAdHelper;
import com.tonyapp.djxplugin.RewardAdHelper;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.activity.BonusActivity;
import com.tonyfeng.jinshisuda.activity.PunchActivity;
import com.tonyfeng.jinshisuda.activity.WheelActivity;
import com.tonyfeng.jinshisuda.activity.WithdrawalActivity;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 福利页。
 * - 今日已赚 + 每日签到：接后端 /api/welfare/*
 *   签到流程：点"立即签到" → 激励视频 → 看完上报服务端发金币 → 结果弹窗 → 关掉后弹插屏
 * - 每日打卡：跳 PunchActivity
 * - 福利活动：卡片上显示今日进度，点"去观看"跳 BonusActivity（看满N次领M金币）
 * - 信息流广告：不再夹在页面中间，改成由 FeedAdDrawer 从底部抽屉式弹出，
 *   挂载逻辑统一在 MyApplication 里，本页面不用管
 * - 幸运转盘：点"转一转"跳 WheelActivity（抽奖结果服务端定，看完广告才发金币）
 */
public class WelfareFragment extends Fragment {

    private View root;
    private TextView tvTodayEarned;
    private TextView tvSignInTitle;
    private TextView tvSignInSubtitle;
    private TextView btnSignIn;
    private TextView tvTaskProgress;
    private TextView tvTaskDesc;
    private TextView btnTask;

    private long coinsPerYuan = 100000;
    private boolean todaySigned = false;
    private boolean signing = false;

    /** 签到某一天 */
    static class SignInDay {
        int day;
        long coins;
        String state;   // done 已签 / today 今天可签 / future 未来
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        root = inflater.inflate(R.layout.fragment_welfare, container, false);

        tvTodayEarned = root.findViewById(R.id.tv_today_earned);
        tvSignInTitle = root.findViewById(R.id.tv_signin_title);
        tvSignInSubtitle = root.findViewById(R.id.tv_signin_subtitle);
        btnSignIn = root.findViewById(R.id.btn_signin);
        tvTaskProgress = root.findViewById(R.id.tv_task_progress);
        tvTaskDesc = root.findViewById(R.id.tv_task_desc);
        btnTask = root.findViewById(R.id.btn_task);

        root.findViewById(R.id.btn_go_withdraw).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), WithdrawalActivity.class)));

        btnSignIn.setOnClickListener(v -> onSignInClick());

        root.findViewById(R.id.btn_punch).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), PunchActivity.class)));

        btnTask.setOnClickListener(v ->
                startActivity(new Intent(requireContext(), BonusActivity.class)));

        root.findViewById(R.id.btn_wheel).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), WheelActivity.class)));

        return root;
    }

    @Override
    public void onResume() {
        super.onResume();
        loadInfo();
    }

    @Override
    public void onHiddenChanged(boolean hidden) {
        super.onHiddenChanged(hidden);
        if (!hidden) {
            loadInfo();     // 从其他 tab 切回来时刷新
        }
    }

    // ================= 数据 =================

    private void loadInfo() {
        if (!isAdded()) return;
        if (!UserManager.isLoggedIn(requireContext())) {
            tvTodayEarned.setText("0.0");
            return;
        }
        String token = UserManager.getToken(requireContext());
        ApiClient.getSignInInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> renderInfo(d));
            }

            @Override
            public void onError(String message) {
                runOnUi(() -> toast("福利数据加载失败：" + message));
            }
        });
        loadBonusInfo(token);
    }

    private void renderInfo(JSONObject d) {
        long rate = d.optLong("coins_per_yuan", coinsPerYuan);
        coinsPerYuan = rate > 0 ? rate : coinsPerYuan;

        tvTodayEarned.setText(coinsToYuan(d.optLong("today_earned_coins", 0)));

        int cycleDays = d.optInt("cycle_days", 7);
        int signedDays = d.optInt("signed_days", 0);
        todaySigned = d.optBoolean("today_signed", false);

        tvSignInTitle.setText("连续签到" + cycleDays + "天领金币");
        tvSignInSubtitle.setText(todaySigned
                ? "今日已签到，已连续 " + signedDays + " 天"
                : "中途断签需重新签到");
        btnSignIn.setText(todaySigned ? "已签到" : "立即签到");
        btnSignIn.setAlpha(todaySigned ? 0.5f : 1f);

        renderSignInDays(parseDays(d.optJSONArray("days")));
    }

    private List<SignInDay> parseDays(JSONArray arr) {
        List<SignInDay> list = new ArrayList<>();
        if (arr == null) return list;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            SignInDay day = new SignInDay();
            day.day = o.optInt("day", i + 1);
            day.coins = o.optLong("coins", 0);
            day.state = o.optString("state", "future");
            list.add(day);
        }
        return list;
    }

    private void renderSignInDays(List<SignInDay> days) {
        LinearLayout container = root.findViewById(R.id.layout_signin_days);
        container.removeAllViews();
        if (days.isEmpty()) return;

        LayoutInflater inflater = LayoutInflater.from(requireContext());
        for (SignInDay day : days) {
            View cell = inflater.inflate(R.layout.item_signin_day, container, false);
            TextView tvCoins = cell.findViewById(R.id.tv_signin_coins);
            TextView tvState = cell.findViewById(R.id.tv_signin_state);
            View packet = cell.findViewById(R.id.layout_packet);

            tvCoins.setText(String.valueOf(day.coins));
            ((TextView) cell.findViewById(R.id.tv_signin_day)).setText("第" + day.day + "天");

            if ("done".equals(day.state)) {
                packet.setBackgroundResource(R.drawable.bg_signin_packet_done);
                tvCoins.setTextColor(Color.parseColor("#FFFFFF"));
                tvState.setText("已领");
                tvState.setTextColor(Color.parseColor("#FFFFFF"));
            } else {
                packet.setBackgroundResource(R.drawable.bg_signin_packet);
                tvCoins.setTextColor(Color.parseColor("#FFF6D8"));
                tvState.setText("开");
                tvState.setTextColor(Color.parseColor("#FFD54F"));
            }
            container.addView(cell);
        }
    }

    // ================= 福利活动（卡片上的进度） =================

    private void loadBonusInfo(String token) {
        ApiClient.getBonusInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> renderBonus(d));
            }

            @Override
            public void onError(String message) {
                // 静默失败：卡片保留布局里的默认文案，不打扰用户
            }
        });
    }

    private void renderBonus(JSONObject d) {
        View card = root.findViewById(R.id.layout_task_card);
        if (!d.optBoolean("enabled", true)) {
            card.setVisibility(View.GONE);
            return;
        }
        card.setVisibility(View.VISIBLE);

        int target = Math.max(1, d.optInt("target_count", 20));
        int watched = d.optInt("watch_count", 0);
        boolean completed = d.optBoolean("completed", false);

        tvTaskDesc.setText(d.optString("title", "看视频" + target + "次 · 领金币"));
        tvTaskProgress.setText("当前已观看广告次数（" + watched + "/" + target + "）");
        btnTask.setText(completed ? "已完成" : "去观看");
        btnTask.setAlpha(completed ? 0.5f : 1f);
    }

    // ================= 签到 =================

    private void onSignInClick() {
        if (!UserManager.isLoggedIn(requireContext())) {
            toast("请先登录");
            return;
        }
        if (todaySigned) {
            toast("今天已经签到过了，明天再来");
            return;
        }
        if (signing) return;
        signing = true;

        // 看完激励视频才发金币；跳过或中途退出都拿不到
        RewardAdHelper.loadAndShowRewardAd(requireActivity(), new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                doSignIn();
            }

            @Override
            public void onRewardFail(String reason) {
                runOnUi(() -> {
                    signing = false;
                    toast(reason);
                });
            }
        });
    }

    private void doSignIn() {
        String token = UserManager.getToken(requireContext());
        ApiClient.signIn(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                long coins = d.optLong("coins", 0);
                int signedDays = d.optInt("signed_days", 0);
                runOnUi(() -> {
                    signing = false;
                    showResultDialog(coins, signedDays);
                    loadInfo();
                });
            }

            @Override
            public void onError(String message) {
                runOnUi(() -> {
                    signing = false;
                    toast(message);
                    loadInfo();
                });
            }
        });
    }

    private void showResultDialog(long coins, int signedDays) {
        Dialog dialog = new Dialog(requireContext());
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(requireContext())
                .inflate(R.layout.dialog_signin_result, null);
        dialog.setContentView(view);
        dialog.setCanceledOnTouchOutside(false);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }

        ((TextView) view.findViewById(R.id.tv_result_coins)).setText("+" + coins + " 金币");
        ((TextView) view.findViewById(R.id.tv_result_tip))
                .setText("已连续签到 " + signedDays + " 天\n明天继续签到可领更多");

        view.findViewById(R.id.btn_result_ok).setOnClickListener(v -> {
            dialog.dismiss();
            // 弹窗关掉之后再弹插屏，不跟签到按钮叠在一起
            if (isAdded()) InterstitialAdHelper.show(requireActivity(), null);
        });

        dialog.show();
    }

    // ================= 工具 =================

    private String coinsToYuan(long coins) {
        double v = coins / (double) coinsPerYuan;
        return String.format("%.2f", v);
    }

    private void runOnUi(Runnable r) {
        if (!isAdded()) return;
        requireActivity().runOnUiThread(() -> {
            if (isAdded()) r.run();
        });
    }

    private void toast(String msg) {
        if (isAdded()) Toast.makeText(requireContext(), msg, Toast.LENGTH_SHORT).show();
    }
}
