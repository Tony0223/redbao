package com.tonyfeng.jinshisuda.activity;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.tonyfeng.jinshisuda.LoginActivity;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.UserManager;

import org.json.JSONObject;

import java.io.File;
import java.util.Locale;

/**
 * 我的设置。
 * - 清除缓存：算 cacheDir + externalCacheDir 的大小，清掉
 * - 检查更新：比对后台配的 latest_version_code，有新版跳浏览器下载
 * - 用户协议 / 隐私政策：ContentActivity，内容后台配
 * - 退出登录
 * - 注销账号：应用市场强制要求有这个入口，两次确认后调服务端
 */
public class SettingsActivity extends AppCompatActivity {

    private TextView tvCacheSize;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        tvCacheSize = findViewById(R.id.tv_cache_size);

        findViewById(R.id.btn_back).setOnClickListener(v -> finish());
        findViewById(R.id.row_clear_cache).setOnClickListener(v -> confirmClearCache());
        findViewById(R.id.row_check_update).setOnClickListener(v -> checkUpdate());
        findViewById(R.id.row_agreement).setOnClickListener(v -> openContent("agreement"));
        findViewById(R.id.row_privacy).setOnClickListener(v -> openContent("privacy"));
        findViewById(R.id.row_logout).setOnClickListener(v -> confirmLogout());
        findViewById(R.id.row_deactivate).setOnClickListener(v -> confirmDeactivate());

        ((TextView) findViewById(R.id.tv_version_name)).setText(currentVersionName());
        refreshCacheSize();
    }

    // ================= 清除缓存 =================

    private void refreshCacheSize() {
        long size = dirSize(getCacheDir()) + dirSize(getExternalCacheDir());
        tvCacheSize.setText(formatSize(size));
    }

    private void confirmClearCache() {
        new AlertDialog.Builder(this)
                .setTitle("清除缓存")
                .setMessage("会清掉图片和临时文件，不影响金币和登录状态")
                .setNegativeButton("取消", null)
                .setPositiveButton("确定清除", (d, w) -> {
                    deleteDir(getCacheDir());
                    deleteDir(getExternalCacheDir());
                    refreshCacheSize();
                    toast("缓存已清除");
                })
                .show();
    }

    /** 递归算目录大小，目录本身不删 */
    private long dirSize(File dir) {
        if (dir == null || !dir.exists()) return 0;
        long total = 0;
        File[] files = dir.listFiles();
        if (files == null) return 0;
        for (File f : files) {
            total += f.isDirectory() ? dirSize(f) : f.length();
        }
        return total;
    }

    /** 删掉目录里的内容，保留目录本身 */
    private void deleteDir(File dir) {
        if (dir == null || !dir.exists()) return;
        File[] files = dir.listFiles();
        if (files == null) return;
        for (File f : files) {
            if (f.isDirectory()) {
                deleteDir(f);
            }
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }

    private String formatSize(long bytes) {
        if (bytes <= 0) return "0.0 M";
        if (bytes < 1024 * 1024) {
            return String.format(Locale.CHINA, "%.1f K", bytes / 1024.0);
        }
        return String.format(Locale.CHINA, "%.1f M", bytes / 1024.0 / 1024.0);
    }

    // ================= 检查更新 =================

    private String currentVersionName() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return "v" + info.versionName;
        } catch (Exception e) {
            return "v1.0.0";
        }
    }

    private long currentVersionCode() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return info.getLongVersionCode();
        } catch (Exception e) {
            return 1;
        }
    }

    private void checkUpdate() {
        toast("检查中…");
        ApiClient.getAppConfig(new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                runOnUiThread(() -> {
                    long latest = d.optLong("latest_version_code", 1);
                    String url = d.optString("update_url", "");
                    String notes = d.optString("update_notes", "");
                    String name = d.optString("latest_version_name", "");

                    if (latest <= currentVersionCode()) {
                        toast("已是最新版本");
                        return;
                    }
                    if (url.isEmpty()) {
                        toast("发现新版本 " + name + "，但下载地址还没配置");
                        return;
                    }
                    new AlertDialog.Builder(SettingsActivity.this)
                            .setTitle("发现新版本 " + name)
                            .setMessage(notes.isEmpty() ? "建议更新到最新版本" : notes)
                            .setNegativeButton("以后再说", null)
                            .setPositiveButton("立即更新", (dl, w) -> openUrl(url))
                            .show();
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast(message));
            }
        });
    }

    private void openUrl(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            toast("打不开下载链接");
        }
    }

    private void openContent(String key) {
        Intent intent = new Intent(this, ContentActivity.class);
        intent.putExtra(ContentActivity.EXTRA_KEY, key);
        startActivity(intent);
    }

    // ================= 退出登录 / 注销 =================

    private void confirmLogout() {
        if (!UserManager.isLoggedIn(this)) {
            toast("还没登录");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("退出登录")
                .setMessage("退出后金币不会丢失，重新登录还在")
                .setNegativeButton("取消", null)
                .setPositiveButton("退出", (d, w) ->
                        UserManager.logout(this, () -> runOnUiThread(() -> {
                            toast("已退出登录");
                            backToLogin();
                        })))
                .show();
    }

    /** 注销要两次确认：这个操作不可恢复 */
    private void confirmDeactivate() {
        if (!UserManager.isLoggedIn(this)) {
            toast("还没登录");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("注销账号")
                .setMessage("注销后账号信息将被清除，账户内剩余金币会作废且无法恢复。\n\n"
                        + "如果还有未提现的金币，建议先提现再注销。")
                .setNegativeButton("我再想想", null)
                .setPositiveButton("继续注销", (d, w) -> secondConfirmDeactivate())
                .show();
    }

    private void secondConfirmDeactivate() {
        new AlertDialog.Builder(this)
                .setTitle("确认注销？")
                .setMessage("这是最后一次确认，点击确认后账号立即注销，无法撤销。")
                .setNegativeButton("取消", null)
                .setPositiveButton("确认注销", (d, w) -> doDeactivate())
                .show();
    }

    private void doDeactivate() {
        String token = UserManager.getToken(this);
        ApiClient.deactivateAccount(token, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject d) {
                // 服务端已经把账号处理掉了，本地登录状态也必须清干净
                UserManager.logout(SettingsActivity.this, () -> runOnUiThread(() -> {
                    toast("账号已注销");
                    backToLogin();
                }));
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> toast(message));
            }
        });
    }

    private void backToLogin() {
        // 退出登录/注销后必须回登录页（必须登录才能进），并清空返回栈防止退回已登录的界面
        Intent intent = new Intent(this, LoginActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }

    private void toast(String msg) {
        if (msg != null && !msg.isEmpty()) {
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        }
    }
}
