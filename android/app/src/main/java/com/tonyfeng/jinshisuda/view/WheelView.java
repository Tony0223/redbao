package com.tonyfeng.jinshisuda.view;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;

import androidx.annotation.Nullable;

import java.util.ArrayList;
import java.util.List;

/**
 * 幸运转盘。格子数、文案都由服务端下发，这里只负责画和转。
 *
 * 角度约定跟 Canvas 一致：0° 在 3 点钟方向，顺时针增大。
 * 第 i 格占 [i*sweep 到 (i+1)*sweep]，中心角 = i*sweep + sweep/2。
 * 指针固定在正上方（270°），所以把第 i 格转到指针下需要的旋转角 = 270 - 中心角（取模360）。
 *
 * 转动分两段：
 *   startFreeSpin()  点完广告立刻匀速转起来，盖住等接口的时间
 *   stopAt(index)    接口返回后再减速停到中奖那一格
 */
public class WheelView extends View {

    private static final int COLOR_SECTOR_A = Color.parseColor("#FFFFFF");
    private static final int COLOR_SECTOR_B = Color.parseColor("#FFF0CE");
    private static final int COLOR_RING = Color.parseColor("#FFC94D");
    private static final int COLOR_RING_EDGE = Color.parseColor("#FFB020");
    private static final int COLOR_DOT_A = Color.parseColor("#FFFFFF");
    private static final int COLOR_DOT_B = Color.parseColor("#FF8A3D");
    private static final int COLOR_TEXT = Color.parseColor("#D8341F");

    /**
     * 中心圆钮占外半径的比例。文案只画在圆钮外沿到外圈之间的环带里，不会被圆钮盖住。
     * 【这个值要跟布局里 btn_wheel_spin 的尺寸对上】：
     * 圆钮边长 118dp ÷ 转盘边长 330dp ≈ 0.36。改布局尺寸时记得同步改这里。
     */
    private static final float HUB_RATIO = 0.36f;

    /** 指针方向：正上方 */
    private static final float POINTER_ANGLE = 270f;
    /** 匀速空转一圈用多久 */
    private static final long FREE_SPIN_PERIOD = 750L;
    /** 收到结果后再转几圈停下 */
    private static final int STOP_ROUNDS = 3;
    private static final long STOP_DURATION = 2400L;

    private final List<String> labels = new ArrayList<>();
    private final Paint sectorPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint linePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF oval = new RectF();

    private ObjectAnimator freeSpinAnimator;
    private ObjectAnimator stopAnimator;

    public WheelView(Context context) {
        this(context, null);
    }

    public WheelView(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        sectorPaint.setStyle(Paint.Style.FILL);
        ringPaint.setStyle(Paint.Style.FILL);
        dotPaint.setStyle(Paint.Style.FILL);
        linePaint.setStyle(Paint.Style.STROKE);
        linePaint.setColor(Color.parseColor("#F0C061"));
        textPaint.setColor(COLOR_TEXT);
        textPaint.setTextAlign(Paint.Align.CENTER);
        textPaint.setFakeBoldText(true);
    }

    /** 服务端下发的格子文案，顺序就是格子序号 */
    public void setLabels(List<String> newLabels) {
        labels.clear();
        if (newLabels != null) labels.addAll(newLabels);
        invalidate();
    }

    public int getSectorCount() {
        return labels.size();
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int w = MeasureSpec.getSize(widthMeasureSpec);
        int h = MeasureSpec.getSize(heightMeasureSpec);
        int size = Math.min(w, h);
        if (size <= 0) size = Math.max(w, h);
        setMeasuredDimension(size, size);
    }

    /**
     * 区间奖品（如 16666-38888）单行放不下会被压得很小，拆成两行：
     * 第一行 "16666-"，第二行 "38888"。
     */
    private String[] splitLabel(String label) {
        if (label == null) return new String[]{""};
        int cut = label.indexOf('-');
        if (cut < 0) cut = label.indexOf('~');
        if (cut > 0 && cut < label.length() - 1 && label.length() > 6) {
            return new String[]{label.substring(0, cut + 1), label.substring(cut + 1)};
        }
        return new String[]{label};
    }

    private float maxLineWidth(String[] lines) {
        float max = 0;
        for (String line : lines) {
            max = Math.max(max, textPaint.measureText(line));
        }
        return max;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int n = labels.size();
        if (n == 0) return;

        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        float outer = Math.min(cx, cy);
        float ringWidth = outer * 0.13f;
        float r = outer - ringWidth;

        // 外圈金边
        ringPaint.setColor(COLOR_RING);
        canvas.drawCircle(cx, cy, outer, ringPaint);
        ringPaint.setColor(COLOR_RING_EDGE);
        canvas.drawCircle(cx, cy, outer * 0.985f, ringPaint);
        ringPaint.setColor(COLOR_RING);
        canvas.drawCircle(cx, cy, outer * 0.96f, ringPaint);

        // 扇形格子
        oval.set(cx - r, cy - r, cx + r, cy + r);
        float sweep = 360f / n;
        for (int i = 0; i < n; i++) {
            sectorPaint.setColor(i % 2 == 0 ? COLOR_SECTOR_A : COLOR_SECTOR_B);
            canvas.drawArc(oval, i * sweep, sweep, true, sectorPaint);
        }

        // 格子分隔线
        linePaint.setStrokeWidth(outer * 0.008f);
        for (int i = 0; i < n; i++) {
            double a = Math.toRadians(i * sweep);
            canvas.drawLine(cx, cy,
                    cx + (float) (r * Math.cos(a)), cy + (float) (r * Math.sin(a)), linePaint);
        }

        // 金边上的小圆点
        float dotR = outer * 0.022f;
        float dotOrbit = outer - ringWidth / 2f;
        for (int k = 0; k < 20; k++) {
            double a = Math.toRadians(k * 18);
            dotPaint.setColor(k % 2 == 0 ? COLOR_DOT_A : COLOR_DOT_B);
            canvas.drawCircle(cx + (float) (dotOrbit * Math.cos(a)),
                    cy + (float) (dotOrbit * Math.sin(a)), dotR, dotPaint);
        }

        // 文案只画在「圆钮外沿 → 外圈」这段环带里，不会被中间的圆钮盖住
        float bandStart = outer * HUB_RATIO + outer * 0.04f;
        float bandEnd = r * 0.96f;
        float bandWidth = bandEnd - bandStart;
        float bandCenter = (bandStart + bandEnd) / 2f;
        float maxTextWidth = bandWidth * 0.94f;

        for (int i = 0; i < n; i++) {
            String[] lines = splitLabel(labels.get(i));

            float textSize = outer * 0.115f;
            textPaint.setTextSize(textSize);
            while (maxLineWidth(lines) > maxTextWidth && textSize > outer * 0.055f) {
                textSize -= 1f;
                textPaint.setTextSize(textSize);
            }

            canvas.save();
            canvas.rotate(i * sweep + sweep / 2f, cx, cy);
            if (lines.length == 1) {
                canvas.drawText(lines[0], cx + bandCenter, cy + textSize / 3f, textPaint);
            } else {
                float lineGap = textSize * 1.08f;
                canvas.drawText(lines[0], cx + bandCenter, cy - lineGap / 2f + textSize / 3f, textPaint);
                canvas.drawText(lines[1], cx + bandCenter, cy + lineGap / 2f + textSize / 3f, textPaint);
            }
            canvas.restore();
        }
    }

    public interface SpinEndListener {
        void onSpinEnd();
    }

    /** 第一段：匀速空转，用来盖住"等服务端返回结果"的那一两秒 */
    public void startFreeSpin() {
        if (freeSpinAnimator != null && freeSpinAnimator.isRunning()) return;
        cancelStopAnimator();

        float current = getRotation();
        freeSpinAnimator = ObjectAnimator.ofFloat(this, "rotation", current, current + 360f);
        freeSpinAnimator.setDuration(FREE_SPIN_PERIOD);
        freeSpinAnimator.setInterpolator(new LinearInterpolator());
        freeSpinAnimator.setRepeatCount(ValueAnimator.INFINITE);
        freeSpinAnimator.setRepeatMode(ValueAnimator.RESTART);
        freeSpinAnimator.start();
    }

    /** 第二段：接口回来了，从当前角度继续转几圈，减速停在第 index 格 */
    public void stopAt(int index, SpinEndListener listener) {
        int n = labels.size();
        if (n == 0) {
            stopFreeSpin();
            if (listener != null) listener.onSpinEnd();
            return;
        }
        if (index < 0 || index >= n) index = 0;

        float current = getRotation();
        cancelFreeSpinAnimator();
        setRotation(current);   // 空转停在哪就从哪接着减速，不跳帧

        float sweep = 360f / n;
        float center = index * sweep + sweep / 2f;
        float want = (POINTER_ANGLE - center) % 360f;
        if (want < 0) want += 360f;

        float base = current % 360f;
        if (base < 0) base += 360f;
        float delta = (want - base + 360f) % 360f;
        float target = current + STOP_ROUNDS * 360f + delta;

        cancelStopAnimator();
        stopAnimator = ObjectAnimator.ofFloat(this, "rotation", current, target);
        stopAnimator.setDuration(STOP_DURATION);
        stopAnimator.setInterpolator(new DecelerateInterpolator(2.0f));
        stopAnimator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                // 角度收回 0~360，转很多次也不会让数值越滚越大
                setRotation(getRotation() % 360f);
                if (listener != null) listener.onSpinEnd();
            }
        });
        stopAnimator.start();
    }

    /** 抽奖请求失败时用：就地停住，不用转到某一格 */
    public void stopFreeSpin() {
        float current = getRotation();
        cancelFreeSpinAnimator();
        setRotation(current % 360f);
    }

    private void cancelFreeSpinAnimator() {
        if (freeSpinAnimator != null) {
            freeSpinAnimator.cancel();
            freeSpinAnimator = null;
        }
    }

    private void cancelStopAnimator() {
        if (stopAnimator != null) {
            stopAnimator.cancel();
            stopAnimator = null;
        }
    }

    public void cancelSpin() {
        cancelFreeSpinAnimator();
        cancelStopAnimator();
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        cancelSpin();
    }
}
