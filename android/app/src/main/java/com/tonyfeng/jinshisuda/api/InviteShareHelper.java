package com.tonyfeng.jinshisuda.api;

import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.EncodeHintType;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel;
import com.tencent.mm.opensdk.modelmsg.SendMessageToWX;
import com.tencent.mm.opensdk.modelmsg.WXImageObject;
import com.tencent.mm.opensdk.modelmsg.WXMediaMessage;
import com.tencent.mm.opensdk.openapi.IWXAPI;
import com.tencent.mm.opensdk.openapi.WXAPIFactory;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * 邀请海报：生成、分享到微信/朋友圈、保存到相册。
 *
 * 海报底图：默认用代码画的渐变背景；
 * 如果 res/drawable 下放了 bg_invite_poster.png，会自动改用这张图当底图。
 */
public class InviteShareHelper {

    private static final String TAG = "InviteShareHelper";

    private static final String LANDING_BASE = "https://hongbao.zero-start.online/i/";
    private static final int W = 750;
    private static final int H = 1334;

    public static String landingUrl(String inviteCode) {
        return LANDING_BASE + inviteCode;
    }

    /** 落地页写进剪贴板的口令，要和 InviteCodeStore 的解析规则一致 */
    public static String inviteToken(String inviteCode) {
        return "金石速答邀请码:" + inviteCode;
    }

    // ---------------- 生成海报 ----------------

    public static Bitmap buildPoster(Context context, String nickname, String inviteCode) {
        Bitmap poster = Bitmap.createBitmap(W, H, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(poster);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

        drawBackground(context, canvas, paint);

        // 标题
        paint.setColor(Color.WHITE);
        paint.setFakeBoldText(true);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(76);
        canvas.drawText("邀请好友", W / 2f, 210, paint);
        paint.setColor(Color.parseColor("#FFF0C2"));
        canvas.drawText("赚取收益", W / 2f, 300, paint);

        // 白色卡片
        paint.setColor(Color.WHITE);
        RectF card = new RectF(95, 380, W - 95, 1010);
        canvas.drawRoundRect(card, 28, 28, paint);

        // 二维码
        Bitmap qr = createQrCode(landingUrl(inviteCode), 380);
        if (qr != null) {
            canvas.drawBitmap(qr, (W - qr.getWidth()) / 2f, 430, null);
            qr.recycle();
        }

        // 昵称 + 邀请码
        paint.setFakeBoldText(true);
        paint.setColor(Color.parseColor("#222222"));
        paint.setTextSize(38);
        canvas.drawText(nickname == null || nickname.isEmpty() ? "微信用户" : nickname, W / 2f, 890, paint);

        paint.setFakeBoldText(false);
        paint.setColor(Color.parseColor("#666666"));
        paint.setTextSize(30);
        canvas.drawText("邀请码：" + inviteCode, W / 2f, 945, paint);

        // 底部说明
        paint.setColor(Color.WHITE);
        paint.setTextSize(30);
        canvas.drawText("长按识别二维码，下载App领金币", W / 2f, 1120, paint);
        paint.setColor(Color.parseColor("#FFE9D2"));
        paint.setTextSize(26);
        canvas.drawText("看广告赚金币，可提现到微信零钱", W / 2f, 1175, paint);

        return poster;
    }

    private static void drawBackground(Context context, Canvas canvas, Paint paint) {
        int resId = context.getResources().getIdentifier(
                "bg_invite_poster", "drawable", context.getPackageName());
        if (resId != 0) {
            Bitmap bg = BitmapFactory.decodeResource(context.getResources(), resId);
            if (bg != null) {
                canvas.drawBitmap(bg, null, new Rect(0, 0, W, H), null);
                bg.recycle();
                return;
            }
        }
        paint.setShader(new LinearGradient(0, 0, 0, H,
                new int[]{Color.parseColor("#1FA8A0"), Color.parseColor("#E8261F")},
                new float[]{0f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawRect(0, 0, W, H, paint);
        paint.setShader(null);
    }

    public static Bitmap createQrCode(String content, int size) {
        try {
            Map<EncodeHintType, Object> hints = new HashMap<>();
            hints.put(EncodeHintType.CHARACTER_SET, "UTF-8");
            hints.put(EncodeHintType.ERROR_CORRECTION, ErrorCorrectionLevel.H);
            hints.put(EncodeHintType.MARGIN, 1);

            BitMatrix matrix = new QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size, hints);
            int[] pixels = new int[size * size];
            for (int y = 0; y < size; y++) {
                for (int x = 0; x < size; x++) {
                    pixels[y * size + x] = matrix.get(x, y) ? Color.BLACK : Color.WHITE;
                }
            }
            Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
            bitmap.setPixels(pixels, 0, size, 0, 0, size, size);
            return bitmap;
        } catch (Exception e) {
            Log.e(TAG, "生成二维码失败: " + e.getMessage());
            return null;
        }
    }

    // ---------------- 分享到微信 ----------------

    /** timeline=true 发朋友圈，false 发给好友 */
    public static boolean shareToWeChat(Context context, Bitmap poster, boolean timeline) {
        IWXAPI api = WXAPIFactory.createWXAPI(
                context.getApplicationContext(), WeChatLoginManager.WECHAT_APP_ID, false);
        api.registerApp(WeChatLoginManager.WECHAT_APP_ID);
        if (!api.isWXAppInstalled()) return false;

        WXMediaMessage msg = new WXMediaMessage(new WXImageObject(compress(poster, 9 * 1024 * 1024)));
        msg.thumbData = buildThumb(poster);

        SendMessageToWX.Req req = new SendMessageToWX.Req();
        req.transaction = "invite_poster_" + System.currentTimeMillis();
        req.message = msg;
        req.scene = timeline ? SendMessageToWX.Req.WXSceneTimeline : SendMessageToWX.Req.WXSceneSession;
        return api.sendReq(req);
    }

    /** 缩略图必须小于32KB，不然微信会拒绝 */
    private static byte[] buildThumb(Bitmap poster) {
        Bitmap thumb = Bitmap.createScaledBitmap(poster, 150, 267, true);
        byte[] data = compress(thumb, 30 * 1024);
        thumb.recycle();
        return data;
    }

    private static byte[] compress(Bitmap bitmap, int maxBytes) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int quality = 90;
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out);
        while (out.size() > maxBytes && quality > 20) {
            out.reset();
            quality -= 15;
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out);
        }
        return out.toByteArray();
    }

    // ---------------- 保存到相册 ----------------

    public static boolean saveToGallery(Context context, Bitmap poster) {
        String name = "invite_" + System.currentTimeMillis() + ".jpg";
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES);
                Uri uri = context.getContentResolver()
                        .insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                if (uri == null) return false;
                try (OutputStream os = context.getContentResolver().openOutputStream(uri)) {
                    if (os == null) return false;
                    poster.compress(Bitmap.CompressFormat.JPEG, 90, os);
                }
                return true;
            }

            File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES);
            if (!dir.exists() && !dir.mkdirs()) return false;
            File file = new File(dir, name);
            try (FileOutputStream fos = new FileOutputStream(file)) {
                poster.compress(Bitmap.CompressFormat.JPEG, 90, fos);
            }
            // 通知相册刷新
            MediaStore.Images.Media.insertImage(
                    context.getContentResolver(), file.getAbsolutePath(), name, null);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "保存到相册失败: " + e.getMessage());
            return false;
        }
    }
}