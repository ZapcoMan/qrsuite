# 生成 24x24 的 Android vector drawable（路径已按 24 单位手写，不做数值缩放）
import pathlib

OUT = pathlib.Path(r'E:\学习\qcode\07-android\app\src\main\res\drawable')

ICONS = {
    # 手电筒（关）：灯头 + 灯身
    'ic_torch_off': [
        'M8,2h8v2.2l-1.3,1.5V21a2.7,2.7 0 0 1 -5.4,0V5.7L8,4.2Z',
    ],
    # 手电筒（开）：附加光晕
    'ic_torch_on': [
        'M8,2h8v2.2l-1.3,1.5V21a2.7,2.7 0 0 1 -5.4,0V5.7L8,4.2Z',
        'M3.4,4.6l1.7,1.7 -1.7,1.7 -1.7,-1.7Z',
        'M20.6,4.6l1.7,1.7 -1.7,1.7 -1.7,-1.7Z',
        'M12,0.4l1.6,2.6h-3.2Z',
    ],
    # 历史（时钟 + 回退箭头）
    'ic_history': [
        'M12,4a8,8 0 1 0 7.7,10H17.6A6,6 0 1 1 12,6a6,6 0 0 1 3.9,1.5L13,10.4h7V3.5l-2.6,2.6A8,8 0 0 0 12,4Z',
        'M11.2,8h1.7v3.6l2.9,1.7 -0.85,1.45 -3.75,-2.2Z',
    ],
    # 相册
    'ic_gallery': [
        'M3,5h18a1.5,1.5 0 0 1 1.5,1.5v11A1.5,1.5 0 0 1 21,19H3a1.5,1.5 0 0 1 -1.5,-1.5v-11A1.5,1.5 0 0 1 3,5Zm0.5,11h17v-2.6l-4,-4 -3.6,3.6 -2.6,-2.6 -6.8,6.8Z',
        'M8.2,8.1a1.8,1.8 0 1 1 0,3.6 1.8,1.8 0 0 1 0,-3.6Z',
    ],
    # 复制
    'ic_copy': [
        'M9,1.5h9.5A1.5,1.5 0 0 1 20,3v12.5A1.5,1.5 0 0 1 18.5,17H9a1.5,1.5 0 0 1 -1.5,-1.5V3A1.5,1.5 0 0 1 9,1.5Zm0.3,2.2V14h8.9V3.7Z',
        'M4.5,6.5H7v2.2H5.7V20h9.1v-1.3h2.2v1.8A1.5,1.5 0 0 1 15.5,22h-9.8A1.5,1.5 0 0 1 4.2,20.5V8A1.5,1.5 0 0 1 4.5,6.5Z',
    ],
    # 分享（三节点连线）
    'ic_share': [
        'M18,15.4a3,3 0 0 0 -1.9,0.7l-6.4,-3.7a3,3 0 0 0 0,-0.8l6.3,-3.7A3,3 0 1 0 15,5.6l-6.3,3.7a3,3 0 1 0 0,5.4L15,18.4A3,3 0 1 0 18,15.4Z',
    ],
    # 外部打开
    'ic_open': [
        'M13.5,3H21v7.5h-2.2V6.8l-7.6,7.6 -1.6,-1.6 7.6,-7.6H13.5Z',
        'M19,19H5V5h5.5V2.8H5A2,2 0 0 0 3,4.8V19a2,2 0 0 0 2,2h14a2,2 0 0 0 2,-2v-5.5h-2.2Z',
    ],
    # 搜索
    'ic_search': [
        'M10.5,3a7.5,7.5 0 1 0 4.6,13.4l4.3,4.3 1.7,-1.7 -4.3,-4.3A7.5,7.5 0 0 0 10.5,3Zm0,2.2a5.3,5.3 0 1 1 0,10.6 5.3,5.3 0 0 1 0,-10.6Z',
    ],
    # 删除
    'ic_delete': [
        'M9,2h6l1,1.2h4.2v2.2H3.8V3.2H8Z',
        'M5.2,7h13.6v12.8A2.2,2.2 0 0 1 16.6,22H7.4A2.2,2.2 0 0 1 5.2,19.8Zm3.2,2.2v10.6h2.1V9.2Zm5.3,0v10.6h2.1V9.2Z',
    ],
    # 关闭
    'ic_close': [
        'M18.4,5.6l-1.6,-1.6L12,8.8 7.2,4 5.6,5.6 10.4,10.4 5.6,15.2l1.6,1.6L12,12l4.8,4.8 1.6,-1.6L13.6,10.4Z',
    ],
    # 二维码（品牌标志）
    'ic_qr': [
        'M3,3h8v8H3Zm2,2v4h4V5Z',
        'M13,3h8v8h-8Zm2,2v4h4V5Z',
        'M3,13h8v8H3Zm2,2v4h4v-4Z',
        'M13,13h3.2v3.2H13Zm4.8,0H21v3.2h-3.2Zm-4.8,4.8H16.2V21H13Zm4.8,1.6H21V21h-3.2Z',
    ],
    # 对勾
    'ic_check': [
        'M9.2,16.6L4.6,12l-1.6,1.6 6.2,6.2L21,8.2 19.4,6.6Z',
    ],
}

for name, paths in ICONS.items():
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<vector xmlns:android="http://schemas.android.com/apk/res/android"',
             '    android:width="24dp"',
             '    android:height="24dp"',
             '    android:viewportWidth="24"',
             '    android:viewportHeight="24">']
    for d in paths:
        lines.append('    <path')
        lines.append('        android:fillColor="#FFFFFFFF"')
        lines.append(f'        android:pathData="{d}" />')
    lines.append('</vector>')
    (OUT / f'{name}.xml').write_text('\n'.join(lines) + '\n', encoding='utf-8')

print('generated:', len(ICONS), 'icons')
