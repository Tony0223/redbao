package com.tonyfeng.jinshisuda.wxapi;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.tencent.mm.opensdk.constants.ConstantsAPI;
import com.tencent.mm.opensdk.modelbase.BaseReq;
import com.tencent.mm.opensdk.modelbase.BaseResp;
import com.tencent.mm.opensdk.modelbiz.WXOpenBusinessView;
import com.tencent.mm.opensdk.modelmsg.SendAuth;
import com.tencent.mm.opensdk.openapi.IWXAPI;
import com.tencent.mm.opensdk.openapi.IWXAPIEventHandler;
import com.tencent.mm.opensdk.openapi.WXAPIFactory;
import com.tonyfeng.jinshisuda.api.ApiClient;
import com.tonyfeng.jinshisuda.api.InviteCodeStore;
import com.tonyfeng.jinshisuda.api.UserManager;
import com.tonyfeng.jinshisuda.api.WeChatLoginManager;
import com.tonyfeng.jinshisuda.api.WeChatTransferAuth;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * 微信回调入口（类名、包名、位置都是微信SDK规定死的）。处理三种回调：
 * 1. 微信登录：拿到 code 后当场换 token 并存本地，换完再 finish（不依赖主界面是否存活）
 * 2. 免确认收款授权页返回：只打日志然后关闭，授权结果由提现页 onResume 向服务端查询
 * 3. 分享结果：不做处理
 */
public class WXEntryActivity extends Activity implements IWXAPIEventHandler {

    private static final String TAG = "WXEntryActivity";
    private IWXAPI api;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildLoadingView()); // 换token期间给个转圈，别让用户看着黑屏
        api = WXAPIFactory.createWXAPI(this, WeChatLoginManager.WECHAT_APP_ID, false);
        api.handleIntent(getIntent(), this);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        api.handleIntent(intent, this);
    }

    @Override
    public void onReq(BaseReq baseReq) {
        // 用不上
    }

    @Override
    public void onResp(BaseResp baseResp) {
        // ---------- 1. 微信登录 ----------
        if (baseResp.getType() == ConstantsAPI.COMMAND_SENDAUTH && baseResp instanceof SendAuth.Resp) {
            WeChatLoginManager.forceResetLoginState(); // 释放登录锁，允许下次重试
            SendAuth.Resp resp = (SendAuth.Resp) baseResp;
            if (baseResp.errCode == BaseResp.ErrCode.ERR_OK) {
                exchangeCodeForToken(resp.code);
                return; // 换完 token 再 finish
            } else if (baseResp.errCode == BaseResp.ErrCode.ERR_USER_CANCEL) {
                Log.d(TAG, "用户取消了微信登录");
            } else {
                Log.e(TAG, "微信登录失败: " + baseResp.errStr);
            }
            finishSafely();
            return;
        }

        // ---------- 2. 免确认收款授权页返回 ----------
        if (baseResp.getType() == ConstantsAPI.COMMAND_OPEN_BUSINESS_VIEW
                && baseResp instanceof WXOpenBusinessView.Resp) {
            WXOpenBusinessView.Resp resp = (WXOpenBusinessView.Resp) baseResp;
            if (WeChatTransferAuth.BUSINESS_TYPE.equals(resp.businessType)) {
                Log.d(TAG, "免确认收款授权页返回 errCode=" + resp.errCode + ", extMsg=" + resp.extMsg);
            }
        }
        finishSafely();
    }

    private void exchangeCodeForToken(String code) {
        String inviterCode = InviteCodeStore.peek(getApplicationContext());
        Log.d(TAG, "拿到 code，开始换 token，邀请码=" + inviterCode);
        ApiClient.loginWithWeChatCode(code, inviterCode, new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                try {
                    int userId = data.getInt("user_id");
                    String token = data.getString("token");
                    // 用 applicationContext 存，就算这个 Activity 被杀，token 也已经落地了
                    UserManager.saveLogin(getApplicationContext(), userId, token);
                    InviteCodeStore.consume(getApplicationContext()); // 邀请码用过就清掉
                    Log.d(TAG, "登录成功，token 已存本地");
                    runOnUiThread(() -> {
                        toast("登录成功");
                        finishSafely();
                    });
                } catch (JSONException e) {
                    Log.e(TAG, "解析登录响应失败: " + e.getMessage());
                    runOnUiThread(() -> {
                        toast("登录失败，请重试");
                        finishSafely();
                    });
                }
            }

            @Override
            public void onError(String message) {
                Log.e(TAG, "code 换 token 失败: " + message);
                runOnUiThread(() -> {
                    toast("登录失败，请重试");
                    finishSafely();
                });
            }
        });
    }

    private void toast(String msg) {
        Toast.makeText(getApplicationContext(), msg, Toast.LENGTH_SHORT).show();
    }

    private void finishSafely() {
        if (!isFinishing() && !isDestroyed()) {
            finish();
        }
    }

    private FrameLayout buildLoadingView() {
        FrameLayout root = new FrameLayout(this);
        root.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        root.setBackgroundColor(Color.parseColor("#80000000"));
        ProgressBar pb = new ProgressBar(this);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.gravity = Gravity.CENTER;
        pb.setLayoutParams(lp);
        root.addView(pb);
        return root;
    }
}