package com.tonyfeng.jinshisuda;

import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.InviteCodeStore;
import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.api.WeChatLoginManager;

import org.json.JSONObject;

import java.util.Locale;

/**
 * 登录页 = APP 启动入口。
 *
 * 启动流程：
 * 1. 先拉后台配置查“网站开关”：关闭时只显示“网站已关闭”提示，拦住一切；
 * 2. 网站开启时——已登录直接走开屏进首页；未登录展示“微信登录”按钮。
 *
 * 产品决策：必须登录才能进（无跳过入口）。拉不到配置(离线等)时按开启处理，不误伤。
 *
 * 邀请码：新用户是在本页完成注册的，所以剪贴板里的邀请码必须在本页读取
 * (之前放在首页读，注册时还没读到，导致邀请/代理关系绑不上)。
 * 读到的码自动填进“邀请码(选填)”输入框，用户也可手动输入代理/好友给的码。
 */
public class LoginActivity extends AppCompatActivity {

    private boolean navigated = false;   // 已跳走
    private boolean siteClosed = false;  // 网站被关闭
    private boolean siteChecked = false; // 配置已拉到(拿到网站开关结果)

    private EditText etInviteCode;
    private View btnLogin;

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (!hasFocus || siteClosed || etInviteCode == null) return;
        // Android 10+ 只有前台有焦点时才能读剪贴板，所以放在这里
        InviteCodeStore.tryReadFromClipboard(this);
        String pending = InviteCodeStore.peek(this);
        if (pending != null && etInviteCode.getText().toString().trim().isEmpty()) {
            etInviteCode.setText(pending);
        }
    }

    /** 点微信登录：有邀请码先校验存在再登录；没填就直接登录 */
    private void onLoginClick() {
        String code = etInviteCode.getText().toString().trim().toUpperCase(Locale.ROOT);
        if (code.isEmpty()) {
            InviteCodeStore.consume(this);   // 用户清空了输入框，就不绑定
            WeChatLoginManager.login(this);
            return;
        }
        if (!code.matches("[A-Z0-9]{4,16}")) {
            Toast.makeText(this, "邀请码格式不对，请核对", Toast.LENGTH_SHORT).show();
            return;
        }
        btnLogin.setEnabled(false);
        ApiClient.checkInviteCode(code, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    btnLogin.setEnabled(true);
                    if (!d.optBoolean("valid", false)) {
                        Toast.makeText(LoginActivity.this,
                                "邀请码不存在，请核对；没有邀请码可清空后直接登录", Toast.LENGTH_LONG).show();
                        return;
                    }
                    InviteCodeStore.save(LoginActivity.this, code);
                    WeChatLoginManager.login(LoginActivity.this);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    btnLogin.setEnabled(true);
                    // 校验接口不通时不拦用户，照常带上邀请码登录，由服务端判断
                    InviteCodeStore.save(LoginActivity.this, code);
                    WeChatLoginManager.login(LoginActivity.this);
                });
            }
        });
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_login);
        etInviteCode = findViewById(R.id.et_invite_code);
        btnLogin = findViewById(R.id.btn_wechat_login);
        btnLogin.setOnClickListener(v -> onLoginClick());

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
