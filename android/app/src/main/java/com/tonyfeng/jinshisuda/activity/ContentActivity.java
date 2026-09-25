package com.tonyfeng.jinshisuda.activity;

import android.os.Bundle;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;

import org.json.JSONObject;

/**
 * 图文页：平台公告 / 隐私政策 / 用户协议。
 * 内容在后台 /admin/content 维护，改完用户重进页面就能看到，不用发版。
 * 后台没填就显示"暂无内容"。
 */
public class ContentActivity extends AppCompatActivity {

    public static final String EXTRA_KEY = "content_key";

    private TextView tvTitle;
    private TextView tvContent;
    private TextView tvEmpty;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_content);

        tvTitle = findViewById(R.id.tv_content_title);
        tvContent = findViewById(R.id.tv_content_body);
        tvEmpty = findViewById(R.id.tv_content_empty);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());

        String key = getIntent().getStringExtra(EXTRA_KEY);
        if (key == null || key.isEmpty()) key = "notice";

        // 先按 key 摆个标题，接口回来再用服务端的标题覆盖，避免打开时标题是空的
        tvTitle.setText(defaultTitle(key));
        load(key);
    }

    private String defaultTitle(String key) {
        switch (key) {
            case "privacy":
                return "隐私政策";
            case "agreement":
                return "用户协议";
            default:
                return "平台公告";
        }
    }

    private void load(String key) {
        ApiClient.getAppContent(key, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    tvTitle.setText(d.optString("title", tvTitle.getText().toString()));
                    String content = d.optString("content", "");
                    // 后台没填内容就展示空白页，不再显示“暂无内容”
                    tvContent.setText(content);
                    tvContent.setVisibility(View.VISIBLE);
                    tvEmpty.setVisibility(View.GONE);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    tvContent.setVisibility(View.GONE);
                    tvEmpty.setVisibility(View.VISIBLE);
                    tvEmpty.setText("内容加载失败，请稍后再试");
                    Toast.makeText(ContentActivity.this, message, Toast.LENGTH_SHORT).show();
                });
            }
        });
    }
}
