#!/usr/bin/env python3
"""
APK下载路径修复工具

这个脚本用于处理前端传递的错误路径格式，重建正确的文件路径。
"""

import re
from pathlib import Path

def fix_apk_path(broken_path: str) -> str:
    """
    修复损坏的APK文件路径

    Args:
        broken_path: 损坏的路径，如 "D%3AdevprojectgovCarAppPluginappuildoutputsapkeleaseGovCarApp_3.0.30(330)_release_202510161634.apk"

    Returns:
        修复后的完整路径
    """
    # 移除URL编码
    from urllib.parse import unquote
    decoded_path = unquote(broken_path)

    print(f"修复前: {decoded_path}")

    # 如果路径包含反斜杠，直接返回
    if "\\" in decoded_path:
        return decoded_path

    # 如果路径缺少反斜杠，尝试重建
    if "D:" in decoded_path and "GovCarApp" in decoded_path and ".apk" in decoded_path:
        # 提取文件名
        filename_match = re.search(r'GovCarApp_.*\.apk', decoded_path)
        if filename_match:
            filename = filename_match.group(0)

            # 基于最新的构建结果，重建可能的路径
            possible_base_paths = [
                "D:\\dev\\project\\govCarAppPlugin\\app\\build\\outputs\\apk\\release",
                "D:\\dev\\project\\govCarAppPlugin\\build\\outputs\\apk\\release",
                "D:\\dev\\project\\govCarAppPlugin\\app\\build\\outputs\\apk",
                "D:\\dev\\project\\govCarAppPlugin\\build\\outputs\\apk"
            ]

            # 尝试找到实际存在的文件
            for base_path in possible_base_paths:
                full_path = f"{base_path}\\{filename}"
                if Path(full_path).exists():
                    print(f"修复后: {full_path}")
                    return full_path

            # 如果找不到文件，返回最可能的路径
            most_likely_path = f"D:\\dev\\project\\govCarAppPlugin\\app\\build\\outputs\\apk\\release\\{filename}"
            print(f"最可能路径: {most_likely_path}")
            return most_likely_path

    # 如果无法识别，返回原路径
    return decoded_path

def test_path_fix():
    """测试路径修复功能"""
    test_cases = [
        "D%3AdevprojectgovCarAppPluginappuildoutputsapkeleaseGovCarApp_3.0.30(330)_release_202510161634.apk",
        "D%3A%5Cdev%5Cproject%5CgovCarAppPlugin%5Capp%5Cbuild%5Coutputs%5Capk%5Crelease%5CGovCarApp_3.0.30(330)_release_202510161634.apk"
        "D:\\dev\\project\\govCarAppPlugin\\app\\build\\outputs\\apk\\release\\GovCarApp_3.0.30(330)_release_202510161634.apk"
    ]

    for test_path in test_cases:
        print(f"\n测试路径: {test_path}")
        fixed_path = fix_apk_path(test_path)
        print(f"文件存在: {Path(fixed_path).exists()}")
        print("-" * 50)

if __name__ == "__main__":
    test_path_fix()