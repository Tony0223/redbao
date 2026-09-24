package com.tonyfeng.jinshisuda.api;

import android.content.Context;
import android.util.Log;

import com.tencent.mm.opensdk.constants.Build;
import com.tencent.mm.opensdk.modelbiz.WXOpenBusinessView;
import com.tencent.mm.opensdk.openapi.IWXAPI;
import com.tencent.mm.opensdk.openapi.WXAPIFactory;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;

/**
 * 拉起微信"免确认收款授权"页面（商家转账·用户授权免确认模式）。
 * 用户在微信里点同意后，以后的提现审核通过即自动到账，无需每笔确认。
 *
 * 注意：微信回调(WXEntryActivity.onResp)里的结果只代表页面有没有拉起来，
 * 不代表授权成功——真实结果以服务端查询为准，提现页 onResume 时会重新查。
 */
public class WeChatTransferAuth {

    private static final String TAG = "WeChatTransferAuth";
    public static final String BUSINESS_TYPE = "requestMerchantTransfer";

    public enum Result {
        OK,                     // 已成功跳转微信
        WECHAT_NOT_INSTALLED,   // 没装微信
        WECHAT_TOO_OLD,         // 微信版本太低，不支持这个页面
        SEND_FAILED             // 跳转失败
    }

    public static Result launch(Context context, String mchId, String appId, String packageInfo) {
        IWXAPI api = WXAPIFactory.createWXAPI(
                context.getApplicationContext(), WeChatLoginManager.WECHAT_APP_ID, false);
        api.registerApp(WeChatLoginManager.WECHAT_APP_ID);

        if (!api.isWXAppInstalled()) {
            return Result.WECHAT_NOT_INSTALLED;
        }
        if (api.getWXAppSupportAPI() < Build.OPEN_BUSINESS_VIEW_SDK_INT) {
            return Result.WECHAT_TOO_OLD;
        }

        WXOpenBusinessView.Req req = new WXOpenBusinessView.Req();
        req.businessType = BUSINESS_TYPE;
        req.query = "mchId=" + encode(mchId)
                + "&appId=" + encode(appId)
                + "&package=" + encode(packageInfo);

        boolean sent = api.sendReq(req);
        Log.d(TAG, "拉起免确认收款授权页 sendReq=" + sent);
        return sent ? Result.OK : Result.SEND_FAILED;
    }

    private static String encode(String value) {
        try {
            return URLEncoder.encode(value == null ? "" : value, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            return "";
        }
    }
}