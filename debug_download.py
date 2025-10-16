#!/usr/bin/env python3
"""
调试文件下载路径解析问题
"""

import sys
import os
from pathlib import Path
from urllib.parse import unquote
import re

def debug_path_parsing(file_path: str):
    """调试路径解析逻辑"""
    print(f"原始URL参数: {file_path}")

    # 解码URL编码的文件路径
    decoded_path = unquote(file_path)
    print(f"解码后路径: {decoded_path}")

    # 清理路径中的控制字符
    # 移除控制字符（ASCII 0-31, 127）
    cleaned_path = re.sub(r'[\x00-\x1f\x7f]', '', decoded_path)
    # 规范化路径分隔符
    cleaned_path = cleaned_path.replace('\\', '/')

    # 如果路径看起来不完整，尝试重新构建
    if not cleaned_path.startswith('D:') and 'D:' in decoded_path:
        # 尝试提取D:路径部分
        d_match = re.search(r'D:.*?\.apk', decoded_path, re.IGNORECASE)
        if d_match:
            cleaned_path = d_match.group(0).replace('\\', '/')

    print(f"清理后路径: {cleaned_path}")

    # 安全验证：确保文件路径在允许的范围内
    # 防止路径遍历攻击
    normalized_path = Path(cleaned_path).resolve()
    print(f"规范化路径: {normalized_path}")

    # 允许的目录列表（更宽松的验证）
    allowed_directories = [
        Path.cwd(),  # 当前工作目录
        Path.cwd() / "build_outputs",  # 构建输出目录
        Path.cwd() / "uploads",  # 上传目录
        # 常见的Android项目目录
        Path("D:\\dev\\project"),  # D:\dev\project
        Path("D:/dev/project"),    # D:/dev/project (Unix风格路径)
    ]

    print(f"允许的目录: {[str(d) for d in allowed_directories]}")

    # 检查文件路径是否在允许的目录内
    is_allowed = False
    for i, allowed_dir in enumerate(allowed_directories):
        if allowed_dir.exists():
            try:
                relative_path = normalized_path.relative_to(allowed_dir.resolve())
                print(f"路径验证成功: {normalized_path} 在允许目录 {allowed_dir} 内，相对路径: {relative_path}")
                is_allowed = True
                break
            except ValueError:
                print(f"路径验证失败: {normalized_path} 不在目录 {allowed_dir} 内")
                continue
        else:
            print(f"允许目录不存在: {allowed_dir}")

    # 如果不在预定义目录中，允许绝对路径但进行基本安全检查
    if not is_allowed and normalized_path.is_absolute():
        print(f"绝对路径安全检查: {normalized_path}")
        # 基本安全检查：确保不是系统关键目录
        system_dirs = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "/bin", "/usr/bin", "/etc"]
        is_system_dir = any(str(normalized_path).lower().startswith(sys_dir.lower()) for sys_dir in system_dirs)
        print(f"系统目录检查结果: {is_system_dir}")
        if not is_system_dir:
            is_allowed = True
            print(f"绝对路径检查通过，允许访问: {normalized_path}")

    print(f"文件是否存在: {normalized_path.exists()}")
    print(f"是否为文件: {normalized_path.is_file()}")

    return is_allowed, normalized_path

if __name__ == "__main__":
    # 测试路径
    test_path = "D%3A%5Cdev%5Cproject%5CgovCarAppPlugin%5Capp%5Cbuild%5Coutputs%5Capk%5Crelease%5CGovCarApp_3.0.30(330)_release_202510161618.apk"

    is_allowed, normalized_path = debug_path_parsing(test_path)

    print(f"\n最终结果:")
    print(f"允许访问: {is_allowed}")
    print(f"最终路径: {normalized_path}")