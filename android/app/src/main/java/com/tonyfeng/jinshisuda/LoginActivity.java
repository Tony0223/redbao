package com.tonyfeng.jinshisuda;

import android.content.Intent;
import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.api.WeChatLoginManager;

/**
 * 登录页 = APP 启动入口。
 *
 * 流程改动：以前是直接进首页，用到需要登录的功能时才现拉微信授权、登完再刷新，
 * 体验割裂。现在改成——启动先到这里判断登录：
 * - 已登录：直接进首页，本页一闪而过；
 * - 未登录：展示"微信登录"按钮，用户点了拉起微信授权；授权换 token 由
 *   WXEntryActivity 完成并存本地，返回本页后 onResume 检测到已登录，再进首页。
 *
 * 产品决策：必须登录才能进（无跳过入口）；未装微信时 WeChatLoginManager 会提示，
 * 用户停留在本页。
 */
public class LoginActivity extends AppCompatActivity {

    /** 防止 onCreate 直进首页后 onResume 再触发一次跳转 */
    private boolean navigated = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 已登录就别停在登录页，直接进首页
        if (UserManager.isLoggedIn(this)) {
            goToMain();
            return;
        }

        setContentView(R.layout.activity_login);
        findViewById(R.id.btn_wechat_login).setOnClickListener(v ->
                WeChatLoginManager.login(LoginActivity.this));
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 从微信授权返回后，token 已由 WXEntryActivity 存好，这里检测到即进首页
        if (!navigated && UserManager.isLoggedIn(this)) {
            goToMain();
        }
    }

    private void goToMain() {
        if (navigated) return;
        navigated = true;
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }
}
