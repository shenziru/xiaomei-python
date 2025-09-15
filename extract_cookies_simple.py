#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版Cookie提取工具
非交互式，直接从文件读取curl命令
"""

import re
import json
import os
from typing import Dict, List

def extract_cookies_from_curl(curl_command: str) -> List[Dict[str, str]]:
    """从curl命令中提取cookie"""
    cookies = []
    
    # 查找 -b 或 --cookie 参数
    cookie_pattern = r"-b\s+'([^']+)'|--cookie\s+'([^']+)'|-b\s+\"([^\"]+)\"|--cookie\s+\"([^\"]+)\""
    matches = re.findall(cookie_pattern, curl_command)
    
    if not matches:
        # 尝试查找 -H 'cookie: ...' 格式
        header_pattern = r"-H\s+'cookie:\s*([^']+)'|-H\s+\"cookie:\s*([^\"]+)\""
        matches = re.findall(header_pattern, curl_command, re.IGNORECASE)
    
    for match in matches:
        cookie_string = next(filter(None, match))
        if cookie_string:
            # 解析cookie字符串
            cookie_pairs = cookie_string.split(';')
            for pair in cookie_pairs:
                if '=' in pair:
                    name, value = pair.strip().split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip()
                    })
    
    return cookies

def extract_headers_from_curl(curl_command: str) -> Dict[str, str]:
    """从curl命令中提取重要的请求头"""
    headers = {}
    
    # 提取所有 -H 参数
    header_pattern = r"-H\s+'([^:]+):\s*([^']+)'|-H\s+\"([^:]+):\s*([^\"]+)\""
    matches = re.findall(header_pattern, curl_command)
    
    important_headers = [
        'user-agent', 'x-s', 'x-s-common', 'x-t', 'x-xray-traceid',
        'x-b3-traceid', 'referer', 'origin'
    ]
    
    for match in matches:
        if match[0] and match[1]:  # 单引号格式
            header_name = match[0].strip().lower()
            header_value = match[1].strip()
        elif match[2] and match[3]:  # 双引号格式
            header_name = match[2].strip().lower()
            header_value = match[3].strip()
        else:
            continue
        
        if header_name in important_headers:
            headers[header_name] = header_value
    
    return headers

def format_cookies_for_config(cookies: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """格式化cookie用于配置文件"""
    # 过滤重要的cookie
    important_cookies = [
        'web_session', 'a1', 'webId', 'gid', 'abRequestId', 
        'customerClientId', 'customer-sso-sid', 'access-token-creator.xiaohongshu.com',
        'galaxy_creator_session_id', 'galaxy.creator.beaker.session.id',
        'xsecappid', 'acw_tc', 'websectiga', 'sec_poison_id'
    ]
    
    filtered_cookies = []
    for cookie in cookies:
        if cookie['name'] in important_cookies:
            filtered_cookies.append(cookie)
    
    return filtered_cookies

def update_config_with_cookies(cookies: List[Dict[str, str]], headers: Dict[str, str] = None):
    """更新配置文件中的cookie信息"""
    config_file = 'config.json'
    
    try:
        # 读取现有配置
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {
                'target_user_id': '58953dcb3460945280efcf7b',
                'email': {},
                'monitor_interval': 5,
                'max_notes_per_check': 20,
                'max_comments_per_note': 50
            }
        
        # 更新cookie信息
        config['cookies'] = cookies
        
        # 更新请求头信息
        if headers:
            config['headers'] = headers
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 配置已更新，添加了 {len(cookies)} 个cookie")
        if headers:
            print(f"✅ 同时添加了 {len(headers)} 个请求头")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新配置失败: {e}")
        return False

def main():
    """主函数"""
    print("🍪 简化版Cookie提取工具")
    print("=" * 50)
    
    # 方法1: 从命令行参数读取
    import sys
    if len(sys.argv) > 1:
        curl_command = ' '.join(sys.argv[1:])
        print("从命令行参数读取curl命令")
    else:
        # 方法2: 从文件读取
        curl_file = 'curl_command.txt'
        if os.path.exists(curl_file):
            try:
                with open(curl_file, 'r', encoding='utf-8') as f:
                    curl_command = f.read().strip()
                print(f"从文件 {curl_file} 读取curl命令")
            except Exception as e:
                print(f"❌ 读取文件失败: {e}")
                return
        else:
            print("❌ 未找到curl命令")
            print("请使用以下方式之一:")
            print("1. 创建 curl_command.txt 文件并粘贴curl命令")
            print("2. 直接作为命令行参数传递:")
            print("   python3 extract_cookies_simple.py 'curl命令内容'")
            return
    
    if not curl_command:
        print("❌ curl命令为空")
        return
    
    print(f"📝 curl命令长度: {len(curl_command)} 字符")
    
    # 提取cookie和请求头
    cookies = extract_cookies_from_curl(curl_command)
    headers = extract_headers_from_curl(curl_command)
    
    if not cookies:
        print("❌ 未找到cookie信息")
        print("请确保curl命令包含 -b 或 -H 'cookie: ...' 参数")
        return
    
    print(f"🔍 从curl命令中提取到 {len(cookies)} 个cookie")
    
    # 过滤重要cookie
    filtered_cookies = format_cookies_for_config(cookies)
    print(f"📋 筛选出 {len(filtered_cookies)} 个重要cookie")
    
    # 显示提取的cookie
    print("\n提取的Cookie:")
    for cookie in filtered_cookies:
        print(f"  {cookie['name']}: {cookie['value'][:20]}...")
    
    if headers:
        print(f"\n提取的请求头: {list(headers.keys())}")
    
    # 更新配置
    success = update_config_with_cookies(filtered_cookies, headers)
    
    if success:
        print("\n🎉 Cookie提取和配置更新完成！")
        print("现在可以运行监控程序:")
        print("  python3 xhs_smart_monitor.py")
    else:
        print("\n❌ 配置更新失败")

if __name__ == "__main__":
    main()
