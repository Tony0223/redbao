package com.tonyfeng.jinshisuda.activity;

import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
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
 * 意见反馈。
 * - 内容必填，5~500字，带字数统计
 * - 手机号和邮箱【二选一必填】，方便客服回复
 * - 微信昵称由服务端自动带上，不用用户填
 * - 下面挂着"我的反馈"，能看到后台回复了什么
 *
 * 校验客户端做一遍是为了即时提示，服务端还会再做一遍，不能只靠客户端。
 */
public class FeedbackActivity extends AppCompatActivity {

    private static final int CONTENT_MIN = 5;
    private static final int CONTENT_MAX = 500;

    private EditText etContent;
    private EditText etPhone;
    private EditText etEmail;
    private TextView tvCounter;
    private TextView btnSubmit;
    private LinearLayout listContainer;
    private TextView tvMyEmpty;

    private boolean submitting = false;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!UserManager.isLoggedIn(this)) {
            Toast.makeText(this, "请先登录", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(R.layout.activity_feedback);

        etContent = findViewById(R.id.et_feedback_content);
        etPhone = findViewById(R.id.et_feedback_phone);
        etEmail = findViewById(R.id.et_feedback_email);
        tvCounter = findViewById(R.id.tv_feedback_counter);
        btnSubmit = findViewById(R.id.btn_feedback_submit);
        listContainer = findViewById(R.id.layout_feedback_list);
        tvMyEmpty = findViewById(R.id.tv_feedback_my_empty);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());
        btnSubmit.setOnClickListener(v -> submit());

        etContent.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int st, int c, int a) {
            }

            @Override
            public void onTextChanged(CharSequence s, int st, int b, int c) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                tvCounter.setText(s.length() + "/" + CONTENT_MAX);
            }
        });
        tvCounter.setText("0/" + CONTENT_MAX);
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadMyFeedback();
    }

    // ================= 提交 =================

    private void submit() {
        if (submitting) return;

        String content = etContent.getText().toString().trim();
        String phone = etPhone.getText().toString().trim();
        String email = etEmail.getText().toString().trim();

        if (content.length() < CONTENT_MIN) {
            toast("反馈内容至少" + CONTENT_MIN + "个字");
            return;
        }
        if (content.length() > CONTENT_MAX) {
            toast("反馈内容最多" + CONTENT_MAX + "个字");
            return;
        }
        if (phone.isEmpty() && email.isEmpty()) {
            toast("手机号和邮箱请至少填写一个，方便我们回复你");
            return;
        }
        if (!phone.isEmpty() && !phone.matches("^1[3-9]\\d{9}$")) {
            toast("手机号格式不对，请填11位手机号");
            return;
        }
        if (!email.isEmpty() && !email.matches("^[^@\\s]+@[^@\\s.]+(\\.[^@\\s.]+)+$")) {
            toast("邮箱格式不对");
            return;
        }

        setSubmitting(true);
        String token = UserManager.getToken(this);
        ApiClient.submitFeedback(token, content, phone, email, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    setSubmitting(false);
                    toast(d.optString("message", "反馈已提交"));
                    etContent.setText("");
                    loadMyFeedback();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    setSubmitting(false);
                    toast(message);
                });
            }
        });
    }

    private void setSubmitting(boolean value) {
        submitting = value;
        btnSubmit.setEnabled(!value);
        btnSubmit.setAlpha(value ? 0.6f : 1f);
        btnSubmit.setText(value ? "提交中…" : "提交反馈");
    }

    // ================= 我的反馈 =================

    private void loadMyFeedback() {
        String token = UserManager.getToken(this);
        ApiClient.getMyFeedback(token, 1, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> renderMyFeedback(d.optJSONArray("list")));
            }

            @Override
            public void onError(String message) {
                // 静默失败，不打扰正在填写的用户
            }
        });
    }

    private void renderMyFeedback(JSONArray arr) {
        listContainer.removeAllViews();
        if (arr == null || arr.length() == 0) {
            tvMyEmpty.setVisibility(View.VISIBLE);
            return;
        }
        tvMyEmpty.setVisibility(View.GONE);

        LayoutInflater inflater = LayoutInflater.from(this);
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o == null) continue;
            View row = inflater.inflate(R.layout.item_feedback, listContainer, false);

            ((TextView) row.findViewById(R.id.tv_fb_content)).setText(o.optString("content", ""));
            ((TextView) row.findViewById(R.id.tv_fb_time)).setText(o.optString("time", ""));

            TextView tvStatus = row.findViewById(R.id.tv_fb_status);
            String status = o.optString("status", "");
            tvStatus.setText(o.optString("status_text", ""));
            if ("replied".equals(status)) {
                tvStatus.setTextColor(android.graphics.Color.parseColor("#16A34A"));
            } else if ("pending".equals(status)) {
                tvStatus.setTextColor(android.graphics.Color.parseColor("#F59E0B"));
            } else {
                tvStatus.setTextColor(android.graphics.Color.parseColor("#999999"));
            }

            String reply = o.optString("reply", "");
            View replyBox = row.findViewById(R.id.layout_fb_reply);
            if (reply.isEmpty()) {
                replyBox.setVisibility(View.GONE);
            } else {
                replyBox.setVisibility(View.VISIBLE);
                ((TextView) row.findViewById(R.id.tv_fb_reply)).setText(reply);
            }

            listContainer.addView(row);
        }
    }

    private void toast(String msg) {
        if (msg != null && !msg.isEmpty()) {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        }
    }
}
