# ML Kit / CameraX 在 R8 全量混淆下的常规保留项
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_vision_barcode.** { *; }
-dontwarn com.google.mlkit.**

# 保留行号，便于真机崩溃定位
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# 样式化私有码结构判定：纯计算类、无反射，理论上被 R8 处理也不会改变行为；
# 但它的正确性依赖与 Python 参考实现逐位一致的浮点顺序（已用 16 张样本做一致性回归），
# 因此显式保留类与方法，避免激进内联/重排后难以定位的精度漂移。
-keep class com.qrsuite.scanner.StylizedDetector { *; }
-keep class com.qrsuite.scanner.StylizedDetector$* { *; }
