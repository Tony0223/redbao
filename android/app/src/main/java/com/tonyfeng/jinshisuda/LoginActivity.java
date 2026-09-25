package com.tonyfeng.jinshisuda;

import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.api.WeChatLoginManager;

import org.json.JSONObject;

/**
 * 登录页 = APP 启动入口。
 *
 * 启动流程：
 * 1. 先拉后台配置查“网站开关”：关闭时只显示“网站已关闭”提示，拦住一切；
 * 2. 网站开启时——已登录直接走开屏进首页；未登录展示“微信登录”按钮。
 *
 * 产品决策：必须登录才能进（无跳过入口）。拉不到配置(离线等)时按开启处理，不误伤。
 */
public class LoginActivity extends AppCompatActivity {

    private boolean navigated = false;   // 已跳走
    private boolean siteClosed = false;  // 网站被关闭
    private boolean siteChecked = false; // 配置已拉到(拿到网站开关结果)

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_login);
        findViewById(R.id.btn_wechat_login).setOnClickListener(v ->
                WeChatLoginManager.login(LoginActivity.this));

        checkSite();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 网站开关结果出来前不做任何跳转，避免关闭时还漏进去
        if (navigated || siteClosed || !siteChecked) return;
        if (UserManager.isLoggedIn(this)) {
            goNext();
        }
    }

    /** 拉后台配置，判断网站开关 */
    private void checkSite() {
        ApiClient.getAppConfig(new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    siteChecked = true;
                    if (!d.optBoolean("site_enabled", true)) {
                        siteClosed = true;
                        showClosed(d.optString("site_closed_msg", "网站已关闭，请联系管理员"));
                        return;
                    }
                    if (UserManager.isLoggedIn(LoginActivity.this)) {
                        goNext();
                    }
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    // 拉不到配置就按网站开启处理，别把人挡在门外
                    siteChecked = true;
                    if (UserManager.isLoggedIn(LoginActivity.this)) {
                        goNext();
                    }
                });
            }
        });
    }

    /** 网站关闭：整屏只显示提示，不能再往下走 */
    private void showClosed(String msg) {
        TextView tv = new TextView(this);
        tv.setText(msg);
        tv.setGravity(Gravity.CENTER);
        tv.setTextColor(0xFF666666);
        tv.setTextSize(16);
        tv.setPadding(48, 0, 48, 0);
        tv.setBackgroundColor(0xFFF5F5F5);
        setContentView(tv, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    /** 登录成功后先进开屏页，开屏结束再由它进首页 */
    private void goNext() {
        if (navigated) return;
        navigated = true;
        startActivity(new Intent(this, SplashActivity.class));
        finish();
    }
}
