package com.tonyfeng.jinshisuda.api;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Shader;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.LruCache;
import android.widget.ImageView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

/**
 * 圆形头像加载器。
 *
 * 项目里没有 Glide/Picasso，为了一个头像去加个几百K的依赖不划算，
 * 这里用已有的 OkHttp 写个轻量版：内存 LRU + 磁盘缓存 + 圆形裁剪。
 *
 * 头像地址为空（老用户还没登录过新版本）时，显示昵称首字的彩色圆形占位，
 * 不会留个空框。
 *
 * 用法：AvatarLoader.load(imageView, avatarUrl, nickname);
 */
public final class AvatarLoader {

    private static final String TAG = "AvatarLoader";
    /** 头像不大，2M 内存缓存足够放几十张 */
    private static final int MEMORY_CACHE_BYTES = 2 * 1024 * 1024;
    /** 解码后的目标边长，头像框最大也就 60dp，200px 绰绰有余 */
    private static final int TARGET_SIZE = 200;
    private static final String DISK_DIR = "avatars";

    /** 占位图的底色，按昵称哈希挑一个，同一个人每次进来颜色一致 */
    private static final int[] PLACEHOLDER_COLORS = {
            Color.parseColor("#F4601B"), Color.parseColor("#E8261F"),
            Color.parseColor("#4B44E8"), Color.parseColor("#16A34A"),
            Color.parseColor("#F59E0B"), Color.parseColor("#0EA5E9"),
    };

    private static final LruCache<String, Bitmap> MEMORY = new LruCache<String, Bitmap>(MEMORY_CACHE_BYTES) {
        @Override
        protected int sizeOf(String key, Bitmap value) {
            return value.getByteCount();
        }
    };

    private static final ExecutorService POOL = Executors.newFixedThreadPool(2);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final OkHttpClient CLIENT = new OkHttpClient();

    private AvatarLoader() {
    }

    /**
     * 加载头像。url 为空就只显示昵称首字占位。
     * 用 setTag 防止列表复用时图片错位（慢的那张回来时发现 tag 变了就丢弃）。
     */
    public static void load(ImageView view, String url, String nickname) {
        if (view == null) return;

        final String key = url == null ? "" : url.trim();
        view.setTag(key);

        // 先摆上占位，网络头像回来了再覆盖，避免切换时闪白
        view.setImageBitmap(placeholder(nickname));
        if (key.isEmpty()) return;

        Bitmap cached = MEMORY.get(key);
        if (cached != null && !cached.isRecycled()) {
            view.setImageBitmap(cached);
            return;
        }

        final Context appContext = view.getContext().getApplicationContext();
        POOL.execute(() -> {
            Bitmap bitmap = loadFromDisk(appContext, key);
            if (bitmap == null) {
                bitmap = download(appContext, key);
            }
            if (bitmap == null) return;      // 失败就保持占位，不打扰用户

            final Bitmap circle = toCircle(bitmap);
            if (circle == null) return;
            MEMORY.put(key, circle);

            MAIN.post(() -> {
                // tag 还是当初那个才贴上去，否则说明这个 ImageView 已经被复用了
                if (key.equals(view.getTag())) {
                    view.setImageBitmap(circle);
                }
            });
        });
    }

    // ================= 磁盘缓存 =================

    private static File diskFile(Context context, String url) {
        File dir = new File(context.getCacheDir(), DISK_DIR);
        if (!dir.exists()) {
            //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        }
        return new File(dir, md5(url));
    }

    private static Bitmap loadFromDisk(Context context, String url) {
        File f = diskFile(context, url);
        if (!f.exists() || f.length() == 0) return null;
        try {
            return decodeSampled(BitmapFactory.decodeFile(f.getAbsolutePath()));
        } catch (Throwable e) {
            Log.w(TAG, "读磁盘缓存失败: " + e.getMessage());
            return null;
        }
    }

    private static Bitmap download(Context context, String url) {
        Request request = new Request.Builder().url(url).get().build();
        try (Response resp = CLIENT.newCall(request).execute()) {
            if (!resp.isSuccessful() || resp.body() == null) {
                Log.w(TAG, "头像下载失败: " + resp.code());
                return null;
            }
            InputStream in = resp.body().byteStream();
            Bitmap raw = BitmapFactory.decodeStream(in);
            if (raw == null) return null;

            Bitmap scaled = decodeSampled(raw);
            // 存磁盘，下次直接读，省流量
            try (FileOutputStream fos = new FileOutputStream(diskFile(context, url))) {
                scaled.compress(Bitmap.CompressFormat.PNG, 90, fos);
            } catch (Throwable e) {
                Log.w(TAG, "写磁盘缓存失败: " + e.getMessage());
            }
            return scaled;
        } catch (Throwable e) {
            Log.w(TAG, "头像下载异常: " + e.getMessage());
            return null;
        }
    }

    // ================= 图片处理 =================

    /** 缩到目标尺寸，微信头像本身就不大，这一步主要是统一尺寸 */
    private static Bitmap decodeSampled(Bitmap src) {
        if (src == null) return null;
        int size = Math.min(src.getWidth(), src.getHeight());
        if (size <= TARGET_SIZE) return src;
        float scale = TARGET_SIZE / (float) size;
        int w = Math.round(src.getWidth() * scale);
        int h = Math.round(src.getHeight() * scale);
        Bitmap out = Bitmap.createScaledBitmap(src, w, h, true);
        if (out != src) src.recycle();
        return out;
    }

    /** 裁成圆形。用 BitmapShader，不用额外的自定义 View */
    private static Bitmap toCircle(Bitmap src) {
        if (src == null) return null;
        int size = Math.min(src.getWidth(), src.getHeight());
        if (size <= 0) return null;

        Bitmap out = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(out);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

        BitmapShader shader = new BitmapShader(src, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP);
        // 图不是正方形时居中取中间那块
        Matrix m = new Matrix();
        m.setTranslate(-(src.getWidth() - size) / 2f, -(src.getHeight() - size) / 2f);
        shader.setLocalMatrix(m);
        paint.setShader(shader);

        canvas.drawCircle(size / 2f, size / 2f, size / 2f, paint);
        return out;
    }

    /** 昵称首字占位图：彩色圆 + 白字 */
    public static Bitmap placeholder(String nickname) {
        String text = "微";
        if (nickname != null && !nickname.trim().isEmpty()) {
            text = nickname.trim().substring(0, 1);
        }
        int color = PLACEHOLDER_COLORS[Math.abs((nickname == null ? "" : nickname).hashCode())
                % PLACEHOLDER_COLORS.length];

        int size = TARGET_SIZE;
        Bitmap out = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(out);

        Paint bg = new Paint(Paint.ANTI_ALIAS_FLAG);
        bg.setColor(color);
        canvas.drawCircle(size / 2f, size / 2f, size / 2f, bg);

        Paint tp = new Paint(Paint.ANTI_ALIAS_FLAG);
        tp.setColor(Color.WHITE);
        tp.setTextSize(size * 0.45f);
        tp.setTextAlign(Paint.Align.CENTER);
        tp.setFakeBoldText(true);
        Paint.FontMetrics fm = tp.getFontMetrics();
        float baseline = size / 2f - (fm.ascent + fm.descent) / 2f;
        canvas.drawText(text, size / 2f, baseline, tp);

        return out;
    }

    private static String md5(String text) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] bytes = md.digest(text.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte b : bytes) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return String.valueOf(text.hashCode());
        }
    }
}
