package com.qrsuite.scanner;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * 设备端一致性测试：在真实 Android 运行时上跑 {@link StylizedDetector}，
 * 与 Python 参考实现（qrsuite/stylized.py）的权威输出逐项比对。
 *
 * <p>为什么需要它：桌面 JVM 测试已证明算法一致（16/16），但 Android 上仍可能因
 * Bitmap 像素格式、R8 混淆或精度差异而改变结果；本测试在真机上再验一遍。
 *
 * <p>运行：{@code gradlew :app:connectedDebugAndroidTest}
 */
@RunWith(AndroidJUnit4.class)
public class StylizedDeviceTest {

    /** 期望值一行：文件名 kind confidence nEyes centerX centerY（-999 表示无圆心）。 */
    private static final class Expect {
        String name, kind;
        double conf, cx, cy;
        int eyes;
        int line;
    }

    private List<Expect> loadExpect() throws Exception {
        AssetManager am = InstrumentationRegistry.getInstrumentation().getContext().getAssets();
        List<Expect> out = new ArrayList<>();
        try (InputStream is = am.open("expect.tsv");
             BufferedReader br = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            String line;
            int n = 0;
            while ((line = br.readLine()) != null) {
                n++;
                if (line.isBlank() || line.startsWith("#")) continue;
                String[] f = line.trim().split("\t");
                if (f.length < 6) continue;
                Expect e = new Expect();
                e.line = n;
                e.name = f[0];
                e.kind = f[1];
                e.conf = Double.parseDouble(f[2]);
                e.eyes = Integer.parseInt(f[3]);
                e.cx = Double.parseDouble(f[4]);
                e.cy = Double.parseDouble(f[5]);
                out.add(e);
            }
        }
        return out;
    }

    /** 从 assets 解码为 RGB 像素数组（与 App 里 detectStylizedThenHint 的处理一致）。 */
    private static int[] pixelsOf(AssetManager am, String name, int[] dims) throws Exception {
        try (InputStream is = am.open(name)) {
            Bitmap bmp = BitmapFactory.decodeStream(is);
            assertNotNull("assets 解码失败: " + name, bmp);
            int w = bmp.getWidth(), h = bmp.getHeight();
            int[] px = new int[w * h];
            bmp.getPixels(px, 0, w, 0, 0, w, h);
            bmp.recycle();
            dims[0] = w;
            dims[1] = h;
            return px;
        }
    }

    @Test
    public void detectorMatchesPythonReferenceOnDevice() throws Exception {
        AssetManager am = InstrumentationRegistry.getInstrumentation().getContext().getAssets();
        List<Expect> expects = loadExpect();
        assertTrue("期望值文件为空", expects.size() > 0);

        StringBuilder report = new StringBuilder("\n设备端一致性结果:\n");
        int pass = 0;
        for (Expect e : expects) {
            int[] dims = new int[2];
            int[] px = pixelsOf(am, e.name, dims);
            long t0 = System.nanoTime();
            StylizedDetector.Info info = new StylizedDetector(px, dims[0], dims[1]).classify();
            long ms = (System.nanoTime() - t0) / 1_000_000;

            report.append(String.format("  %-28s %-18s conf=%.3f eyes=%d (%dms)  [%dx%d]%n",
                    e.name, info.kind, info.confidence, info.nEyes, ms, dims[0], dims[1]));

            assertEquals(e.name + " 判定不一致", e.kind, info.kind);
            assertEquals(e.name + " 置信度偏差", e.conf, info.confidence, 0.02);
            assertEquals(e.name + " 定位点数不一致", e.eyes, info.nEyes);
            if (e.cx < -900) {
                assertEquals(e.name + " 应为无圆心", null, info.center);
            } else {
                assertNotNull(e.name + " 缺圆心", info.center);
                assertEquals(e.name + " 圆心X偏差", e.cx, info.center[0], 0.05);
                assertEquals(e.name + " 圆心Y偏差", e.cy, info.center[1], 0.05);
            }
            pass++;
        }
        report.append("  合计 ").append(pass).append(" / ").append(expects.size()).append(" 与 Python 参考一致");
        System.out.println(report);
    }

    /** 判定必须在可接受时间内完成（真机移动端预算）。 */
    @Test
    public void detectionWithinTimeBudget() throws Exception {
        AssetManager am = InstrumentationRegistry.getInstrumentation().getContext().getAssets();
        int[] dims = new int[2];
        int[] px = pixelsOf(am, "real_douyin.jpg", dims);
        StylizedDetector d = new StylizedDetector(px, dims[0], dims[1]);
        d.classify();                                    // 预热（JIT）
        long t0 = System.nanoTime();
        d.classify();
        long ms = (System.nanoTime() - t0) / 1_000_000;
        System.out.println("真机判定耗时: " + ms + "ms（预算 1500ms）");
        assertTrue("判定耗时 " + ms + "ms 超出预算", ms < 1500);
    }
}
