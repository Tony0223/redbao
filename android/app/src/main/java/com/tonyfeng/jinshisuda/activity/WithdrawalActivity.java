package com.tonyfeng.jinshisuda.activity;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.adapter.WithdrawalRecordAdapter;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.api.WeChatTransferAuth;
import com.tonyfeng.jinshisuda.model.WithdrawalRecord;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class WithdrawalActivity extends AppCompatActivity {

    // 从后端 /api/withdrawal/info 读取，这里只是加载完成前的默认值
    private long minCoins = 500000;
    private long coinsPerYuan = 100000;

    private LinearLayout layoutAuth;
    private TextView tvAuthStatus;
    private Button btnAuth;
    private TextView tvBalance;
    private EditText etAmount;
    private TextView tvHint;
    private Button btnSubmit;
    private TextView tvEmpty;
    private RecyclerView rvRecords;
    private WithdrawalRecordAdapter adapter;

    private long currentBalance = -1;     // -1 表示还没加载到
    private Boolean authorized = null;    // null 表示状态未知（还没查到或查询失败）

    // 刚从微信授权页回来时，微信服务端状态可能有一两秒延迟，没查到已授权就隔2秒再查几次
    private boolean waitingForAuthResult = false;
    private int authRecheckCount = 0;
    private static final int AUTH_RECHECK_MAX = 3;
    private static final long AUTH_RECHECK_DELAY_MS = 2000;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        setContentView(R.layout.activity_withdrawal);

        layoutAuth = findViewById(R.id.layout_auth);
        tvAuthStatus = findViewById(R.id.tv_auth_status);
        btnAuth = findViewById(R.id.btn_auth);
        tvBalance = findViewById(R.id.tv_balance);
        etAmount = findViewById(R.id.et_amount);
        tvHint = findViewById(R.id.tv_hint);
        btnSubmit = findViewById(R.id.btn_submit);
        tvEmpty = findViewById(R.id.tv_empty);
        rvRecords = findViewById(R.id.rv_records);

        adapter = new WithdrawalRecordAdapter();
        rvRecords.setLayoutManager(new LinearLayoutManager(this));
        rvRecords.setAdapter(adapter);

        btnAuth.setOnClickListener(v -> doAuth());
        btnSubmit.setOnClickListener(v -> doSubmit());
        renderHint();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (UserManager.isLoggedIn(this)) {
            // 从微信授权页返回、从后台切回来，都会走这里重新查一遍
            loadInfo();
            loadBalance();
            loadRecords();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        handler.removeCallbacksAndMessages(null);
    }

    // ---------------- 网络 ----------------

    private void loadInfo() {
        String token = UserManager.getToken(this);
        ApiClient.getWithdrawalInfo(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                boolean isAuthorized = data.optBoolean("authorized", false);
                String authState = data.optString("auth_state", "NONE");
                long min = data.optLong("min_withdraw_coins", minCoins);
                long rate = data.optLong("coins_per_yuan", coinsPerYuan);
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    authorized = isAuthorized;
                    minCoins = min;
                    coinsPerYuan = rate > 0 ? rate : coinsPerYuan;
                    renderAuth(authState);
                    renderHint();
                    renderBalance();
                    scheduleAuthRecheckIfNeeded();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    authorized = null;
                    tvAuthStatus.setText("绑定状态查询失败，点这里重试");
                    layoutAuth.setOnClickListener(v -> loadInfo());
                    btnAuth.setVisibility(View.GONE);
                    btnSubmit.setEnabled(false);
                });
            }
        });
    }

    private void loadBalance() {
        String token = UserManager.getToken(this);
        ApiClient.getUserBalance(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                long bal = data.optLong("coin_balance", 0);
                runOnUiThread(() -> {
                    currentBalance = bal;
                    renderBalance();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> tvBalance.setText("余额加载失败"));
            }
        });
    }

    private void loadRecords() {
        String token = UserManager.getToken(this);
        ApiClient.getWithdrawalList(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                List<WithdrawalRecord> list = parse(data.optJSONArray("list"));
                runOnUiThread(() -> render(list));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    adapter.setData(new ArrayList<>());
                    tvEmpty.setText("记录加载失败：" + message);
                    tvEmpty.setVisibility(View.VISIBLE);
                    rvRecords.setVisibility(View.GONE);
                });
            }
        });
    }

    /** 点"绑定微信收款"：向后端要授权参数，然后拉起微信授权页 */
    private void doAuth() {
        btnAuth.setEnabled(false);
        String token = UserManager.getToken(this);
        ApiClient.applyWithdrawalAuth(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                if (data.optBoolean("authorized", false)) {
                    // 服务端发现其实已经绑定过了，直接刷新
                    runOnUiThread(() -> {
                        btnAuth.setEnabled(true);
                        loadInfo();
                    });
                    return;
                }
                String mchId = data.optString("mch_id", "");
                String appId = data.optString("app_id", "");
                String pkg = data.optString("package", "");
                runOnUiThread(() -> {
                    btnAuth.setEnabled(true);
                    if (mchId.isEmpty() || appId.isEmpty() || pkg.isEmpty()) {
                        toast("获取授权信息失败，请稍后重试");
                        return;
                    }
                    WeChatTransferAuth.Result result =
                            WeChatTransferAuth.launch(WithdrawalActivity.this, mchId, appId, pkg);
                    switch (result) {
                        case OK:
                            waitingForAuthResult = true;
                            authRecheckCount = 0;
                            break;
                        case WECHAT_NOT_INSTALLED:
                            toast("请先安装微信");
                            break;
                        case WECHAT_TOO_OLD:
                            toast("微信版本过低，请升级微信后再试");
                            break;
                        default:
                            toast("拉起微信失败，请重试");
                            break;
                    }
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    btnAuth.setEnabled(true);
                    toast(message);
                });
            }
        });
    }

    private void doSubmit() {
        if (!Boolean.TRUE.equals(authorized)) {
            toast("请先绑定微信收款");
            return;
        }
        String s = etAmount.getText().toString().trim();
        if (s.isEmpty()) {
            toast("请输入提现金币数");
            return;
        }
        long coins;
        try {
            coins = Long.parseLong(s);
        } catch (NumberFormatException e) {
            toast("金额格式不对");
            return;
        }
        if (coins < minCoins) {
            toast("最低提现 " + minCoins + " 金币（" + yuan(minCoins) + "元）");
            return;
        }
        if (currentBalance >= 0 && coins > currentBalance) {
            toast("余额不足");
            return;
        }
        if (coins > Integer.MAX_VALUE) {
            toast("金额过大");
            return;
        }

        btnSubmit.setEnabled(false);
        String token = UserManager.getToken(this);
        ApiClient.requestWithdrawal(token, (int) coins, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                runOnUiThread(() -> {
                    btnSubmit.setEnabled(true);
                    etAmount.setText("");
                    toast("提现申请已提交，审核通过后自动到账微信零钱");
                    loadBalance();
                    loadRecords();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    btnSubmit.setEnabled(true);
                    Toast.makeText(WithdrawalActivity.this, "提交失败：" + message, Toast.LENGTH_LONG).show();
                    loadInfo(); // 可能是绑定失效了，顺便刷新一下绑定状态
                });
            }
        });
    }

    // ---------------- 渲染 ----------------

    private void renderAuth(String authState) {
        layoutAuth.setOnClickListener(null);
        if (Boolean.TRUE.equals(authorized)) {
            tvAuthStatus.setText("✓ 已绑定微信零钱，审核通过后自动到账");
            btnAuth.setVisibility(View.GONE);
            btnSubmit.setEnabled(true);
            return;
        }
        btnSubmit.setEnabled(false);
        btnAuth.setVisibility(View.VISIBLE);
        if ("WAIT_USER_CONFIRM".equals(authState)) {
            tvAuthStatus.setText(waitingForAuthResult
                    ? "正在确认授权结果…"
                    : "绑定还没完成，请点下方按钮在微信里确认");
            btnAuth.setText("继续绑定");
        } else {
            tvAuthStatus.setText("首次提现需要绑定微信零钱收款（只需绑定一次）");
            btnAuth.setText("绑定微信收款");
        }
    }

    /** 刚从授权页回来但还没查到已授权：隔2秒再查，最多3次 */
    private void scheduleAuthRecheckIfNeeded() {
        if (!waitingForAuthResult) return;
        if (Boolean.TRUE.equals(authorized)) {
            waitingForAuthResult = false;
            toast("微信收款绑定成功");
            return;
        }
        if (authRecheckCount >= AUTH_RECHECK_MAX) {
            waitingForAuthResult = false;
            renderAuth("WAIT_USER_CONFIRM");
            return;
        }
        authRecheckCount++;
        handler.postDelayed(this::loadInfo, AUTH_RECHECK_DELAY_MS);
    }

    private void renderBalance() {
        if (currentBalance < 0) return;
        tvBalance.setText("可提现余额：" + currentBalance + " 金币  ≈ ¥" + yuan(currentBalance));
    }

    private void renderHint() {
        tvHint.setText("最低 " + minCoins + " 金币（" + yuan(minCoins) + "元）起提，"
                + coinsPerYuan + " 金币 = 1 元");
    }

    private List<WithdrawalRecord> parse(JSONArray arr) {
        List<WithdrawalRecord> list = new ArrayList<>();
        if (arr == null) return list;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject item = arr.optJSONObject(i);
            if (item == null) continue;
            long coinAmount = item.optLong("coin_amount", 0);
            long yuanFen = item.optLong("yuan_amount", 0);     // 提现金额，单位分
            long subsidyFen = item.optLong("subsidy_fen", 0);  // 平台补贴，单位分
            String status = item.optString("status", "");
            String statusText = item.optString("status_text", mapStatus(status));
            String createdAt = item.optString("created_at", "");

            String amountText = "¥" + String.format("%.2f", yuanFen / 100.0);
            if (subsidyFen > 0) {
                amountText += " + 补贴¥" + String.format("%.2f", subsidyFen / 100.0);
            }
            amountText += "（" + coinAmount + " 金币）";
            list.add(new WithdrawalRecord(amountText, statusText, status, createdAt));
        }
        return list;
    }

    private void render(List<WithdrawalRecord> list) {
        if (list.isEmpty()) {
            tvEmpty.setText("暂无提现记录");
            tvEmpty.setVisibility(View.VISIBLE);
            rvRecords.setVisibility(View.GONE);
        } else {
            tvEmpty.setVisibility(View.GONE);
            rvRecords.setVisibility(View.VISIBLE);
            adapter.setData(list);
        }
    }

    private String mapStatus(String status) {
        switch (status) {
            case "pending":     return "审核中";
            case "processing":  return "打款中";
            case "success":     return "已到账";
            case "failed":      return "打款失败";
            default:            return status;
        }
    }

    private String yuan(long coins) {
        return String.format("%.2f", coins / (double) coinsPerYuan);
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }
}