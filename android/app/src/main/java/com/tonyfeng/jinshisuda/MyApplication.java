package com.tonyfeng.jinshisuda;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.tonyapp.djxplugin.DjxSdkHolder;
import com.tonyfeng.jinshisuda.api.WeChatLoginManager;
import com.tonyfeng.jinshisuda.view.FeedAdDrawer;

public class MyApplication extends Application {

    private static final String TAG = "MyApplication";

    @Override
    public void onCreate() {
        super.onCreate();

        WeChatLoginManager.init(this);

        DjxSdkHolder.initAdSdk(this, "5878709", "短剧888");
        DjxSdkHolder.startAdOnly(new DjxSdkHolder.StartCallback() {
            @Override
            public void onResult(boolean success, String message) {
                Log.d(TAG, "广告SDK启动结果: success=" + success + " message=" + message);
            }
        });

        registerFeedAdDrawer();
    }

    /**
     * 给所有自家页面自动挂底部抽屉广告。
     * 在这里统一挂，业务代码一行都不用改；哪个页面不想要，
     * 在 FeedAdDrawer.shouldAttach() 里加个判断就行。
     */
    private void registerFeedAdDrawer() {
        registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
            @Override
            public void onActivityCreated(@NonNull Activity activity, @Nullable Bundle savedInstanceState) {
                // 这个回调发生在 Activity.onCreate 执行完之后，
                // 此时 setContentView 已经调过了，能拿到 android.R.id.content
                FeedAdDrawer.attach(activity);
            }

            @Override
            public void onActivityResumed(@NonNull Activity activity) {
                FeedAdDrawer.onResume(activity);
            }

            @Override
            public void onActivityPaused(@NonNull Activity activity) {
                FeedAdDrawer.onPause(activity);
            }

            @Override
            public void onActivityDestroyed(@NonNull Activity activity) {
                FeedAdDrawer.detach(activity);
            }

            @Override
            public void onActivityStarted(@NonNull Activity activity) {
            }

            @Override
            public void onActivityStopped(@NonNull Activity activity) {
            }

            @Override
            public void onActivitySaveInstanceState(@NonNull Activity activity, @NonNull Bundle outState) {
            }
        });
    }
}
