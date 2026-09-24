package com.tonyfeng.jinshisuda;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;

import androidx.appcompat.app.AppCompatActivity;

import com.tonyapp.djxplugin.SplashAdHelper;

/**
 * 开屏页。登录成功后进这里展示开屏广告，广告倒计时结束/跳过后再进首页。
 *
 * 兜底：广告加载失败、无填充、或迟迟没有任何回调，都会进首页，不会卡住。
 */
public class SplashActivity extends AppCompatActivity {

    /** 兜底总超时：万一 SDK 一个回调都不给，到点也进首页 */
    private static final long HARD_TIMEOUT_MS = 6000;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean forwarded = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_splash);

        ViewGroup container = findViewById(R.id.splash_container);

        // 兜底超时，防止极端情况下卡在开屏
        handler.postDelayed(this::goToMain, HARD_TIMEOUT_MS);

        SplashAdHelper.loadAndShow(this, container, this::goToMain);
    }

    private void goToMain() {
        if (forwarded) return;
        forwarded = true;
        handler.removeCallbacksAndMessages(null);
        startActivity(new Intent(this, MainActivity.class));
        finish();
        overridePendingTransition(0, 0);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        // 开屏期间屏蔽返回键，避免直接退出到桌面
    }
}
