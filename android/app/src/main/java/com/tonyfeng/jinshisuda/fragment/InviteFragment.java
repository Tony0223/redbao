package com.tonyfeng.jinshisuda.fragment;

import android.Manifest;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;

import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.activity.InviteListActivity;
import com.tonyfeng.jinshisuda.activity.WithdrawalActivity;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.AvatarLoader;
import com.tonyfeng.jinshisuda.api.InviteShareHelper;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 邀请页。
 * - 推广统计、我的推广、我的收益：/api/invite/*
 * - 平台补贴：/api/subsidy/*（没配活动时隐藏；活动结束显示"活动已结束"）
 * - 立即邀请：生成带二维码的邀请海报，分享到微信/朋友圈、保存相册、复制链接
 * - 微信头像昵称：走 /api/user/me/profile（invite/summary 没有头像字段），
 *   头像为空的老用户显示昵称首字的彩色圆
 */
public class InviteFragment extends Fragment {

    private static final int REQ_SAVE_PERMISSION = 1001;

    private View root;
    private ImageView ivAvatar;
    private TextView tvNickname;
    private TextView tvUserId;

    private long coinsPerYuan = 100000;
    private int totalCount = 0;
    private long totalIncomeCoins = 0;
    private String inviteCode = "";
    private Bitmap posterCache;

    // 倒计时：用服务器时间算出剩余时长，再用开机时钟本地走秒，不受手机系统时间影响
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long endElapsedRealtime = 0;
    private boolean submitting = false;

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (!isAdded()) return;
            long remain = endElapsedRealtime - SystemClock.elapsedRealtime();
            if (remain <= 0) {
                renderCountdown(0);
                loadSubsidy(); // 到点了，重新向服务器确认活动状态
                return;
            }
            renderCountdown(remain);
            handler.postDelayed(this, 1000);
        }
    };

    /** 海报生成是异步的，生成好后回调 */
    interface PosterReady {
        void onReady(Bitmap poster);
    }

    /** 补贴档位（金额单位都是分） */
    static class SubsidyTier {
        int id;
        long withdrawFen;
        int percent;
        long subsidyFen;
        long arriveFen;
        long coinAmount;
        int limit;   // 0 表示不限次
        int used;

        boolean exhausted() {
            return limit > 0 && used >= limit;
        }
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        root = inflater.inflate(R.layout.fragment_invite, container, false);

        ivAvatar = root.findViewById(R.id.iv_avatar);
        tvNickname = root.findViewById(R.id.tv_nickname);
        tvUserId = root.findViewById(R.id.tv_user_id);

        initStats();
        initCountdownLabels();
        initMenus();

        root.findViewById(R.id.layout_user_id).setOnClickListener(v -> copyUserId());
        root.findViewById(R.id.btn_invite).setOnClickListener(v -> showShareDialog());

        root.findViewById(R.id.layout_subsidy).setVisibility(View.GONE); // 加载到活动信息后再决定显示

        return root;
    }

    @Override
    public void onResume() {
        super.onResume();
        refreshAll();
    }

    @Override
    public void onPause() {
        super.onPause();
        handler.removeCallbacks(tick);
    }

    @Override
    public void onHiddenChanged(boolean hidden) {
        super.onHiddenChanged(hidden);
        if (hidden) {
            handler.removeCallbacks(tick);
        } else {
            refreshAll(); // 从其他 tab 切回来时刷新
        }
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        handler.removeCallbacksAndMessages(null);
        if (posterCache != null && !posterCache.isRecycled()) {
            posterCache.recycle();
        }
        posterCache = null;
    }

    private void refreshAll() {
        loadSummary();
        loadSubsidy();
        loadAvatar();
    }

    // ================= 头像昵称 =================

    /**
     * 头像和昵称走 /api/user/me/profile。
     * invite/summary 接口里没有头像字段，与其为这一个字段改后端，
     * 不如直接调"我的"页那个现成的接口。
     */
    private void loadAvatar() {
        if (!isAdded()) return;
        if (!UserManager.isLoggedIn(requireContext())) {
            AvatarLoader.load(ivAvatar, "", "未登录");
            return;
        }
        String token = UserManager.getToken(requireContext());
        ApiClient.getMyProfile(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> {
                    String nickname = d.optString("nickname", "微信用户");
                    // 头像为空（老用户还没用新版本登录过）时自动显示昵称首字
                    AvatarLoader.load(ivAvatar, d.optString("avatar_url", ""), nickname);
                    tvNickname.setText(nickname);
                });
            }

            @Override
            public void onError(String message) {
                // 头像拉不到不影响页面其他部分，静默处理
            }
        });
    }

    // ================= 推广统计 =================

    private void loadSummary() {
        if (!isAdded()) return;
        if (!UserManager.isLoggedIn(requireContext())) {
            AvatarLoader.load(ivAvatar, "", "未登录");
            tvNickname.setText("未登录");
            tvUserId.setText("用户ID：-");
            renderStats(0, 0, 0, 0, 0, 0, 0);
            return;
        }
        tvUserId.setText("用户ID：" + UserManager.getUserId(requireContext()));

        String token = UserManager.getToken(requireContext());
        ApiClient.getInviteSummary(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> {
                    long rate = d.optLong("coins_per_yuan", coinsPerYuan);
                    coinsPerYuan = rate > 0 ? rate : coinsPerYuan;
                    totalIncomeCoins = d.optLong("total_income_coins", 0);

                    String newCode = d.optString("invite_code", "");
                    if (!newCode.equals(inviteCode)) {
                        inviteCode = newCode;
                        clearPosterCache();   // 换了账号，海报要重新生成
                    }

                    tvNickname.setText(d.optString("nickname", "微信用户"));
                    tvUserId.setText("用户ID：" + d.optLong("user_id"));
                    renderStats(
                            d.optInt("total_count", 0),
                            d.optLong("today_income_coins", 0),
                            d.optInt("today_new", 0),
                            d.optInt("today_active", 0),
                            d.optInt("yesterday_new", 0),
                            d.optInt("yesterday_active", 0),
                            d.optLong("yesterday_income_coins", 0));
                });
            }

            @Override
            public void onError(String message) {
                runOnUi(() -> toast("推广数据加载失败：" + message));
            }
        });
    }

    private void copyUserId() {
        if (!UserManager.isLoggedIn(requireContext())) return;
        String id = String.valueOf(UserManager.getUserId(requireContext()));
        ClipboardManager cm = (ClipboardManager) requireContext()
                .getSystemService(Context.CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("user_id", id));
        toast("用户ID已复制");
    }

    private void initStats() {
        setStatLabel(R.id.stat_total, "总人数", 30);
        setStatLabel(R.id.stat_today_income, "今日收益(元)", 30);
        setStatLabel(R.id.stat_today_new, "今日新增", 22);
        setStatLabel(R.id.stat_today_active, "今日活跃", 22);
        setStatLabel(R.id.stat_yesterday_new, "昨日新增", 22);
        setStatLabel(R.id.stat_yesterday_active, "昨日活跃", 22);
    }

    private void setStatLabel(int cellId, String label, int valueSp) {
        View cell = root.findViewById(cellId);
        ((TextView) cell.findViewById(R.id.tv_stat_label)).setText(label);
        ((TextView) cell.findViewById(R.id.tv_stat_value)).setTextSize(valueSp);
    }

    private void setStatValue(int cellId, String value) {
        View cell = root.findViewById(cellId);
        ((TextView) cell.findViewById(R.id.tv_stat_value)).setText(value);
    }

    private void renderStats(int total, long todayIncomeCoins, int todayNew, int todayActive,
                             int yesterdayNew, int yesterdayActive, long yesterdayIncomeCoins) {
        totalCount = total;
        setStatValue(R.id.stat_total, String.valueOf(total));
        setStatValue(R.id.stat_today_income, coinsToYuan(todayIncomeCoins));
        setStatValue(R.id.stat_today_new, String.valueOf(todayNew));
        setStatValue(R.id.stat_today_active, String.valueOf(todayActive));
        setStatValue(R.id.stat_yesterday_new, String.valueOf(yesterdayNew));
        setStatValue(R.id.stat_yesterday_active, String.valueOf(yesterdayActive));
        setMenuValue(R.id.row_promotion, total + "人", "#666666");
        setMenuValue(R.id.row_income, "昨日收益：¥" + coinsToYuan(yesterdayIncomeCoins), "#F03E3E");
    }

    // ================= 邀请分享 =================

    private void showShareDialog() {
        if (!checkLogin()) return;
        if (inviteCode.isEmpty()) {
            toast("邀请码加载中，请稍后再试");
            loadSummary();
            return;
        }

        BottomSheetDialog dialog = new BottomSheetDialog(requireContext());
        View view = LayoutInflater.from(requireContext())
                .inflate(R.layout.dialog_invite_share, null);
        dialog.setContentView(view);

        // 一打开就完全展开，不用用户手动上滑
        dialog.setOnShowListener(d -> {
            View sheet = dialog.findViewById(
                    com.google.android.material.R.id.design_bottom_sheet);
            if (sheet == null) return;
            com.google.android.material.bottomsheet.BottomSheetBehavior<View> behavior =
                    com.google.android.material.bottomsheet.BottomSheetBehavior.from(sheet);
            behavior.setState(
                    com.google.android.material.bottomsheet.BottomSheetBehavior.STATE_EXPANDED);
            behavior.setSkipCollapsed(true);
        });

        ImageView ivPoster = view.findViewById(R.id.iv_poster);
        View loading = view.findViewById(R.id.poster_loading);

        view.findViewById(R.id.share_wechat).setOnClickListener(v -> {
            dialog.dismiss();
            shareToWeChat(false);
        });
        view.findViewById(R.id.share_moments).setOnClickListener(v -> {
            dialog.dismiss();
            shareToWeChat(true);
        });
        view.findViewById(R.id.share_save).setOnClickListener(v -> {
            dialog.dismiss();
            savePoster();
        });
        view.findViewById(R.id.share_link).setOnClickListener(v -> {
            dialog.dismiss();
            copyInviteLink();
        });
        view.findViewById(R.id.share_cancel).setOnClickListener(v -> dialog.dismiss());

        dialog.show();

        // 海报生成好后显示预览（生成期间显示转圈）
        preparePoster(poster -> {
            if (!dialog.isShowing()) return;
            ivPoster.setImageBitmap(poster);
            ivPoster.setVisibility(View.VISIBLE);
            loading.setVisibility(View.GONE);
        });
    }

    /** 海报生成放后台线程，生成好了在主线程回调 */
    private void preparePoster(@Nullable PosterReady onReady) {
        if (posterCache != null && !posterCache.isRecycled()) {
            if (onReady != null) onReady.onReady(posterCache);
            return;
        }
        String nickname = tvNickname.getText().toString();
        String code = inviteCode;
        Context appContext = requireContext().getApplicationContext();
        new Thread(() -> {
            Bitmap poster = InviteShareHelper.buildPoster(appContext, nickname, code);
            runOnUi(() -> {
                posterCache = poster;
                if (onReady != null) onReady.onReady(poster);
            });
        }).start();
    }

    private void clearPosterCache() {
        if (posterCache != null && !posterCache.isRecycled()) {
            posterCache.recycle();
        }
        posterCache = null;
    }

    private void shareToWeChat(boolean timeline) {
        toast("正在生成邀请海报…");
        preparePoster(poster -> {
            boolean ok = InviteShareHelper.shareToWeChat(requireContext(), poster, timeline);
            if (!ok) toast("分享失败，请确认已安装微信");
        });
    }

    private void savePoster() {
        // Android 9 及以下保存到相册要存储权限
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P
                && ContextCompat.checkSelfPermission(requireContext(),
                Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(requireActivity(),
                    new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_SAVE_PERMISSION);
            return;
        }
        toast("正在保存…");
        Context appContext = requireContext().getApplicationContext();
        preparePoster(poster -> new Thread(() -> {
            boolean ok = InviteShareHelper.saveToGallery(appContext, poster);
            runOnUi(() -> toast(ok ? "已保存到相册" : "保存失败"));
        }).start());
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_SAVE_PERMISSION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                savePoster();
            } else {
                toast("没有存储权限，无法保存到相册");
            }
        }
    }

    private void copyInviteLink() {
        String text = InviteShareHelper.inviteToken(inviteCode)
                + " 下载链接：" + InviteShareHelper.landingUrl(inviteCode);
        ClipboardManager cm = (ClipboardManager) requireContext()
                .getSystemService(Context.CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("invite_link", text));
        toast("邀请链接已复制，去微信粘贴给好友");
    }

    // ================= 平台补贴 =================

    private void loadSubsidy() {
        if (!isAdded() || !UserManager.isLoggedIn(requireContext())) {
            root.findViewById(R.id.layout_subsidy).setVisibility(View.GONE);
            return;
        }
        String token = UserManager.getToken(requireContext());
        ApiClient.getSubsidyInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> renderSubsidy(d));
            }

            @Override
            public void onError(String message) {
                // 补贴信息拉不到就先不显示这个模块，不影响页面其他部分
                runOnUi(() -> root.findViewById(R.id.layout_subsidy).setVisibility(View.GONE));
            }
        });
    }

    private void renderSubsidy(JSONObject d) {
        View layoutSubsidy = root.findViewById(R.id.layout_subsidy);
        View layoutCountdown = root.findViewById(R.id.layout_countdown);
        View layoutTiers = root.findViewById(R.id.layout_tiers);
        TextView tvSubtitle = root.findViewById(R.id.tv_subsidy_subtitle);

        handler.removeCallbacks(tick);
        String status = d.optString("status", "none");

        if ("none".equals(status)) {
            layoutSubsidy.setVisibility(View.GONE);
            return;
        }
        layoutSubsidy.setVisibility(View.VISIBLE);

        long remain = d.optLong("end_at_ms", 0) - d.optLong("server_now_ms", 0);
        if ("ended".equals(status) || remain <= 0) {
            tvSubtitle.setText("活动已结束");
            layoutCountdown.setVisibility(View.GONE);
            layoutTiers.setVisibility(View.GONE);
            return;
        }

        tvSubtitle.setText("活动剩余时间");
        layoutCountdown.setVisibility(View.VISIBLE);
        layoutTiers.setVisibility(View.VISIBLE);

        endElapsedRealtime = SystemClock.elapsedRealtime() + remain;
        renderCountdown(remain);
        handler.postDelayed(tick, 1000);

        renderTiers(parseTiers(d.optJSONArray("tiers")));
    }

    private List<SubsidyTier> parseTiers(JSONArray arr) {
        List<SubsidyTier> list = new ArrayList<>();
        if (arr == null) return list;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            SubsidyTier t = new SubsidyTier();
            t.id = o.optInt("id");
            t.withdrawFen = o.optLong("withdraw_fen");
            t.percent = o.optInt("percent");
            t.subsidyFen = o.optLong("subsidy_fen");
            t.arriveFen = o.optLong("arrive_fen");
            t.coinAmount = o.optLong("coin_amount");
            t.limit = o.optInt("limit", 0);
            t.used = o.optInt("used", 0);
            list.add(t);
        }
        return list;
    }

    private void renderTiers(List<SubsidyTier> tiers) {
        LinearLayout container = root.findViewById(R.id.layout_tiers);
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(requireContext());
        for (SubsidyTier tier : tiers) {
            View row = inflater.inflate(R.layout.item_invite_subsidy_tier, container, false);
            ((TextView) row.findViewById(R.id.tv_tier_desc)).setText(
                    "提现" + fenToYuan(tier.withdrawFen, true) + "元  实际到账 "
                            + fenToYuan(tier.arriveFen, false) + "元");
            ((TextView) row.findViewById(R.id.tv_tier_percent)).setText(tier.percent + "%");

            TextView tvLimit = row.findViewById(R.id.tv_tier_limit);
            if (tier.limit > 0) {
                tvLimit.setText(tier.exhausted()
                        ? "每人限" + tier.limit + "次，已用完"
                        : "每人限" + tier.limit + "次，已用" + tier.used + "次");
            } else {
                tvLimit.setText("不限次数");
            }

            row.setAlpha(tier.exhausted() ? 0.5f : 1f);
            row.setOnClickListener(v -> onTierClick(tier));
            container.addView(row);
        }
    }

    private void onTierClick(SubsidyTier tier) {
        if (!UserManager.isLoggedIn(requireContext())) {
            toast("请先登录");
            return;
        }
        if (tier.exhausted()) {
            toast("这一档的补贴次数已用完");
            return;
        }
        String message = "提现 " + fenToYuan(tier.withdrawFen, true) + " 元"
                + "，平台补贴 " + fenToYuan(tier.subsidyFen, true) + " 元"
                + "，实际到账 " + fenToYuan(tier.arriveFen, true) + " 元\n"
                + "将扣除 " + tier.coinAmount + " 金币\n\n"
                + "审核通过后打款到微信零钱。补贴以审核时活动仍在进行为准，"
                + "活动结束后才审核的，按提现金额到账。";

        new AlertDialog.Builder(requireContext())
                .setTitle("确认补贴提现")
                .setMessage(message)
                .setPositiveButton("确认提现", (dialog, which) -> submitTier(tier))
                .setNegativeButton("取消", null)
                .show();
    }

    private void submitTier(SubsidyTier tier) {
        if (submitting) return;
        submitting = true;
        String token = UserManager.getToken(requireContext());
        ApiClient.subsidyWithdraw(token, tier.id, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                runOnUi(() -> {
                    submitting = false;
                    toast("提现申请已提交，等待审核");
                    refreshAll();
                });
            }

            @Override
            public void onError(String message) {
                runOnUi(() -> {
                    submitting = false;
                    if (message != null && message.contains("绑定微信收款")) {
                        new AlertDialog.Builder(requireContext())
                                .setTitle("需要先绑定微信收款")
                                .setMessage("首次提现需要绑定微信零钱收款，只需绑定一次。")
                                .setPositiveButton("去绑定", (d, w) -> startActivity(
                                        new Intent(requireContext(), WithdrawalActivity.class)))
                                .setNegativeButton("取消", null)
                                .show();
                    } else {
                        toast(message);
                        loadSubsidy(); // 可能活动刚结束或次数已用完，刷新一下
                    }
                });
            }
        });
    }

    // ================= 倒计时 =================

    private void initCountdownLabels() {
        setCountdownUnit(R.id.cd_day, "天");
        setCountdownUnit(R.id.cd_hour, "时");
        setCountdownUnit(R.id.cd_minute, "分");
        setCountdownUnit(R.id.cd_second, "秒");
    }

    private void setCountdownUnit(int boxId, String unit) {
        View box = root.findViewById(boxId);
        ((TextView) box.findViewById(R.id.tv_countdown_unit)).setText(unit);
    }

    private void setCountdownValue(int boxId, String value) {
        View box = root.findViewById(boxId);
        ((TextView) box.findViewById(R.id.tv_countdown_value)).setText(value);
    }

    private void renderCountdown(long remainingMs) {
        long totalSec = Math.max(0, remainingMs) / 1000;
        setCountdownValue(R.id.cd_day, String.valueOf(totalSec / 86400));
        setCountdownValue(R.id.cd_hour, String.format("%02d", (totalSec % 86400) / 3600));
        setCountdownValue(R.id.cd_minute, String.format("%02d", (totalSec % 3600) / 60));
        setCountdownValue(R.id.cd_second, String.format("%02d", totalSec % 60));
    }

    // ================= 菜单 =================

    private void initMenus() {
        setupMenu(R.id.row_wallet, R.drawable.ic_invite_wallet, "推广钱包", "去提现", "#F03E3E",
                v -> startActivity(new Intent(requireContext(), WithdrawalActivity.class)));

        setupMenu(R.id.row_promotion, R.drawable.ic_invite_person_add, "我的推广", "0人", "#666666",
                v -> {
                    if (!checkLogin()) return;
                    InviteListActivity.open(requireContext(), InviteListActivity.MODE_MEMBERS,
                            "共邀请 " + totalCount + " 人", coinsPerYuan);
                });

        setupMenu(R.id.row_income, R.drawable.ic_invite_income, "我的收益", "昨日收益：¥0", "#F03E3E",
                v -> {
                    if (!checkLogin()) return;
                    InviteListActivity.open(requireContext(), InviteListActivity.MODE_INCOME,
                            "累计推广收益 ¥" + coinsToYuan(totalIncomeCoins) + "（" + totalIncomeCoins + " 金币）",
                            coinsPerYuan);
                });
    }

    private boolean checkLogin() {
        if (UserManager.isLoggedIn(requireContext())) return true;
        toast("请先登录");
        return false;
    }

    private void setupMenu(int rowId, int iconRes, String title, String value, String valueColor,
                           View.OnClickListener listener) {
        View row = root.findViewById(rowId);
        ((ImageView) row.findViewById(R.id.iv_menu_icon)).setImageResource(iconRes);
        ((TextView) row.findViewById(R.id.tv_menu_title)).setText(title);
        setMenuValue(rowId, value, valueColor);
        row.setOnClickListener(listener);
    }

    private void setMenuValue(int rowId, String value, String color) {
        View row = root.findViewById(rowId);
        TextView tv = row.findViewById(R.id.tv_menu_value);
        tv.setText(value);
        tv.setTextColor(Color.parseColor(color));
    }

    // ================= 工具 =================

    /** 金币换算成元，整数不带小数点，其他保留两位 */
    private String coinsToYuan(long coins) {
        double v = coins / (double) coinsPerYuan;
        if (v == Math.floor(v)) return String.valueOf((long) v);
        return String.format("%.2f", v);
    }

    /** 分换算成元；alwaysTwoDecimals=false 时整数元不带小数点（用于"实际到账 7元"） */
    private String fenToYuan(long fen, boolean alwaysTwoDecimals) {
        if (!alwaysTwoDecimals && fen % 100 == 0) return String.valueOf(fen / 100);
        return String.format("%.2f", fen / 100.0);
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
