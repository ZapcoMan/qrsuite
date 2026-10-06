package com.qrsuite.scanner;

import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;

/**
 * 严格一致性测试：Java 移植版 vs Python 参考实现。
 *
 * <p>由 tools/stylized_parity.py 生成 cases 列表与期望值，本类只负责逐张跑并比对。
 * 判定（kind）必须完全一致；几何量允许极小浮点差（容差 0.05）。
 */
public final class StylizedParityTest {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2) {
            out.println("用法: StylizedParityTest <期望值tsv> <文件列表txt>");
            out.println("  文件列表txt 每行一个图片路径（避免在命令行传中文路径）");
            return;
        }
        // 期望值文件每行： 文件名 \t kind \t confidence \t nEyes \t centerX \t centerY
        java.util.Map<String, String[]> expect = new java.util.HashMap<>();
        for (String line : java.nio.file.Files.readAllLines(
                java.nio.file.Paths.get(args[0]), java.nio.charset.StandardCharsets.UTF_8)) {
            if (line.isBlank() || line.startsWith("#")) continue;
            String[] f = line.split("\t");
            expect.put(f[0], f);
        }
        // 图片路径从文件读，规避命令行中文参数问题
        List<File> files = new ArrayList<>();
        for (String line : java.nio.file.Files.readAllLines(
                java.nio.file.Paths.get(args[1]), java.nio.charset.StandardCharsets.UTF_8)) {
            if (!line.isBlank()) files.add(new File(line.trim()));
        }

        int pass = 0, fail = 0;
        List<String> problems = new ArrayList<>();
        out.printf("%-30s %-20s %-22s %s%n", "文件", "Java 判定", "Python 判定", "结果");
        out.println("-".repeat(92));
        for (File f : files) {
            String name = f.getName();
            String[] exp = expect.get(name);
            if (exp == null) { out.printf("%-30s %s%n", name, "期望值缺失，跳过"); continue; }

            BufferedImage img = javax.imageio.ImageIO.read(f);
            if (img == null) { out.printf("%-30s %s%n", name, "读取失败"); fail++; continue; }
            int iw = img.getWidth(), ih = img.getHeight();
            int[] px = new int[iw * ih];
            img.getRGB(0, 0, iw, ih, px, 0, iw);

            StylizedDetector.Info info = new StylizedDetector(px, iw, ih).classify();

            String expKind = exp[1];
            double expConf = Double.parseDouble(exp[2]);
            int expEyes = Integer.parseInt(exp[3]);
            double expCx = Double.parseDouble(exp[4]);
            double expCy = Double.parseDouble(exp[5]);

            boolean kindOk = info.kind.equals(expKind);
            boolean confOk = Math.abs(info.confidence - expConf) <= 0.02;
            boolean eyesOk = info.nEyes == expEyes;
            boolean cenOk = true;
            if (expCx > -900) {                 // -999 表示 Python 侧无圆心
                cenOk = info.center != null
                        && Math.abs(info.center[0] - expCx) <= 0.05
                        && Math.abs(info.center[1] - expCy) <= 0.05;
            } else {
                cenOk = info.center == null;
            }
            boolean ok = kindOk && confOk && eyesOk && cenOk;
            if (ok) pass++; else {
                fail++;
                StringBuilder sb = new StringBuilder(name + ":");
                if (!kindOk) sb.append(" kind ").append(info.kind).append("!=").append(expKind);
                if (!confOk) sb.append(String.format(" conf %.3f!=%.3f", info.confidence, expConf));
                if (!eyesOk) sb.append(" eyes ").append(info.nEyes).append("!=").append(expEyes);
                if (!cenOk) sb.append(String.format(" center %s != (%.1f,%.1f)",
                        info.center == null ? "null" : String.format("%.1f,%.1f", info.center[0], info.center[1]),
                        expCx, expCy));
                problems.add(sb.toString());
            }
            out.printf("%-30s %-20s %-22s %s%n", name, info.kind, expKind, ok ? "一致 ✓" : "不一致 ✗");
        }
        out.println("-".repeat(92));
        out.printf("结果: %d 一致 / %d 不一致%n", pass, fail);
        for (String p : problems) out.println("  ✗ " + p);
    }
}
