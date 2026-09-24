package com.tonyfeng.jinshisuda.activity;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 收入明细。数据来自服务端统一流水表 coin_logs，
 * 看广告、徒弟返利、签到、打卡、福利活动、转盘的入账都在这一个列表里。
 * 滑到底自动加载下一页，每页20条。
 */
public class IncomeActivity extends AppCompatActivity {

    private ScrollView scrollView;
    private LinearLayout listContainer;
    private TextView tvTotal;
    private TextView tvEmpty;
    private TextView tvFooter;

    private int page = 1;
    private boolean loading = false;
    private boolean hasMore = true;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(R.layout.activity_income);

        scrollView = findViewById(R.id.scroll_income);
        listContainer = findViewById(R.id.layout_income_list);
        tvTotal = findViewById(R.id.tv_income_total);
        tvEmpty = findViewById(R.id.tv_income_empty);
        tvFooter = findViewById(R.id.tv_income_footer);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());

        // 滑到底部自动加载下一页
        scrollView.getViewTreeObserver().addOnScrollChangedListener(() -> {
            View child = scrollView.getChildAt(0);
            if (child == null) return;
            int bottomGap = child.getBottom() - (scrollView.getHeight() + scrollView.getScrollY());
            if (bottomGap <= 80 && hasMore && !loading) {
                loadPage(page + 1);
            }
        });

        loadPage(1);
    }

    private void loadPage(int target) {
        if (loading) return;
        loading = true;
        if (target > 1) tvFooter.setText("加载中…");

        String token = UserManager.getToken(this);
        ApiClient.getCoinLogs(token, target, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    loading = false;
                    page = target;
                    render(d, target == 1);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    loading = false;
                    tvFooter.setText("加载失败，上滑重试");
                    toast(message);
                });
            }
        });
    }

    private void render(JSONObject d, boolean reset) {
        if (reset) {
            listContainer.removeAllViews();
            long total = d.optLong("total_income_coins", 0);
            tvTotal.setText(String.format("%,d", total));
        }

        JSONArray arr = d.optJSONArray("list");
        hasMore = d.optBoolean("has_more", false);

        if (arr == null || arr.length() == 0) {
            if (reset) {
                tvEmpty.setVisibility(View.VISIBLE);
                tvFooter.setText("");
            } else {
                tvFooter.setText("没有更多了");
            }
            return;
        }
        tvEmpty.setVisibility(View.GONE);

        LayoutInflater inflater = LayoutInflater.from(this);
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            View row = inflater.inflate(R.layout.item_income, listContainer, false);

            ((TextView) row.findViewById(R.id.tv_income_source))
                    .setText(o.optString("source_text", "收入"));

            TextView tvRemark = row.findViewById(R.id.tv_income_remark);
            String remark = o.optString("remark", "");
            tvRemark.setText(remark);
            tvRemark.setVisibility(remark.isEmpty() ? View.GONE : View.VISIBLE);

            ((TextView) row.findViewById(R.id.tv_income_time)).setText(o.optString("time", ""));

            long coins = o.optLong("coins", 0);
            TextView tvCoins = row.findViewById(R.id.tv_income_coins);
            tvCoins.setText((coins > 0 ? "+" : "") + String.format("%,d", coins));

            listContainer.addView(row);
        }

        tvFooter.setText(hasMore ? "上滑加载更多" : "没有更多了");
    }

    private void toast(String msg) {
        if (msg != null && !msg.isEmpty()) {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        }
    }
}
