@echo off
rem QRSuite Android build wrapper (Windows).
rem NOTE: this file starts with chcp 65001 on purpose. cmd.exe parses .bat files using the
rem OEM codepage, so a UTF-8 batch file containing non-ASCII paths would otherwise be
rem mangled byte-by-byte (symptoms: "'droid' is not recognized as an internal command").
chcp 65001 >nul
setlocal

rem 1) 优先用仓库自带的 Gradle wrapper（可移植，别人 clone 下来也能构建）
if exist "%~dp0gradlew.bat" (
  set "GRADLE_EXE=%~dp0gradlew.bat"
) else (
  rem 2) 回退到本机安装的 Gradle（下面这些是本机路径，换机器需自行调整）
  set "JAVA_HOME=E:\Program Files\Java\jdk-21.0.11"
  set "GRADLE_USER_HOME=E:\学习\Android\.gradle"
  set "GRADLE_EXE=E:\学习\Android\gradle\gradle-8.11.1\bin\gradle.bat"
)

rem Android SDK：优先用环境变量；都没有时由 local.properties 的 sdk.dir 决定
if not defined ANDROID_HOME set "ANDROID_HOME=E:\学习\Android\sdk"
if not defined ANDROID_SDK_ROOT set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
if not defined ANDROID_USER_HOME set "ANDROID_USER_HOME=E:\学习\Android\.android"
set "LANG=en_US.UTF-8"

if "%~1"=="" (
  set "TASK=:app:assembleRelease"
) else (
  set "TASK=%~1"
)

call "%GRADLE_EXE%" --no-daemon --console=plain %TASK%
exit /b %ERRORLEVEL%
