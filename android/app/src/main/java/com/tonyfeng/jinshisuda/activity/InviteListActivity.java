package com.tonyfeng.jinshisuda.activity;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.DividerItemDecoration;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 邀请相关列表页，两种模式：
 * - members：我的推广（我邀请的人 + 每人贡献）
 * - income：我的收益（返利流水）
 */
public class InviteListActivity extends AppCompatActivity {

    public static final String MODE_MEMBERS = "members";
    public static final String MODE_INCOME = "income";

    private static final String EXTRA_MODE = "mode";
    private static final String EXTRA_HEADER = "header";
    private static final String EXTRA_COINS_PER_YUAN = "coins_per_yuan";

    public static void open(Context context, String mode, String header, long coinsPerYuan) {
        Intent intent = new Intent(context, InviteListActivity.class);
        intent.putExtra(EXTRA_MODE, mode);
        intent.putExtra(EXTRA_HEADER, header);
        intent.putExtra(EXTRA_COINS_PER_YUAN, coinsPerYuan);
        context.startActivity(intent);
    }

    private String mode;
    private long coinsPerYuan;
    private int page = 1;
    private boolean loading = false;

    private TextView tvEmpty;
    private TextView btnLoadMore;
    private final RowAdapter adapter = new RowAdapter();

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            finish();
            return;
        }
        setContentView(R.layout.activity_invite_list);

        mode = getIntent().getStringExtra(EXTRA_MODE);
        if (mode == null) mode = MODE_MEMBERS;
        coinsPerYuan = getIntent().getLongExtra(EXTRA_COINS_PER_YUAN, 100000);
        if (coinsPerYuan <= 0) coinsPerYuan = 100000;

        ((TextView) findViewById(R.id.tv_list_title))
                .setText(MODE_INCOME.equals(mode) ? "我的收益" : "我的推广");
        String header = getIntent().getStringExtra(EXTRA_HEADER);
        ((TextView) findViewById(R.id.tv_list_header)).setText(header == null ? "" : header);

        tvEmpty = findViewById(R.id.tv_list_empty);
        btnLoadMore = findViewById(R.id.btn_load_more);
        btnLoadMore.setOnClickListener(v -> load());

        RecyclerView rv = findViewById(R.id.rv_list);
        rv.setLayoutManager(new LinearLayoutManager(this));
        rv.addItemDecoration(new DividerItemDecoration(this, DividerItemDecoration.VERTICAL));
        rv.setAdapter(adapter);

        load();
    }

    private void load() {
        if (loading) return;
        loading = true;
        btnLoadMore.setText("加载中…");

        String token = UserManager.getToken(this);
        ApiClient.ApiCallback callback = new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                List<Row> rows = parse(data.optJSONArray("list"));
                boolean hasMore = data.optBoolean("has_more", false);
                runOnUiThread(() -> {
                    loading = false;
                    page++;
                    adapter.append(rows);
                    btnLoadMore.setText("加载更多");
                    btnLoadMore.setVisibility(hasMore ? View.VISIBLE : View.GONE);
                    if (adapter.getItemCount() == 0) {
                        tvEmpty.setText(MODE_INCOME.equals(mode)
                                ? "还没有收益，邀请好友看广告就有返利"
                                : "还没有邀请好友");
                        tvEmpty.setVisibility(View.VISIBLE);
                    } else {
                        tvEmpty.setVisibility(View.GONE);
                    }
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    loading = false;
                    btnLoadMore.setText("加载更多");
                    if (adapter.getItemCount() == 0) {
                        tvEmpty.setText("加载失败：" + message);
                    } else {
                        Toast.makeText(InviteListActivity.this, message, Toast.LENGTH_SHORT).show();
                    }
                });
            }
        };

        if (MODE_INCOME.equals(mode)) {
            ApiClient.getInviteIncome(token, page, callback);
        } else {
            ApiClient.getInviteMembers(token, page, callback);
        }
    }

    private List<Row> parse(JSONArray arr) {
        List<Row> rows = new ArrayList<>();
        if (arr == null) return rows;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            if (MODE_INCOME.equals(mode)) {
                long coins = o.optLong("coin_amount", 0);
                rows.add(new Row(
                        "来自 " + o.optString("from_nickname", ""),
                        o.optString("created_at", ""),
                        "+" + coins + " 金币"));
            } else {
                long coins = o.optLong("contributed_coins", 0);
                rows.add(new Row(
                        o.optString("nickname", "") + "（ID " + o.optLong("user_id") + "）",
                        "加入时间 " + o.optString("joined_at", ""),
                        "贡献 ¥" + yuan(coins)));
            }
        }
        return rows;
    }

    private String yuan(long coins) {
        return String.format("%.2f", coins / (double) coinsPerYuan);
    }

    // ---------------- 列表 ----------------

    static class Row {
        final String title, subtitle, value;

        Row(String title, String subtitle, String value) {
            this.title = title;
            this.subtitle = subtitle;
            this.value = value;
        }
    }

    static class RowAdapter extends RecyclerView.Adapter<RowAdapter.VH> {
        private final List<Row> data = new ArrayList<>();

        void append(List<Row> rows) {
            int start = data.size();
            data.addAll(rows);
            notifyItemRangeInserted(start, rows.size());
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.item_invite_list, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH h, int position) {
            Row r = data.get(position);
            h.title.setText(r.title);
            h.subtitle.setText(r.subtitle);
            h.value.setText(r.value);
        }

        @Override
        public int getItemCount() {
            return data.size();
        }

        static class VH extends RecyclerView.ViewHolder {
            final TextView title, subtitle, value;

            VH(@NonNull View v) {
                super(v);
                title = v.findViewById(R.id.tv_item_title);
                subtitle = v.findViewById(R.id.tv_item_subtitle);
                value = v.findViewById(R.id.tv_item_value);
            }
        }
    }
}