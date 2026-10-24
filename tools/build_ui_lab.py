"""构建 UI 布局编辑器单文件成品：ui_layout_lab.html。

源文件 ui_layout_lab.src.html 中的 __FONT12__/__FONT16__ 占位符会被
凤凰点阵体 TTF 的 base64 内嵌替换——浏览器从 file:// 打开时外链字体
会受 CORS 限制，内嵌后双击即用、零依赖。

运行：python tools/build_ui_lab.py
"""
import base64
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根


def main():
    """读源文件 -> 内嵌两份字体 base64 -> 写出成品并报告体积。"""
    src = open(os.path.join(ROOT, "ui_layout_lab.src.html"), encoding="utf-8").read()
    f12 = base64.b64encode(open(os.path.join(
        ROOT, "assets", "fonts", "VonwaonBitmap-12px.ttf"), "rb").read()).decode()
    f16 = base64.b64encode(open(os.path.join(
        ROOT, "assets", "fonts", "VonwaonBitmap-16px.ttf"), "rb").read()).decode()
    out = src.replace("__FONT12__", f12).replace("__FONT16__", f16)
    dst = os.path.join(ROOT, "ui_layout_lab.html")
    open(dst, "w", encoding="utf-8").write(out)
    print(f"written: {dst} ({os.path.getsize(dst)/1048576:.1f} MB)")


if __name__ == "__main__":
    main()
