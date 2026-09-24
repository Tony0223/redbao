package com.tonyfeng.jinshisuda.api;

import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class ApiClient {

    private static final String TAG = "ApiClient";
    private static final String BASE_URL = "https://hongbao.zero-start.online";
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private static final OkHttpClient client = new OkHttpClient();

    public interface ApiCallback {
        void onSuccess(JSONObject data);
        void onError(String message);
    }

    /**
     * 正式登录：把微信登录SDK拿到的code传给服务端，服务端拿AppSecret去微信换真实openid、
     * 建/查用户，返回一个登录token。这个接口本身不需要带Authorization头（登录前哪来的token）。
     *
     * inviterCode：从落地页剪贴板读到的邀请码，只在新用户注册时用来绑定邀请关系，没有就传 null。
     */
    public static void loginWithWeChatCode(String code, String inviterCode, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("code", code);
            if (inviterCode != null && !inviterCode.isEmpty()) {
                body.put("inviter_code", inviterCode);
            }
            postJson("/api/user/login", body, null, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * 看完广告上报拿金币。身份由token决定，不用再传user_id。
     */
    public static void reportAdReward(String token, String adType, boolean isGameAd, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("ad_type", adType);
            body.put("is_game_ad", isGameAd);
            postJson("/api/ad/reward", body, token, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * 查自己的金币余额。身份由token决定，不用再传user_id。
     */
    public static void getUserBalance(String token, ApiCallback callback) {
        get("/api/user/me/balance", token, callback);
    }

    /**
     * 提现页信息：是否已绑定微信收款（免确认授权）、最低提现金币、汇率。
     */
    public static void getWithdrawalInfo(String token, ApiCallback callback) {
        get("/api/withdrawal/info", token, callback);
    }

    /**
     * 申请绑定微信收款（免确认收款授权）。
     */
    public static void applyWithdrawalAuth(String token, ApiCallback callback) {
        postJson("/api/withdrawal/auth/apply", new JSONObject(), token, callback);
    }

    /**
     * 查自己的提现申请记录。
     */
    public static void getWithdrawalList(String token, ApiCallback callback) {
        get("/api/withdrawal/list", token, callback);
    }

    /**
     * 申请提现。
     */
    public static void requestWithdrawal(String token, int coinAmount, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("coin_amount", coinAmount);
            postJson("/api/withdrawal/request", body, token, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * 邀请页统计：总人数、今日/昨日新增、今日/昨日活跃、今日/昨日收益。
     */
    public static void getInviteSummary(String token, ApiCallback callback) {
        get("/api/invite/summary", token, callback);
    }

    /**
     * 我邀请的人（分页）。返回 {"list": [...], "has_more": bool}
     */
    public static void getInviteMembers(String token, int page, ApiCallback callback) {
        get("/api/invite/members?page=" + page, token, callback);
    }

    /**
     * 我的返利流水（分页）。返回 {"list": [...], "has_more": bool}
     */
    public static void getInviteIncome(String token, int page, ApiCallback callback) {
        get("/api/invite/income?page=" + page, token, callback);
    }

    /**
     * 平台补贴活动信息：状态、结束时间、档位（含每人限次和已用次数）。
     */
    public static void getSubsidyInfo(String token, ApiCallback callback) {
        get("/api/subsidy/info", token, callback);
    }

    /**
     * 福利页签到信息：今日已赚、签到周期、每天奖励、已签几天。
     */
    public static void getSignInInfo(String token, ApiCallback callback) {
        get("/api/welfare/signin/info", token, callback);
    }

    /**
     * 签到领金币。看完激励视频后调用，服务端按配置发金币。
     */
    public static void signIn(String token, ApiCallback callback) {
        postJson("/api/welfare/signin", new JSONObject(), token, callback);
    }

    /**
     * 打卡页信息：状态、时间段、奖金池、我的名次。
     */
    public static void getPunchInfo(String token, ApiCallback callback) {
        get("/api/punch/info", token, callback);
    }

    /**
     * 打卡。看完激励视频后调用。
     */
    public static void punch(String token, ApiCallback callback) {
        postJson("/api/punch", new JSONObject(), token, callback);
    }

    /**
     * 今日打卡排行榜。
     */
    public static void getPunchRank(String token, ApiCallback callback) {
        get("/api/punch/rank", token, callback);
    }

    /**
     * 福利活动信息：今日看满N次领M金币的配置 + 我今天已看几次。
     * 返回 {enabled, title, subtitle, target_count, reward_coin, watch_count, completed, tips_text}
     */
    public static void getBonusInfo(String token, ApiCallback callback) {
        get("/api/bonus/info", token, callback);
    }

    /**
     * 福利活动：看完一个激励视频后上报一次计数，满N次服务端当场发金币。
     * 返回在 info 字段基础上多了 {ok, just_rewarded, reward_got, coin_balance, message}
     * ok=false 表示被防刷间隔挡住了，不算错误，提示一下 message 即可。
     */
    public static void reportBonusWatch(String token, ApiCallback callback) {
        postJson("/api/bonus/watch", new JSONObject(), token, callback);
    }

    /**
     * 幸运转盘信息：是否开启、格子、我的剩余次数、规则文案、待领取的中奖记录。
     */
    public static void getWheelInfo(String token, ApiCallback callback) {
        get("/api/wheel/info", token, callback);
    }

    /**
     * 看完激励视频换 1 次抽奖机会。
     */
    public static void getWheelAdChance(String token, ApiCallback callback) {
        postJson("/api/wheel/ad_chance", new JSONObject(), token, callback);
    }

    /**
     * 抽奖。服务端扣次数、定结果、写一条待领取记录，【这一步不发金币】。
     * 返回 {record_id, prize_index, label, coin, chances_left}，
     * 客户端把转盘转到 prize_index 那一格即可。
     */
    public static void wheelDraw(String token, ApiCallback callback) {
        postJson("/api/wheel/draw", new JSONObject(), token, callback);
    }

    /**
     * 领取转盘奖励。必须在激励视频完整看完之后调用，服务端这时才真正发金币。
     * 没看完就别调，奖励会保留为待领取，当天可以补领。
     */
    public static void wheelClaim(String token, long recordId, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("record_id", recordId);
            postJson("/api/wheel/claim", body, token, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * 我的抽奖记录（分页）。返回 {"list": [...], "has_more": bool}
     */
    public static void getWheelRecords(String token, int page, ApiCallback callback) {
        get("/api/wheel/records?page=" + page, token, callback);
    }

    /**
     * 按补贴档位申请提现。金币数和补贴金额由服务端按档位计算，客户端只传档位ID。
     */
    public static void subsidyWithdraw(String token, int tierId, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("tier_id", tierId);
            postJson("/api/subsidy/withdraw", body, token, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * "我的"页头部：昵称、用户ID、师傅ID、余额、今日已赚、红包领取次数。
     */
    public static void getMyProfile(String token, ApiCallback callback) {
        get("/api/user/me/profile", token, callback);
    }

    /**
     * 收入明细（分页）。数据来自服务端统一流水表，各种玩法的入账都在里面。
     * 返回 {"total_income_coins": n, "list": [...], "has_more": bool}
     */
    public static void getCoinLogs(String token, int page, ApiCallback callback) {
        get("/api/user/coin_logs?page=" + page, token, callback);
    }

    /**
     * App全局配置：客服QQ/微信/电话、版本更新信息、汇率和提现门槛。
     * 这个接口不需要登录，启动时就能拉。
     */
    public static void getAppConfig(ApiCallback callback) {
        get("/api/app/config", null, callback);
    }

    /**
     * 图文页内容：key 传 notice(平台公告) / privacy(隐私政策) / agreement(用户协议)。
     * 内容在后台 /admin/content 维护，不需要登录。
     */
    public static void getAppContent(String key, ApiCallback callback) {
        get("/api/app/content/" + key, null, callback);
    }

    /**
     * 提交意见反馈。手机号和邮箱至少传一个，服务端会再校验一遍。
     * 微信昵称由服务端自己从账号里取，不用客户端传。
     */
    public static void submitFeedback(String token, String content, String phone,
                                      String email, ApiCallback callback) {
        try {
            JSONObject body = new JSONObject();
            body.put("content", content);
            body.put("phone", phone == null ? "" : phone);
            body.put("email", email == null ? "" : email);
            postJson("/api/feedback", body, token, callback);
        } catch (JSONException e) {
            callback.onError("构造请求失败: " + e.getMessage());
        }
    }

    /**
     * 我的反馈记录（分页），带后台回复内容。
     */
    public static void getMyFeedback(String token, int page, ApiCallback callback) {
        get("/api/feedback/my?page=" + page, token, callback);
    }

    /**
     * 注销账号。不可恢复，客户端必须二次确认过再调，调完要本地清登录状态。
     */
    public static void deactivateAccount(String token, ApiCallback callback) {
        postJson("/api/user/deactivate", new JSONObject(), token, callback);
    }

    /**
     * 退出登录：通知服务端把这个token作废。就算这个请求失败（比如没网），
     * 调用方也应该照样清掉本地登录状态。
     */
    public static void logout(String token, ApiCallback callback) {
        Request request = new Request.Builder()
                .url(BASE_URL + "/api/user/logout")
                .header("Authorization", "Bearer " + token)
                .post(RequestBody.create(new byte[0], null))
                .build();
        enqueue(request, callback);
    }

    // ---------------- 内部工具 ----------------

    private static void get(String path, String token, ApiCallback callback) {
        Request.Builder builder = new Request.Builder()
                .url(BASE_URL + path)
                .get();
        if (token != null) {
            builder.header("Authorization", "Bearer " + token);
        }
        enqueue(builder.build(), callback);
    }

    private static void postJson(String path, JSONObject body, String token, ApiCallback callback) {
        RequestBody requestBody = RequestBody.create(body.toString(), JSON);
        Request.Builder builder = new Request.Builder()
                .url(BASE_URL + path)
                .post(requestBody);
        if (token != null) {
            builder.header("Authorization", "Bearer " + token);
        }
        enqueue(builder.build(), callback);
    }

    private static void enqueue(Request request, ApiCallback callback) {
        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "请求失败: " + e.getMessage());
                callback.onError("网络请求失败，请检查网络");
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String bodyStr = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    Log.e(TAG, "服务器返回错误(" + response.code() + "): " + bodyStr);
                    callback.onError(extractErrorMessage(response.code(), bodyStr));
                    return;
                }
                try {
                    callback.onSuccess(bodyStr.isEmpty() ? new JSONObject() : new JSONObject(bodyStr));
                } catch (JSONException e) {
                    callback.onError("解析响应失败: " + e.getMessage());
                }
            }
        });
    }

    /**
     * 后端(FastAPI)报错格式是 {"detail": "中文提示"}，优先把这句提示给用户看。
     */
    private static String extractErrorMessage(int code, String body) {
        try {
            JSONObject obj = new JSONObject(body);
            Object detail = obj.opt("detail");
            if (detail instanceof String && !((String) detail).isEmpty()) {
                return (String) detail;
            }
        } catch (JSONException ignored) {
        }
        return "服务器返回错误(" + code + ")";
    }
}
