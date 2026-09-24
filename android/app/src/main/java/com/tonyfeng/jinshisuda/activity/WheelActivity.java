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

import com.tonyapp.djxplugin.InterstitialAdHelper;
import com.tonyapp.djxplugin.RewardAdHelper;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.view.WheelView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 幸运大转盘。
 *
 * 流程：点"点击抽奖" → 先放激励视频 → 【完整看完】才调 /draw
 *      → 服务端扣次数、按权重定奖品、当场把金币打进余额
 *      → 用户关掉广告回到本页，转盘才开始转 → 减速停在中奖格 → 弹结果弹窗
 *      → 关掉弹窗后再弹一个插屏广告
 *
 * 【时序坑】穿山甲的 onRewardArrived 是"视频播完、奖励校验通过"就回调，
 * 这时候广告页还盖在最上面，用户根本看不见我们的界面。
 * 在那里直接转盘子的话，转完了用户才关广告，回来只看到一个已经停住的转盘。
 * 所以这里用 onResume 当作"用户真的回到本页了"的信号：广告没关掉之前只发请求、
 * 把结果存着，回到页面再开转、再弹窗。
 *
 * 广告没看完（跳过/中途退出）：不调 /draw，不扣次数，转盘不转，什么都不发。
 * 抽奖结果和金额全部由服务端决定，客户端只负责转动画，改本地没用。
 */
public class WheelActivity extends AppCompatActivity {

    private WheelView wheelView;
    private TextView tvChances;
    private TextView tvRules;
    private TextView btnSpin;

    /** 正在走"看广告 → 抽奖 → 转动"这一整套，期间不接受再次点击 */
    private boolean busy = false;
    /** 本页是否在前台。广告页盖着的时候是 false，那期间不做任何动画和弹窗 */
    private boolean resumed = false;
    /** 广告已看完、正在等 /draw 返回 */
    private boolean waitingDraw = false;
    /** 结果比用户先回来时先存着，等回到页面再转、再弹窗；-1 表示没有 */
    private int pendingPrizeIndex = -1;
    private int pendingCoin = 0;
    /** 广告页盖着时抽奖失败了，回到页面再提示 */
    private String pendingError = null;
    private boolean enabled = true;
    private int chancesLeft = 0;
    private int adChanceLeft = 0;
    private boolean adChanceEnabled = false;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(R.layout.activity_wheel);

        wheelView = findViewById(R.id.wheel_view);
        tvChances = findViewById(R.id.tv_wheel_chances);
        tvRules = findViewById(R.id.tv_wheel_rules);
        btnSpin = findViewById(R.id.btn_wheel_spin);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());
        findViewById(R.id.btn_wheel_records).setOnClickListener(v -> showRecords());
        btnSpin.setOnClickListener(v -> onSpinClick());
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;

        if (pendingError != null) {
            // 广告页盖着的时候抽奖失败了，现在才提示得到
            String message = pendingError;
            pendingError = null;
            waitingDraw = false;
            setBusy(false);
            toast(message);
            loadInfo();
            return;
        }
        if (pendingPrizeIndex >= 0) {
            // 结果已经拿到了，用户刚关掉广告回来，这时候才开始转
            int index = pendingPrizeIndex;
            int coin = pendingCoin;
            pendingPrizeIndex = -1;
            spinAndShow(index, coin);
            return;
        }
        if (waitingDraw) {
            // 广告关得比接口返回还快，先空转着等结果
            wheelView.startFreeSpin();
            return;
        }
        if (!busy) loadInfo();
    }

    @Override
    protected void onPause() {
        super.onPause();
        resumed = false;
        // 去广告页了，别让转盘在看不见的地方空转
        wheelView.cancelSpin();
    }

    // ================= 数据 =================

    private void loadInfo() {
        String token = UserManager.getToken(this);
        ApiClient.getWheelInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> renderInfo(d));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast("转盘数据加载失败：" + message));
            }
        });
    }

    private void renderInfo(JSONObject d) {
        enabled = d.optBoolean("enabled", true);
        chancesLeft = d.optInt("chances_left", 0);
        adChanceLeft = d.optInt("ad_chance_left", 0);
        adChanceEnabled = d.optBoolean("ad_chance_enabled", false);

        List<String> labels = new ArrayList<>();
        JSONArray arr = d.optJSONArray("prizes");
        if (arr != null) {
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o != null) labels.add(o.optString("label", ""));
            }
        }
        wheelView.setLabels(labels);

        tvChances.setText("可抽奖次数" + chancesLeft);
        tvRules.setText(d.optString("rules_text", ""));
        updateSpinButton();

        // 老流程遗留的"中了还没领"的记录，进页面直接补发，不用再看一次广告
        JSONObject pending = d.optJSONObject("pending");
        if (pending != null && !busy) {
            claimLegacy(pending.optLong("record_id", 0));
        }
    }

    private void updateSpinButton() {
        if (!enabled) {
            btnSpin.setText("活动\n未开启");
            btnSpin.setAlpha(0.6f);
            return;
        }
        if (busy) {
            btnSpin.setText("抽奖中");
            btnSpin.setAlpha(0.6f);
            return;
        }
        btnSpin.setAlpha(1f);
        if (chancesLeft > 0) {
            btnSpin.setText("点击\n抽奖");
        } else if (adChanceEnabled && adChanceLeft > 0) {
            btnSpin.setText("看视频\n得次数");
        } else {
            btnSpin.setText("次数\n已用完");
        }
    }

    private void setBusy(boolean value) {
        busy = value;
        updateSpinButton();
    }

    // ================= 抽奖：先看广告，看完才转 =================

    private void onSpinClick() {
        if (busy) return;
        if (!enabled) {
            toast("活动未开启");
            return;
        }
        if (chancesLeft <= 0) {
            if (adChanceEnabled && adChanceLeft > 0) {
                watchAdForChance();
            } else {
                toast("今日抽奖次数已用完，明天再来");
            }
            return;
        }

        setBusy(true);
        // 第一步：激励视频。跳过或中途退出都拿不到抽奖机会，也不扣次数。
        RewardAdHelper.loadAndShowRewardAd(this, new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                runOnUiThread(() -> {
                    // 这时候广告页多半还盖在上面，先只发请求，不碰动画
                    waitingDraw = true;
                    doDraw();
                });
            }

            @Override
            public void onRewardFail(String reason) {
                runOnUiThread(() -> {
                    setBusy(false);
                    toast(reason + "，本次不消耗次数");
                });
            }
        });
    }

    /** 第二步：广告看完了，向服务端要结果。服务端这一步就把金币发了。 */
    private void doDraw() {
        String token = UserManager.getToken(this);
        ApiClient.wheelDraw(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    int coin = d.optInt("coin", 0);
                    chancesLeft = d.optInt("chances_left", 0);
                    adChanceLeft = d.optInt("ad_chance_left", adChanceLeft);
                    tvChances.setText("可抽奖次数" + chancesLeft);

                    int index = d.optInt("prize_index", 0);
                    if (resumed) {
                        spinAndShow(index, coin);      // 用户已经回到页面了，直接转
                    } else {
                        pendingPrizeIndex = index;     // 广告还盖着，等 onResume 再转
                        pendingCoin = coin;
                    }
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    if (resumed) {
                        wheelView.stopFreeSpin();   // 抽奖失败，转盘就地停住
                        waitingDraw = false;
                        setBusy(false);
                        toast(message);
                        loadInfo();
                    } else {
                        pendingError = message;     // 广告还盖着，回到页面再提示
                    }
                });
            }
        });
    }

    /** 真正开转：从当前角度转3圈减速停在中奖格，停稳再弹结果 */
    private void spinAndShow(int index, int coin) {
        waitingDraw = false;
        wheelView.stopAt(index, () -> {
            setBusy(false);
            showResultDialog(coin);
        });
    }

    /** 次数用完后看广告换次数（后台默认关闭，开了才会走到这） */
    private void watchAdForChance() {
        setBusy(true);
        RewardAdHelper.loadAndShowRewardAd(this, new RewardAdHelper.RewardCallback() {
            @Override
            public void onRewardSuccess(int rewardAmount, String rewardName) {
                String token = UserManager.getToken(WheelActivity.this);
                ApiClient.getWheelAdChance(token, new ApiClient.ApiCallback() {
                    @Override
                    public void onSuccess(JSONObject d) {
                        runOnUiThread(() -> {
                            chancesLeft = d.optInt("chances_left", chancesLeft);
                            adChanceLeft = d.optInt("ad_chance_left", adChanceLeft);
                            tvChances.setText("可抽奖次数" + chancesLeft);
                            setBusy(false);
                            if (resumed) toast(d.optString("message", "获得1次抽奖机会"));
                        });
                    }

                    @Override
                    public void onError(String message) {
                        runOnUiThread(() -> {
                            setBusy(false);
                            toast(message);
                        });
                    }
                });
            }

            @Override
            public void onRewardFail(String reason) {
                runOnUiThread(() -> {
                    setBusy(false);
                    toast(reason);
                });
            }
        });
    }

    // ================= 结果弹窗 → 插屏 =================

    private void showResultDialog(int coin) {
        if (isFinishing() || isDestroyed()) return;

        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_wheel_result, null);
        dialog.setContentView(view);
        dialog.setCanceledOnTouchOutside(false);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }

        ((TextView) view.findViewById(R.id.tv_wheel_result_title)).setText("恭喜中奖");
        ((TextView) view.findViewById(R.id.tv_wheel_result_coins)).setText(coin + " 金币");
        ((TextView) view.findViewById(R.id.tv_wheel_result_tip))
                .setText("金币已到账\n可在福利页查看今日收益");

        view.findViewById(R.id.btn_wheel_ok).setOnClickListener(v -> {
            dialog.dismiss();
            // 弹窗关掉之后再弹插屏，不跟结果叠在一起
            if (!isFinishing() && !isDestroyed()) {
                InterstitialAdHelper.show(WheelActivity.this, null);
            }
        });

        dialog.show();
    }

    // ================= 遗留待领取记录 =================

    private void claimLegacy(long recordId) {
        if (recordId <= 0) return;
        String token = UserManager.getToken(this);
        ApiClient.wheelClaim(token, recordId, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> toast("补发上次未领取的 " + d.optInt("coin", 0) + " 金币"));
            }

            @Override
            public void onError(String message) {
                // 过期或已领过，静默处理
            }
        });
    }

    // ================= 抽奖记录 =================

    private void showRecords() {
        String token = UserManager.getToken(this);
        ApiClient.getWheelRecords(token, 1, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> renderRecords(d.optJSONArray("list")));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast(message));
            }
        });
    }

    private void renderRecords(JSONArray arr) {
        if (isFinishing() || isDestroyed()) return;

        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_wheel_records, null);
        dialog.setContentView(view);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }

        LinearLayout list = view.findViewById(R.id.layout_records_list);
        TextView empty = view.findViewById(R.id.tv_records_empty);
        list.removeAllViews();

        if (arr == null || arr.length() == 0) {
            empty.setVisibility(View.VISIBLE);
        } else {
            empty.setVisibility(View.GONE);
            LayoutInflater inflater = LayoutInflater.from(this);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o == null) continue;
                View row = inflater.inflate(R.layout.item_wheel_record, list, false);
                ((TextView) row.findViewById(R.id.tv_record_time)).setText(o.optString("time", ""));
                ((TextView) row.findViewById(R.id.tv_record_coin))
                        .setText("+" + o.optInt("coin", 0) + " 金币");

                TextView tvStatus = row.findViewById(R.id.tv_record_status);
                String status = o.optString("status", "");
                tvStatus.setText(o.optString("status_text", ""));
                if ("claimed".equals(status)) {
                    tvStatus.setTextColor(Color.parseColor("#1A7F45"));
                } else if ("pending".equals(status)) {
                    tvStatus.setTextColor(Color.parseColor("#E8261F"));
                } else {
                    tvStatus.setTextColor(Color.parseColor("#999999"));
                }
                list.addView(row);
            }
        }

        view.findViewById(R.id.btn_records_close).setOnClickListener(v -> dialog.dismiss());
        dialog.show();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (wheelView != null) wheelView.cancelSpin();
    }

    private void toast(String msg) {
        if (msg != null && !msg.isEmpty()) {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        }
    }
}
