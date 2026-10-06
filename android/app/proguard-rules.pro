# ML Kit / CameraX 在 R8 全量混淆下的常规保留项
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_vision_barcode.** { *; }
-dontwarn com.google.mlkit.**

# 保留行号，便于真机崩溃定位
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
