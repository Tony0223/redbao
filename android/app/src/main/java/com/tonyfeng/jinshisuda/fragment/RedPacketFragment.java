package com.tonyfeng.jinshisuda.fragment;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.bytedance.sdk.openadsdk.TTFeedAd;
import com.tonyapp.djxplugin.NativeAdHelper;
import com.tonyapp.djxplugin.RewardAdHelper;
import com.tonyapp.djxplugin.redpacket.RedPacketAdapter;
import com.tonyapp.djxplugin.redpacket.RedPacketItem;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class RedPacketFragment extends Fragment {

    private static final int INTERVAL_MIN_MS = 2000;
    private static final int INTERVAL_MAX_MS = 3000;

    private final List<RedPacketItem> dataList = new ArrayList<>();
    private RedPacketAdapter adapter;
    private RecyclerView recyclerView;
    private TextView tvCoin;
    private int coinBalance = 0;

    public static volatile int sCoinBalance = 0;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Random random = new Random();

    private int adThreshold = 3 + random.nextInt(3);
    private int messagesSinceAd = 0;
    private boolean isLoadingAd = false;

    private static final String[] NICKNAMES = {"GSS", "LP", "HZQ", "过来人", "小明", "阿珍", "老王", "神不是李超"};
    private static final String[] TEXT_MESSAGES = {
            "没抢到一个红包，感觉自己又年轻一岁",
            "抢到红包那一刻，激动地睡不着",
            "手速太慢了，眼睁睁看着红包被抢光",
            "这个群福利真不错，天天都有红包",
            "刚才抢了一个大的，开心！"
    };

    private final Runnable spawnRunnable = new Runnable() {
        @Override
        public void run() {
            spawnNewItem();
            int nextDelay = INTERVAL_MIN_MS + random.nextInt(INTERVAL_MAX_MS - INTERVAL_MIN_MS);
            handler.postDelayed(this, nextDelay);
        }
    };

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                              @Nullable Bundle savedInstanceState) {

        LinearLayout root = new LinearLayout(requireContext());
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT));
        // 群聊背景用微信那种浅灰，别用红色（红包本来就红，再红底太冲）
        root.setBackgroundColor(0xFFEDEDED);

        LinearLayout topBar = new LinearLayout(requireContext());
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setPadding(24, 24, 24, 24);
        topBar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        topBar.setBackgroundColor(0xFFFFFFFF);   // 群聊标题栏白底
        topBar.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        tvCoin = new TextView(requireContext());
        tvCoin.setText("金币: 0");
        tvCoin.setTextColor(0xFF333333);
        tvCoin.setTextSize(16);
        LinearLayout.LayoutParams coinParams = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        tvCoin.setLayoutParams(coinParams);

        TextView tvWithdraw = new TextView(requireContext());
        tvWithdraw.setText("提现");
        tvWithdraw.setTextColor(0xFFE64A3B);
        tvWithdraw.setTextSize(16);
        tvWithdraw.setPadding(24, 8, 24, 8);
        tvWithdraw.setOnClickListener(v ->
                startActivity(new android.content.Intent(requireContext(),
                        com.tonyfeng.jinshisuda.activity.WithdrawalActivity.class)));

        topBar.addView(tvCoin);
        topBar.addView(tvWithdraw);

        recyclerView = new RecyclerView(requireContext());
        recyclerView.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        LinearLayoutManager layoutManager = new LinearLayoutManager(requireContext());
        layoutManager.setStackFromEnd(true);
        recyclerView.setLayoutManager(layoutManager);

        adapter = new RedPacketAdapter(dataList, this::onRedPacketClicked);
        recyclerView.setAdapter(adapter);

        root.addView(topBar);
        root.addView(recyclerView);

        spawnNewItem();
        spawnNewItem();

        return root;
    }

    private boolean hasCheckedLogin = false;
    @Override
    public void onResume() {
        super.onResume();
        handler.postDelayed(spawnRunnable, INTERVAL_MIN_MS);
        // 只在第一次真正可见时检查登录
        if (!hasCheckedLogin) {
            hasCheckedLogin = true;
            checkLoginAndRefreshBalance();
        }
    }

    @Override
    public void onHiddenChanged(boolean hidden) {
        super.onHiddenChanged(hidden);
        if (!hidden) {
            // 从其他 tab 切回来
            hasCheckedLogin = false; // 允许再次检查
            checkLoginAndRefreshBalance();
        }
    }

    private void checkLoginAndRefreshBalance() {
        UserManager.ensureLoggedIn(requireContext(), () -> {
            String token = UserManager.getToken(requireContext());
            if (token == null) return;
            ApiClient.getUserBalance(token, new ApiClient.ApiCallback() {
                @Override
                public void onSuccess(JSONObject data) {
                    if (!isAdded()) return;
                    requireActivity().runOnUiThread(() -> {
                        if (!isAdded()) return;
                        try {
                            coinBalance = data.getInt("coin_balance");
                            tvCoin.setText("金币: " + coinBalance);
                        } catch (JSONException ignored) {
                        }
                    });
                }

                @Override
                public void onError(String message) {
                    // 拉取余额失败不影响其他功能，静默处理
                }
            });
        });
    }

    @Override
    public void onPause() {
        super.onPause();
        handler.removeCallbacks(spawnRunnable);
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        handler.removeCallbacksAndMessages(null);
    }

    private void spawnNewItem() {
        String nickname = NICKNAMES[random.nextInt(NICKNAMES.length)];
        RedPacketItem item;
        if (random.nextBoolean()) {
            item = RedPacketItem.newRedPacket(nickname);
        } else {
            String text = TEXT_MESSAGES[random.nextInt(TEXT_MESSAGES.length)];
            item = RedPacketItem.newText(nickname, text);
        }
        dataList.add(item);
        adapter.notifyItemInserted(dataList.size() - 1);
        recyclerView.scrollToPosition(dataList.size() - 1);

        maybeInsertAd();
    }

    private void maybeInsertAd() {
        messagesSinceAd++;
        if (messagesSinceAd >= adThreshold && !isLoadingAd) {
            isLoadingAd = true;
            NativeAdHelper.loadFeedAd(requireActivity(), new NativeAdHelper.NativeAdCallback() {
                @Override
                public void onAdReady(TTFeedAd feedAd, View adView) {
                    if (!isAdded()) return;
                    requireActivity().runOnUiThread(() -> {
                        if (!isAdded()) return;
                        RedPacketItem adItem = RedPacketItem.newAd(adView);
                        dataList.add(adItem);
                        adapter.notifyItemInserted(dataList.size() - 1);
                        recyclerView.scrollToPosition(dataList.size() - 1);
                        messagesSinceAd = 0;
                        adThreshold = 3 + random.nextInt(3);
                        isLoadingAd = false;
                    });
                }

                @Override
                public void onAdFail(String reason) {
                    isLoadingAd = false;
                    messagesSinceAd = 0;
                }
            });
        }
    }

    private void onRedPacketClicked(RedPacketItem item, int position) {
        String token = UserManager.getToken(requireContext());
        if (token == null) {
            Toast.makeText(requireContext(), "请先登录", Toast.LENGTH_SHORT).show();
            return;
        }

        RewardAdHelper.loadAndShowRewardAd(requireActivity(), new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                // 不再本地随便发固定金币，改成上报服务端，由服务端按规则算真实奖励
                ApiClient.reportAdReward(token, "reward_video", false, new ApiClient.ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject data) {
                        if (!isAdded()) return;
                        requireActivity().runOnUiThread(() -> {
                            if (!isAdded()) return;
                            try {
                                int totalThisTime = data.getInt("total_this_time");
                                int newBalance = data.getInt("new_balance");
                                item.opened = true;
                                coinBalance = newBalance;
                                sCoinBalance = coinBalance;
                                tvCoin.setText("金币: " + coinBalance);
                                if (position >= 0 && position < dataList.size()) {
                                    adapter.notifyItemChanged(position);
                                }
                                Toast.makeText(requireContext(),
                                        "恭喜获得" + totalThisTime + "金币", Toast.LENGTH_SHORT).show();
                            } catch (JSONException e) {
                                Toast.makeText(requireContext(), "结算异常，请稍后重试", Toast.LENGTH_SHORT).show();
                            }
                        });
                    }

                    @Override
                    public void onError(String message) {
                        if (!isAdded()) return;
                        requireActivity().runOnUiThread(() ->
                                Toast.makeText(requireContext(), "结算失败：" + message, Toast.LENGTH_SHORT).show());
                    }
                });
            }

            @Override
            public void onRewardFail(String reason) {
                if (!isAdded()) return;
                requireActivity().runOnUiThread(() ->
                        Toast.makeText(requireContext(), "未获得奖励：" + reason, Toast.LENGTH_SHORT).show());
            }
        });
    }
}
