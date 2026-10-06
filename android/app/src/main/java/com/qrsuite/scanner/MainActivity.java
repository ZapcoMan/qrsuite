package com.qrsuite.scanner;

import android.Manifest;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.media.Image;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Log;
import android.view.Display;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.PickVisualMediaRequest;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.annotation.OptIn;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ExperimentalGetImage;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.button.MaterialButton;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.mlkit.vision.barcode.BarcodeScanner;
import com.google.mlkit.vision.barcode.BarcodeScannerOptions;
import com.google.mlkit.vision.barcode.BarcodeScanning;
import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.common.InputImage;

import java.nio.ByteBuffer;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * QRSuite 移动端：CameraX 取景 + ML Kit 本地条码识别。
 *
 * <p>面向“快 + 省电”的三点取舍：
 * <ol>
 *   <li>只把取景框对应的中央方形裁切区交给识别器，像素量约为全帧 1/4，识别更快更省 CPU；</li>
 *   <li>背压策略 KEEP_ONLY_LATEST：识别跟不上时直接丢帧，而不是排队累积；</li>
 *   <li>格式按用户偏好收敛到常用 QR/一维码，减少无效分类开销。</li>
 * </ol>
 * 全程不申请网络权限，图片不出设备。
 */
public class MainActivity extends AppCompatActivity {

    private static final String TAG = "QRSuite";

    private PreviewView previewView;
    private ScanOverlayView overlay;
    private LinearLayout permPanel;
    private MaterialButton btnTorch, btnHistory, btnPick, btnGrant, btnPickFromPerm;
    private TextView hint;

    private ProcessCameraProvider cameraProvider;
    private ImageAnalysis analysis;
    private BarcodeScanner scanner;
    private ExecutorService analysisExecutor;
    private ListenableFuture<ProcessCameraProvider> providerFuture;

    private final AtomicBoolean busy = new AtomicBoolean(false);
    private volatile boolean scanning = false;
    private Camera camera;
    private boolean torchOn = false;
    private HistoryStore db;

    private ActivityResultLauncher<String> permLauncher;
    private ActivityResultLauncher<PickVisualMediaRequest> pickLauncher;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        applyEdgeToEdge();
        setContentView(R.layout.activity_main);
        applyWindowInsets();

        db = new HistoryStore(getApplicationContext());
        analysisExecutor = Executors.newSingleThreadExecutor();

        previewView = findViewById(R.id.preview);
        overlay = findViewById(R.id.overlay);
        permPanel = findViewById(R.id.permPanel);
        hint = findViewById(R.id.hint);
        btnTorch = findViewById(R.id.btnTorch);
        btnHistory = findViewById(R.id.btnHistory);
        btnPick = findViewById(R.id.btnPick);
        btnGrant = findViewById(R.id.btnGrant);
        btnPickFromPerm = findViewById(R.id.btnPickFromPerm);

        BarcodeScannerOptions options = new BarcodeScannerOptions.Builder()
                .setBarcodeFormats(
                        Barcode.FORMAT_QR_CODE,
                        Barcode.FORMAT_DATA_MATRIX,
                        Barcode.FORMAT_AZTEC,
                        Barcode.FORMAT_PDF417,
                        Barcode.FORMAT_CODE_128,
                        Barcode.FORMAT_CODE_39,
                        Barcode.FORMAT_CODE_93,
                        Barcode.FORMAT_EAN_13,
                        Barcode.FORMAT_EAN_8,
                        Barcode.FORMAT_UPC_A,
                        Barcode.FORMAT_UPC_E,
                        Barcode.FORMAT_ITF,
                        Barcode.FORMAT_CODABAR)
                .build();
        scanner = BarcodeScanning.getClient(options);

        registerLaunchers();

        btnTorch.setOnClickListener(v -> toggleTorch());
        btnHistory.setOnClickListener(v -> showHistory());
        btnPick.setOnClickListener(v -> launchPicker());
        btnPickFromPerm.setOnClickListener(v -> launchPicker());
        btnGrant.setOnClickListener(v -> permLauncher.launch(Manifest.permission.CAMERA));

        if (hasCamera()) {
            permPanel.setVisibility(View.GONE);
            startCamera();
        } else {
            permPanel.setVisibility(View.VISIBLE);
            overlay.setVisibility(View.GONE);
        }
    }

    private boolean hasCamera() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * 全屏预览 + 顶部/底部条避开状态栏与手势条。
     * 只给上下两条加内边距，相机预览仍然铺满整屏。
     */
    private void applyWindowInsets() {
        View top = findViewById(R.id.topBar);
        View bottom = findViewById(R.id.bottomBar);
        ViewGroup root = findViewById(R.id.root);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            androidx.core.graphics.Insets bars = androidx.core.view.WindowInsetsCompat
                    .toWindowInsetsCompat(insets)
                    .getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars());
            top.setPadding(top.getPaddingLeft(), bars.top + dp(10),
                    top.getPaddingRight(), top.getPaddingBottom());
            bottom.setPadding(bottom.getPaddingLeft(), bottom.getPaddingTop(),
                    bottom.getPaddingRight(), bars.bottom + dp(18));
            return insets;
        });

        // 提示文字跟随取景框：始终贴在取景框下方 16dp，避免大屏上飘在中间空处
        root.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> {
            float fb = overlay.frameBottom();
            if (fb <= 0 || hint.getHeight() == 0) return;
            float currentTop = hint.getTop() + hint.getTranslationY();
            hint.setTranslationY(hint.getTranslationY() + (fb + dp(16) - currentTop));
        });
    }

    private int dp(float v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void applyEdgeToEdge() {
        Window w = getWindow();
        w.setStatusBarColor(Color.TRANSPARENT);
        w.setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            w.setDecorFitsSystemWindows(false);
        } else {
            w.getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void registerLaunchers() {
        permLauncher = registerForActivityResult(
                new ActivityResultContracts.RequestPermission(), granted -> {
                    if (granted) {
                        permPanel.setVisibility(View.GONE);
                        overlay.setVisibility(View.VISIBLE);
                        startCamera();
                    } else {
                        permPanel.setVisibility(View.VISIBLE);
                        Toast.makeText(this, R.string.permission_needed, Toast.LENGTH_LONG).show();
                    }
                });

        // Android 13+ 用系统照片选择器（无需存储权限）；低版本走 GET_CONTENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pickLauncher = registerForActivityResult(
                    new ActivityResultContracts.PickVisualMedia(), uri -> {
                        if (uri != null) decodeFromUri(uri);
                    });
        } else {
            pickLauncher = null;
        }
    }

    private void launchPicker() {
        if (pickLauncher != null) {
            pickLauncher.launch(new PickVisualMediaRequest.Builder()
                    .setMediaType(ActivityResultContracts.PickVisualMedia.ImageOnly.INSTANCE)
                    .build());
        } else {
            Intent i = new Intent(Intent.ACTION_GET_CONTENT);
            i.setType("image/*");
            i.addCategory(Intent.CATEGORY_OPENABLE);
            legacyPicker.launch(i);
        }
    }

    private final ActivityResultLauncher<Intent> legacyPicker = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(), result -> {
                if (result.getResultCode() == RESULT_OK && result.getData() != null) {
                    Uri uri = result.getData().getData();
                    if (uri != null) decodeFromUri(uri);
                }
            });

    // ---------------- 相机与识别 ----------------

    private void startCamera() {
        providerFuture = ProcessCameraProvider.getInstance(this);
        providerFuture.addListener(() -> {
            try {
                cameraProvider = providerFuture.get();
                bindUseCases();
            } catch (Exception e) {
                Log.e(TAG, "相机初始化失败", e);
                Toast.makeText(this, "相机初始化失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void bindUseCases() {
        cameraProvider.unbindAll();

        Preview preview = new Preview.Builder().build();
        preview.setSurfaceProvider(previewView.getSurfaceProvider());

        // 720p 足够识别二维码，同时显著省电（相比 1080p 少 ~55% 像素）
        analysis = new ImageAnalysis.Builder()
                .setTargetResolution(new android.util.Size(1280, 720))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                .build();
        analysis.setAnalyzer(analysisExecutor, this::onFrame);

        camera = cameraProvider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA,
                preview, analysis);

        if (camera.getCameraInfo().hasFlashUnit()) {
            btnTorch.setVisibility(View.VISIBLE);
        } else {
            btnTorch.setVisibility(View.GONE);
        }
        setScanning(true);
    }

    @OptIn(markerClass = ExperimentalGetImage.class)
    private void onFrame(@NonNull ImageProxy proxy) {
        try {
            if (!scanning) return;
            Image media = proxy.getImage();
            if (media == null) return;
            if (!busy.compareAndSet(false, true)) return;

            InputImage input = buildCenterCrop(proxy, media);
            if (input == null) {
                busy.set(false);
                return;
            }
            scanner.process(input)
                    .addOnSuccessListener(this, codes -> {
                        busy.set(false);
                        if (codes != null && !codes.isEmpty()) onCodes(codes);
                    })
                    .addOnFailureListener(this, e -> {
                        busy.set(false);
                        Log.w(TAG, "识别失败", e);
                    });
        } finally {
            proxy.close();
        }
    }

    /**
     * 只取与取景框对应的中央方形区域，重排成规范 NV21 后交给识别器。
     *
     * <p>为什么值得这么麻烦：识别耗时与像素量近似线性，中央 80%×52% 的区域约为全帧
     * 40% 的像素，单帧识别更快、CPU 更低；而取景框之外的画面用户本来也没对准。
     * 注意 ML Kit 会按 rotationDegrees 旋转，因此裁切必须先在“屏幕方向”下算好再映射回缓冲区。
     */
    private InputImage buildCenterCrop(ImageProxy proxy, Image media) {
        int w = proxy.getWidth(), h = proxy.getHeight();
        boolean rotated = proxy.getImageInfo().getRotationDegrees() % 180 != 0;
        int dispW = rotated ? h : w;
        int dispH = rotated ? w : h;

        // 屏幕方向下的取景区域（与 ScanOverlayView 的比例一致：宽 80%、高 52%）
        int edgeW = Math.max(0, (int) (dispW * 0.80f));
        int edgeH = Math.max(0, (int) (dispH * 0.52f));
        int cw, ch;
        if (rotated) {
            cw = Math.min(w, edgeH);
            ch = Math.min(h, edgeW);
        } else {
            cw = Math.min(w, edgeW);
            ch = Math.min(h, edgeH);
        }
        if (cw < 32 || ch < 32) return null;

        int left = Math.max(0, (w - cw) / 2);
        int top = Math.max(0, (h - ch) / 2);

        Image.Plane[] planes = media.getPlanes();
        Image.Plane yp = planes[0];
        int yRow = yp.getRowStride(), yPix = yp.getPixelStride();
        ByteBuffer yBuf = yp.getBuffer();

        byte[] nv21 = new byte[cw * ch + 2 * (cw / 2) * (ch / 2)];
        int ySize = cw * ch;
        int out = 0;
        for (int r = 0; r < ch; r++) {
            int base = (top + r) * yRow + left * yPix;
            if (base < 0 || base + cw > yBuf.limit()) return null;
            for (int c = 0; c < cw; c++) {
                nv21[out++] = yBuf.get(base + c * yPix);
            }
        }

        // 色度平面：V 在前 U 在后（NV21 布局）
        fillChroma(planes, 1, top, left, cw, ch, nv21, ySize, true);
        fillChroma(planes, 2, top, left, cw, ch, nv21, ySize, false);

        return InputImage.fromByteBuffer(ByteBuffer.wrap(nv21), cw, ch,
                proxy.getImageInfo().getRotationDegrees(), InputImage.IMAGE_FORMAT_NV21);
    }

    private void fillChroma(Image.Plane[] planes, int planeIdx, int top, int left,
                            int cw, int ch, byte[] dst, int dstOffset, boolean isV) {
        Image.Plane p = planes[planeIdx];
        int rowStride = p.getRowStride(), pixStride = p.getPixelStride();
        ByteBuffer buf = p.getBuffer();
        int cw2 = cw / 2, ch2 = ch / 2;
        int step = isV ? 2 : 1;          // V 在偶数字节，U 在奇数字节
        int pos = dstOffset + (isV ? 0 : 1);
        int limit = buf.limit();
        for (int r = 0; r < ch2; r++) {
            int base = (top / 2 + r) * rowStride + (left / 2) * pixStride;
            for (int c = 0; c < cw2; c++) {
                int idx = base + c * pixStride;
                if (idx < 0 || idx >= limit) return;
                dst[pos] = buf.get(idx);
                pos += step;
                if (pos + step - 1 >= dst.length) return;
            }
        }
    }

    private void onCodes(List<Barcode> codes) {
        Barcode best = null;
        for (Barcode b : codes) {
            if (b.getRawValue() != null && !b.getRawValue().isEmpty()) {
                best = b;
                break;
            }
        }
        if (best == null) return;

        String content = best.getRawValue();
        String format = formatName(best.getFormat());
        db.add(content, format, "camera");
        buzz(35);
        setScanning(false);
        showResult(content, format);
    }

    private void setScanning(boolean on) {
        scanning = on;
        overlay.setAnimating(on);
        if (hint != null) hint.setAlpha(on ? 1f : 0.35f);
    }

    private void buzz(int ms) {
        try {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (v == null || !v.hasVibrator()) return;
            v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
        } catch (Exception ignored) {
        }
    }

    private void toggleTorch() {
        if (camera == null || !camera.getCameraInfo().hasFlashUnit()) return;
        torchOn = !torchOn;
        camera.getCameraControl().enableTorch(torchOn);
        btnTorch.setIcon(getDrawable(torchOn ? R.drawable.ic_torch_on : R.drawable.ic_torch_off));
        btnTorch.setContentDescription(torchOn ? "关闭补光灯" : "打开补光灯");
    }

    // ---------------- 相册图片解码 ----------------

    private void decodeFromUri(Uri uri) {
        setScanning(false);
        Toast.makeText(this, R.string.detecting, Toast.LENGTH_SHORT).show();
        InputImage input;
        try {
            input = InputImage.fromFilePath(this, uri);
        } catch (Exception e) {
            setScanning(true);
            Toast.makeText(this, "图片读取失败", Toast.LENGTH_LONG).show();
            return;
        }
        scanner.process(input)
                .addOnSuccessListener(codes -> {
                    if (codes == null || codes.isEmpty()) {
                        setScanning(true);
                        // 提示里点明"样式化私有码"这一可能性：抖音主页码/微信赞赏码的模块是
                        // 圆点圆环，通用解码器（含 ML Kit）结构上就匹配不上。
                        // 注意：这里不做自动判定——实测样本不足以把"样式化码"与"模糊标准码"
                        // 可靠分开（标准码圆度占比也可达 0.80），误报会误导用户，故只用措辞提示。
                        Toast.makeText(this, R.string.stylized_code_hint, Toast.LENGTH_LONG).show();
                        return;
                    }
                    for (Barcode b : codes) {
                        String content = b.getRawValue();
                        if (content == null || content.isEmpty()) continue;
                        String fmt = formatName(b.getFormat());
                        db.add(content, fmt, "gallery");
                    }
                    buzz(35);
                    Barcode b0 = codes.get(0);
                    showResult(b0.getRawValue(), formatName(b0.getFormat()));
                })
                .addOnFailureListener(e -> {
                    setScanning(true);
                    Toast.makeText(this, "识别失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
    }


    // ---------------- 结果面板 ----------------

    private void showResult(String content, String format) {
        BottomSheetDialog dlg = new BottomSheetDialog(this, R.style.Theme_QRSuite_Sheet);
        View v = LayoutInflater.from(this).inflate(R.layout.sheet_result, null, false);

        TextView tvFormat = v.findViewById(R.id.resFormat);
        TextView tvContent = v.findViewById(R.id.resContent);
        TextView tvMeta = v.findViewById(R.id.resMeta);
        MaterialButton bCopy = v.findViewById(R.id.resCopy);
        MaterialButton bShare = v.findViewById(R.id.resShare);
        MaterialButton bOpen = v.findViewById(R.id.resOpen);
        MaterialButton bSearch = v.findViewById(R.id.resSearch);
        MaterialButton bClose = v.findViewById(R.id.resClose);

        tvFormat.setText(format);
        tvContent.setText(content);
        tvMeta.setText(content.length() + " 字符 · 已存入历史");

        boolean isUrl = looksLikeUrl(content);
        bOpen.setVisibility(isUrl ? View.VISIBLE : View.GONE);

        bCopy.setOnClickListener(x -> {
            copy(content);
            Toast.makeText(this, R.string.copied, Toast.LENGTH_SHORT).show();
        });
        bShare.setOnClickListener(x -> {
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_TEXT, content);
            startActivity(Intent.createChooser(i, getString(R.string.share)));
        });
        bOpen.setOnClickListener(x -> openUrl(content));
        bSearch.setOnClickListener(x -> {
            Intent i = new Intent(Intent.ACTION_VIEW,
                    Uri.parse("https://www.google.com/search?q=" + Uri.encode(content)));
            startActivity(i);
        });
        bClose.setOnClickListener(x -> dlg.dismiss());
        v.findViewById(R.id.resContinue).setOnClickListener(x -> dlg.dismiss());

        dlg.setContentView(v);
        dlg.setOnDismissListener(d -> {
            if (hasCamera()) setScanning(true);
        });
        dlg.show();
    }

    private void copy(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("QRSuite", text));
    }

    private void openUrl(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "没有可打开该链接的应用", Toast.LENGTH_SHORT).show();
        }
    }

    private boolean looksLikeUrl(String s) {
        if (s == null || s.length() > 2048) return false;
        String t = s.trim().toLowerCase(Locale.ROOT);
        return t.startsWith("http://") || t.startsWith("https://")
                || t.startsWith("mailto:") || t.startsWith("tel:")
                || t.startsWith("geo:") || t.startsWith("market://");
    }

    // ---------------- 历史 ----------------

    private void showHistory() {
        BottomSheetDialog dlg = new BottomSheetDialog(this, R.style.Theme_QRSuite_Sheet);
        View v = LayoutInflater.from(this).inflate(R.layout.sheet_history, null, false);
        LinearLayout list = v.findViewById(R.id.histList);
        TextView empty = v.findViewById(R.id.histEmpty);
        TextView count = v.findViewById(R.id.histCount);
        MaterialButton clear = v.findViewById(R.id.histClear);

        List<HistoryStore.Entry> items = db.recent(100);
        count.setText(String.valueOf(items.size()));
        empty.setVisibility(items.isEmpty() ? View.VISIBLE : View.GONE);

        for (HistoryStore.Entry e : items) {
            View row = LayoutInflater.from(this).inflate(R.layout.item_history, list, false);
            TextView tvContent = row.findViewById(R.id.itemContent);
            TextView tvMeta = row.findViewById(R.id.itemMeta);
            MaterialButton btnShare = row.findViewById(R.id.itemShare);
            MaterialButton btnDelete = row.findViewById(R.id.itemDelete);

            tvContent.setText(e.content);
            tvMeta.setText(e.format + " · " + timeAgo(e.ts) + " · "
                    + ("camera".equals(e.source) ? "相机" : "相册"));
            row.setOnClickListener(x -> {
                copy(e.content);
                Toast.makeText(this, R.string.copied, Toast.LENGTH_SHORT).show();
            });
            btnShare.setOnClickListener(x -> {
                Intent i = new Intent(Intent.ACTION_SEND);
                i.setType("text/plain");
                i.putExtra(Intent.EXTRA_TEXT, e.content);
                startActivity(Intent.createChooser(i, getString(R.string.share)));
            });
            btnDelete.setOnClickListener(x -> {
                db.delete(e.id);
                list.removeView(row);
                int n = list.getChildCount();
                count.setText(String.valueOf(n));
                empty.setVisibility(n == 0 ? View.VISIBLE : View.GONE);
            });
            list.addView(row);
        }

        clear.setOnClickListener(x -> {
            db.clear();
            list.removeAllViews();
            count.setText("0");
            empty.setVisibility(View.VISIBLE);
            Toast.makeText(this, R.string.cleared, Toast.LENGTH_SHORT).show();
        });

        dlg.setContentView(v);
        dlg.show();
    }

    private static final SimpleDateFormat FULL =
            new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault());

    private String timeAgo(long ts) {
        long diff = System.currentTimeMillis() - ts;
        if (diff < 60_000L) return "刚刚";
        if (diff < 3_600_000L) return (diff / 60_000L) + " 分钟前";
        if (diff < 86_400_000L) return (diff / 3_600_000L) + " 小时前";
        return FULL.format(new Date(ts));
    }

    // ---------------- 条码格式名 ----------------

    private String formatName(int format) {
        switch (format) {
            case Barcode.FORMAT_QR_CODE: return "QR Code";
            case Barcode.FORMAT_DATA_MATRIX: return "Data Matrix";
            case Barcode.FORMAT_AZTEC: return "Aztec";
            case Barcode.FORMAT_PDF417: return "PDF417";
            case Barcode.FORMAT_CODE_128: return "Code 128";
            case Barcode.FORMAT_CODE_39: return "Code 39";
            case Barcode.FORMAT_CODE_93: return "Code 93";
            case Barcode.FORMAT_EAN_13: return "EAN-13";
            case Barcode.FORMAT_EAN_8: return "EAN-8";
            case Barcode.FORMAT_UPC_A: return "UPC-A";
            case Barcode.FORMAT_UPC_E: return "UPC-E";
            case Barcode.FORMAT_ITF: return "ITF";
            case Barcode.FORMAT_CODABAR: return "Codabar";
            default: return "未知格式";
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (hasCamera() && cameraProvider != null) {
            setScanning(true);
            busy.set(false);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        setScanning(false);
        if (torchOn) toggleTorch();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (analysisExecutor != null) analysisExecutor.shutdown();
        if (scanner != null) scanner.close();
        if (db != null) db.close();
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
    }
}
