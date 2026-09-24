package com.tonyfeng.jinshisuda.fragment;

import android.app.Dialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.tonyfeng.jinshisuda.MainActivity;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.activity.ContentActivity;
import com.tonyfeng.jinshisuda.activity.FeedbackActivity;
import com.tonyfeng.jinshisuda.activity.IncomeActivity;
import com.tonyfeng.jinshisuda.activity.SettingsActivity;
import com.tonyfeng.jinshisuda.activity.WithdrawalActivity;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.AvatarLoader;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONObject;

/**
 * "我的"页。
 * - 头部：微信头像、昵称、用户ID（可复制）、师傅ID、红包领取次数
 * - 余额卡：可提现金币、今日已赚、去提现
 * - 邀请横幅、我的好友：都跳到底部的「邀请」tab
 * - 收入明细：IncomeActivity，数据来自统一流水表 coin_logs
 * - 联系客服/意见反馈：弹QQ号，可一键复制，QQ号后台配
 * - 平台公告、隐私协议：ContentActivity，内容后台配
 * - 学习课堂：暂未开放
 * - 我的设置：SettingsActivity
 */
public class MineFragment extends Fragment {

    private View root;
    private ImageView ivAvatar;
    private TextView tvNickname;
    private TextView tvUserId;
    private TextView tvMasterId;
    private TextView tvAdCount;
    private TextView tvBalanceCoins;
    private TextView tvTodayEarned;

    private String contactQq = "";

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        root = inflater.inflate(R.layout.fragment_mine, container, false);

        ivAvatar = root.findViewById(R.id.iv_mine_avatar);
        tvNickname = root.findViewById(R.id.tv_mine_nickname);
        tvUserId = root.findViewById(R.id.tv_mine_user_id);
        tvMasterId = root.findViewById(R.id.tv_mine_master_id);
        tvAdCount = root.findViewById(R.id.tv_mine_ad_count);
        tvBalanceCoins = root.findViewById(R.id.tv_mine_balance_coins);
        tvTodayEarned = root.findViewById(R.id.tv_mine_today_earned);

        root.findViewById(R.id.btn_mine_copy_id).setOnClickListener(v -> copyUserId());
        root.findViewById(R.id.btn_mine_withdraw).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), WithdrawalActivity.class)));
        root.findViewById(R.id.layout_mine_invite_banner).setOnClickListener(v -> goInvite());

        root.findViewById(R.id.item_friends).setOnClickListener(v -> goInvite());
        root.findViewById(R.id.item_income).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), IncomeActivity.class)));
        root.findViewById(R.id.item_feedback).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), FeedbackActivity.class)));
        root.findViewById(R.id.item_course).setOnClickListener(v -> toast("学习课堂开发中"));
        root.findViewById(R.id.item_contact).setOnClickListener(v -> showContactDialog());
        root.findViewById(R.id.item_notice).setOnClickListener(v -> openContent("notice"));
        root.findViewById(R.id.item_privacy).setOnClickListener(v -> openContent("privacy"));
        root.findViewById(R.id.item_settings).setOnClickListener(v ->
                startActivity(new Intent(requireContext(), SettingsActivity.class)));

        return root;
    }

    @Override
    public void onResume() {
        super.onResume();
        loadProfile();
        loadConfig();
    }

    @Override
    public void onHiddenChanged(boolean hidden) {
        super.onHiddenChanged(hidden);
        if (!hidden) {
            loadProfile();
            loadConfig();
        }
    }

    // ================= 数据 =================

    private void loadProfile() {
        if (!isAdded()) return;
        if (!UserManager.isLoggedIn(requireContext())) {
            AvatarLoader.load(ivAvatar, "", "未登录");
            tvNickname.setText("未登录");
            tvUserId.setText("用户ID：--");
            tvMasterId.setText("师傅ID：--");
            tvAdCount.setText("0");
            tvBalanceCoins.setText("0");
            tvTodayEarned.setText("0.0");
            return;
        }
        String token = UserManager.getToken(requireContext());
        ApiClient.getMyProfile(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUi(() -> renderProfile(d));
            }

            @Override
            public void onError(String message) {
                runOnUi(() -> toast("加载失败：" + message));
            }
        });
    }

    private void renderProfile(JSONObject d) {
        String nickname = d.optString("nickname", "用户");
        // 头像为空（老用户还没用新版本登录过）时自动显示昵称首字的彩色圆
        AvatarLoader.load(ivAvatar, d.optString("avatar_url", ""), nickname);
        tvNickname.setText(nickname);
        tvUserId.setText("用户ID：" + d.optInt("user_id", 0));

        int masterId = d.optInt("master_id", 0);
        tvMasterId.setText(masterId > 0 ? "师傅ID：" + masterId : "师傅ID：无");

        tvAdCount.setText(String.valueOf(d.optInt("ad_watch_count", 0)));
        tvBalanceCoins.setText(String.valueOf(d.optLong("coin_balance", 0)));
        tvTodayEarned.setText(String.format("%.2f", d.optDouble("today_earned_yuan", 0)));
    }

    /** 客服QQ在后台配，进页面就拉一次存着，点客服时直接弹 */
    private void loadConfig() {
        ApiClient.getAppConfig(new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                contactQq = d.optString("contact_qq", "");
            }

            @Override
            public void onError(String message) {
                // 静默失败，点客服时再提示
            }
        });
    }

    // ================= 交互 =================

    private void goInvite() {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).switchToInvite();
        }
    }

    private void copyUserId() {
        String text = tvUserId.getText().toString().replace("用户ID：", "").trim();
        if (text.isEmpty() || "--".equals(text)) {
            toast("还没登录");
            return;
        }
        copyToClipboard(text);
        toast("用户ID已复制");
    }

    private void copyToClipboard(String text) {
        if (!isAdded()) return;
        ClipboardManager cm = (ClipboardManager) requireContext()
                .getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) {
            cm.setPrimaryClip(ClipData.newPlainText("text", text));
        }
    }

    private void showContactDialog() {
        if (!isAdded()) return;
        if (contactQq == null || contactQq.isEmpty()) {
            toast("客服信息加载中，请稍后再试");
            loadConfig();
            return;
        }

        Dialog dialog = new Dialog(requireContext());
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(requireContext()).inflate(R.layout.dialog_contact, null);
        dialog.setContentView(view);
        if (dialog.getWindow() != null) {
            android.view.Window w = dialog.getWindow();
            w.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            // 左右满屏平铺、贴底弹出，像个底部弹层
            w.setLayout(android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
            w.setGravity(android.view.Gravity.BOTTOM);
        }

        ((TextView) view.findViewById(R.id.tv_contact_qq)).setText(contactQq);
        view.findViewById(R.id.btn_contact_copy).setOnClickListener(v -> {
            copyToClipboard(contactQq);
            toast("QQ号已复制，去QQ添加好友吧");
            dialog.dismiss();
        });
        view.findViewById(R.id.btn_contact_close).setOnClickListener(v -> dialog.dismiss());

        dialog.show();
    }

    private void openContent(String key) {
        Intent intent = new Intent(requireContext(), ContentActivity.class);
        intent.putExtra(ContentActivity.EXTRA_KEY, key);
        startActivity(intent);
    }

    // ================= 工具 =================

    private void runOnUi(Runnable r) {
        if (!isAdded()) return;
        requireActivity().runOnUiThread(() -> {
            if (isAdded()) r.run();
        });
    }

    private void toast(String msg) {
        if (isAdded() && msg != null && !msg.isEmpty()) {
            Toast.makeText(requireContext(), msg, Toast.LENGTH_SHORT).show();
        }
    }
}
