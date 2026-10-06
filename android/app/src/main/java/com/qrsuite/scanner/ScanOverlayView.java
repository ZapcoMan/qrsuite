package com.qrsuite.scanner;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

/**
 * 取景遮罩：外部压暗 + 中央方形取景框 + 四角高亮括号 + 呼吸扫描线。
 * 走硬件加速的普通 Canvas 绘制，帧率开销可忽略。
 */
public class ScanOverlayView extends View {

    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint bracket = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF frame = new RectF();
    private final Path dimPath = new Path();
    private float sweep = 0f;
    private float phase = 0f;
    private boolean animating = false;
    private long lastFrameNanos = 0L;

    public ScanOverlayView(Context c) {
        this(c, null);
    }

    public ScanOverlayView(Context c, AttributeSet a) {
        super(c, a);
        float d = getResources().getDisplayMetrics().density;

        dim.setColor(Color.parseColor("#99000000"));
        dim.setStyle(Paint.Style.FILL);

        bracket.setColor(Color.parseColor("#7C5CFF"));
        bracket.setStyle(Paint.Style.STROKE);
        bracket.setStrokeWidth(3.5f * d);
        bracket.setStrokeCap(Paint.Cap.ROUND);
        bracket.setStrokeJoin(Paint.Join.ROUND);

        line.setColor(Color.parseColor("#33FFFFFF"));
        line.setStyle(Paint.Style.STROKE);
        line.setStrokeWidth(1f * d);
    }

    /** 取景框底边（供 Activity 把提示文字贴在框下方） */
    public float frameBottom() {
        return frame.bottom;
    }

    /** 由 Activity 告知是否在扫描中（停止时不再刷新动画，省电） */
    public void setAnimating(boolean on) {
        if (animating == on) return;
        animating = on;
        if (on) {
            lastFrameNanos = 0L;
            postInvalidateOnAnimation();
        } else {
            invalidate();
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        float d = getResources().getDisplayMetrics().density;
        float side = Math.min(w * 0.72f, h * 0.46f);
        float cx = w / 2f;
        float cy = h * 0.42f;
        frame.set(cx - side / 2f, cy - side / 2f, cx + side / 2f, cy + side / 2f);

        // 呼吸线行程，留出圆角安全边
        sweep = side * 0.5f - 8f * d;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (frame.isEmpty()) return;

        // 外部压暗（偶奇填充：整屏 - 取景框）
        dimPath.reset();
        dimPath.setFillType(Path.FillType.EVEN_ODD);
        dimPath.addRect(0, 0, getWidth(), getHeight(), Path.Direction.CW);
        dimPath.addRoundRect(frame, 14f * getResources().getDisplayMetrics().density,
                14f * getResources().getDisplayMetrics().density, Path.Direction.CW);
        canvas.drawPath(dimPath, dim);

        // 取景框描边
        canvas.drawRoundRect(frame, 14f * getResources().getDisplayMetrics().density,
                14f * getResources().getDisplayMetrics().density, line);

        // 四角括号
        float d = getResources().getDisplayMetrics().density;
        float arm = Math.min(frame.width(), frame.height()) * 0.22f;
        float r = 14f * d;
        drawBracket(canvas, frame.left, frame.top, arm, r, 1, 1);
        drawBracket(canvas, frame.right, frame.top, arm, r, -1, 1);
        drawBracket(canvas, frame.left, frame.bottom, arm, r, 1, -1);
        drawBracket(canvas, frame.right, frame.bottom, arm, r, -1, -1);

        // 扫描线（在取景框内上下往返）
        if (animating) {
            long now = System.nanoTime();
            if (lastFrameNanos != 0L) {
                float dt = (now - lastFrameNanos) / 1_000_000_000f;
                phase += dt * 0.55f;   // 约 1.8s 一个来回
            }
            lastFrameNanos = now;
            float t = phase % 2f;
            if (t > 1f) t = 2f - t;      // 三角波
            float y = frame.top + r + t * (frame.height() - 2 * r);

            android.graphics.LinearGradient grad = new android.graphics.LinearGradient(
                    frame.left, 0, frame.right, 0,
                    new int[]{0x007C5CFF, 0xB37C5CFF, 0x007C5CFF},
                    new float[]{0f, 0.5f, 1f}, android.graphics.Shader.TileMode.CLAMP);
            line.setShader(grad);
            line.setStrokeWidth(2f * d);
            canvas.drawLine(frame.left + r, y, frame.right - r, y, line);
            line.setShader(null);
            line.setStrokeWidth(1f * d);

            postInvalidateOnAnimation();
        }
    }

    private void drawBracket(Canvas c, float x, float y, float arm, float r,
                             int sx, int sy) {
        // 圆角处起笔，画两条边（竖 + 横）
        c.drawLine(x + sx * r, y + sy * arm, x + sx * r, y + sy * r, bracket);
        c.drawLine(x + sx * r, y + sy * r, x + sx * arm, y + sy * r, bracket);
    }
}
