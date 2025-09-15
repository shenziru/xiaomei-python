#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易方式，避免读笔记详情出错，只抓主页，出现新笔记就发邮件！
小红书小美邀请码监控程序
- 修复笔记重复问题
- 改进邀请码提取逻辑
- 实现定时运行和邮件通知
- 保留config.json和curl_command.txt处理模式
"""

import json
import time
import re
import smtplib
import os
import logging
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import List, Dict, Set
import schedule
import hashlib
from dataclasses import dataclass
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('xhs_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class InviteCodeInfo:
    """邀请码信息"""
    content: str
    source: str  # 'note_title', 'note_content'
    note_id: str
    note_title: str
    note_url: str
    timestamp: str
    hash_id: str
    context: str

@dataclass
class NoteInfo:
    """笔记信息"""
    note_id: str
    title: str
    content: str
    url: str
    timestamp: str
    hash_id: str

class XHSMonitor:
    """小红书监控器"""
    
    def __init__(self, config_file='config.json'):
        """初始化监控器"""
        self.config = self.load_config(config_file)
        self.session = requests.Session()
        self.setup_session()
        self.history_file = 'invite_codes_history.json'
        self.notes_history_file = 'notes_history.json'
        self.known_codes = self.load_history()
        self.known_notes = self.load_notes_history()
        
        # 已知的笔记标题（从图片中可以看到）
        self.known_note_titles = [
            '9.15 | 小美邀请码更新',
            '9.13 | 小美邀请码更新',
            '💌一份关于小美邀请码的真诚说明与感谢～',
            '👋大家好，我是小美，今日上线！🎉等你体验',
            '官宣｜小美-AI生活小秘书，正式入驻小红书啦！'
        ]
        
        # 邀请码模式（从图片中可以看到GROWLUP和FUTURE）
        self.code_patterns = [
            r'GROWLUP',  # 图片中看到的邀请码
            r'FUTURE',   # 图片中看到的邀请码
            r'XIAOMEI[0-9]{2,6}',  # 小美+数字
            r'XM[A-Z0-9]{4,8}',  # 小美专属格式
            r'[A-Z]{6}',  # 6位大写字母
            r'XMGOOD',  # 已知的邀请码
            r'DAYONE',  # 已知的邀请码
        ]
        
        # 已知的邀请码列表
        self.known_invite_codes = ['FUTURE', 'GROWLUP', 'XMGOOD', 'DAYONE']
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                logger.info(f"成功加载配置文件: {config_file}")
                
                # 检查必要的配置项
                if 'target_user_id' not in config_data:
                    logger.warning("配置文件中缺少target_user_id，使用默认值: 58953dcb3460945280efcf7b")
                    config_data['target_user_id'] = "58953dcb3460945280efcf7b"
                
                # 检查邮件配置
                if 'email' not in config_data or not all(k in config_data['email'] for k in ['smtp_server', 'smtp_port', 'sender', 'password', 'receiver']):
                    logger.warning("邮件配置不完整，邮件通知可能无法正常工作")
                
                return config_data
        except FileNotFoundError:
            logger.error(f"配置文件 {config_file} 不存在")
            return {}
        except json.JSONDecodeError:
            logger.error(f"配置文件 {config_file} 格式错误")
            return {}
    
    def setup_session(self):
        """设置请求会话"""
        # 默认请求头
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 存储headers以便在其他方法中使用
        self.headers = default_headers.copy()
        
        # 如果配置文件中有headers，则更新
        if 'headers' in self.config and self.config['headers']:
            self.headers.update(self.config['headers'])
        
        self.session.headers.update(self.headers)
        
        # 添加cookie（如果配置中有的话）
        if 'cookies' in self.config and self.config['cookies']:
            logger.info(f"加载 {len(self.config['cookies'])} 个cookie")
            for cookie in self.config['cookies']:
                self.session.cookies.set(cookie['name'], cookie['value'])
        else:
            logger.warning("未配置cookie信息，可能无法获取完整内容")
    
    def load_history(self) -> Set[str]:
        """加载历史邀请码记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(item['hash_id'] for item in data)
            return set()
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            return set()
    
    def load_notes_history(self) -> Set[str]:
        """加载历史笔记记录"""
        try:
            if os.path.exists(self.notes_history_file):
                with open(self.notes_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(item['hash_id'] for item in data)
            return set()
        except Exception as e:
            logger.error(f"加载笔记历史记录失败: {e}")
            return set()
    
    def save_history(self, invite_codes: List[InviteCodeInfo]):
        """保存邀请码历史记录"""
        try:
            history = []
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            for code in invite_codes:
                history.append({
                    'content': code.content,
                    'source': code.source,
                    'note_id': code.note_id,
                    'note_title': code.note_title,
                    'note_url': code.note_url,
                    'timestamp': code.timestamp,
                    'hash_id': code.hash_id,
                    'context': code.context
                })
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def save_notes_history(self, notes: List[NoteInfo]):
        """保存笔记历史记录"""
        try:
            history = []
            if os.path.exists(self.notes_history_file):
                with open(self.notes_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            for note in notes:
                history.append({
                    'note_id': note.note_id,
                    'title': note.title,
                    'content': note.content[:200] + '...' if len(note.content) > 200 else note.content,  # 保存笔记内容摘要
                    'url': note.url,
                    'timestamp': note.timestamp,
                    'hash_id': note.hash_id
                })
            
            with open(self.notes_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存笔记历史记录失败: {e}")
    
    def generate_hash_id(self, content: str, source: str, context: str) -> str:
        """生成内容的唯一哈希ID"""
        text = f"{content}_{source}_{context[:50]}"
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get_user_page(self, user_url: str) -> str:
        """获取用户主页内容"""
        try:
            logger.info(f"获取用户主页: {user_url}")
            response = self.session.get(user_url, headers=self.headers, timeout=15)
            
            # 生成并保存curl命令，方便调试
            curl_command = f"curl -v "
            for header_name, header_value in self.headers.items():
                curl_command += f"-H '{header_name}: {header_value}' "
            curl_command += f"'{user_url}'"
            
            # 保存curl命令到文件
            with open("curl_command.txt", "w") as f:
                f.write(curl_command)
            
            if response.status_code == 200:
                logger.info(f"成功获取用户主页，内容长度: {len(response.text)}")
                return response.text
            else:
                logger.warning(f"获取用户主页失败: HTTP {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"获取用户主页异常: {e}")
            return ""
    
    def extract_notes_info(self, html_content: str) -> List[Dict]:
        """从HTML内容中提取笔记信息，确保每篇笔记只出现一次"""
        notes = []
        seen_titles = set()  # 用于去重
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 从页面文本中提取笔记信息
            page_text = soup.get_text()
            
            # 首先尝试提取已知的笔记标题
            for title in self.known_note_titles:
                if title in page_text and title not in seen_titles:
                    # 找到标题所在的段落
                    paragraphs = page_text.split('\n')
                    for i, para in enumerate(paragraphs):
                        if title in para:
                            # 提取标题及其后面的几个段落作为内容
                            content = para
                            for j in range(1, 5):  # 最多取后面4个段落
                                if i + j < len(paragraphs) and paragraphs[i + j].strip():
                                    content += '\n' + paragraphs[i + j].strip()
                            
                            notes.append({
                                'title': title,
                                'content': content,
                                'id': hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
                            })
                            seen_titles.add(title)
                            break
            
            # 如果没有找到足够的笔记，尝试从HTML中提取
            if len(notes) < len(self.known_note_titles):
                # 查找可能包含笔记的元素
                note_elements = soup.select('div.note, div.content, article, div.feed-card')
                
                for elem in note_elements:
                    title_elem = elem.select_one('h1, h2, h3, .title, .note-title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if title in self.known_note_titles and title not in seen_titles:
                            content = elem.get_text(strip=True)
                            notes.append({
                                'title': title,
                                'content': content,
                                'id': hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
                            })
                            seen_titles.add(title)
            
            # 如果仍然没有找到足够的笔记，尝试直接从HTML源码中查找
            if len(notes) < len(self.known_note_titles):
                for title in self.known_note_titles:
                    if title not in seen_titles:
                        # 尝试在HTML源码中查找标题
                        if title in html_content:
                            notes.append({
                                'title': title,
                                'content': f"找到标题: {title}",
                                'id': hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
                            })
                            seen_titles.add(title)
            
            logger.info(f"提取到 {len(notes)} 个笔记")
            return notes
            
        except Exception as e:
            logger.error(f"提取笔记信息失败: {e}")
            return []
    
    def detect_invite_codes(self, text: str) -> List[Dict]:
        """检测文本中的邀请码"""
        results = []
        found_positions = set()  # 记录已匹配的位置范围
        
        # 检查是否包含邀请码关键词
        invite_keywords = ['邀请码', '激活码', '内测码', '暗号', '口令', '新邀请码']
        text_lower = text.lower()
        
        # 首先直接检查是否包含已知的邀请码
        for code in self.known_invite_codes:
            if code in text:
                matches = re.finditer(re.escape(code), text)
                for match in matches:
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # 检查是否与已找到的代码位置重叠
                    is_overlapping = any(
                        not (end_pos <= existing_start or start_pos >= existing_end)
                        for existing_start, existing_end in found_positions
                    )
                    
                    if is_overlapping:
                        continue
                    
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(text), end_pos + 50)
                    context = text[context_start:context_end].strip()
                    
                    results.append({
                        'code': code,
                        'context': context,
                        'position': start_pos
                    })
                    found_positions.add((start_pos, end_pos))
        
        # 然后尝试查找明确标记的邀请码
        explicit_patterns = [
            r'邀请码[：:]*\s*([A-Z0-9]{4,12})',  # 邀请码: ABCDEF
            r'暗号[：:]*\s*([A-Z0-9]{4,12})',  # 暗号: ABCDEF
            r'新邀请码[：:]*\s*([A-Z0-9]{4,12})',  # 新邀请码: ABCDEF
            r'"邀请码"\s*[:：]\s*"([A-Z0-9]{4,12})"',  # "邀请码": "ABCDEF"
        ]
        
        for pattern in explicit_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) > 0:
                    code = match.group(1)  # 提取匹配组
                else:
                    continue
                
                start_pos = match.start()
                end_pos = match.end()
                
                # 检查是否与已找到的代码位置重叠
                is_overlapping = any(
                    not (end_pos <= existing_start or start_pos >= existing_end)
                    for existing_start, existing_end in found_positions
                )
                
                if is_overlapping:
                    continue
                
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), end_pos + 50)
                context = text[context_start:context_end].strip()
                
                results.append({
                    'code': code,
                    'context': context,
                    'position': start_pos
                })
                found_positions.add((start_pos, end_pos))
        
        # 如果仍然没有找到邀请码，检查是否包含邀请码模式
        if not results:
            for pattern in self.code_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    code = match.group()
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # 检查是否与已找到的代码位置重叠
                    is_overlapping = any(
                        not (end_pos <= existing_start or start_pos >= existing_end)
                        for existing_start, existing_end in found_positions
                    )
                    
                    if is_overlapping:
                        continue
                    
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(text), end_pos + 50)
                    context = text[context_start:context_end].strip()
                    
                    # 检查上下文是否包含邀请码关键词，或者是已知的邀请码
                    context_lower = context.lower()
                    if any(keyword in context_lower for keyword in invite_keywords) or code in self.known_invite_codes:
                        results.append({
                            'code': code,
                            'context': context,
                            'position': start_pos
                        })
                        found_positions.add((start_pos, end_pos))
        
        return results
    
    def analyze_user_page(self, user_url: str) -> Dict:
        """分析用户页面"""
        result = {
            'notes_count': 0,
            'notes_summary': [],
            'invite_codes': []
        }
        
        # 获取用户主页内容
        html_content = self.get_user_page(user_url)
        if not html_content:
            return result
        
        # 提取笔记信息（已去重）
        notes = self.extract_notes_info(html_content)
        result['notes_count'] = len(notes)
        
        # 分析每个笔记
        for note in notes:
            # 添加笔记摘要
            summary = {
                'title': note['title'],
                'content_preview': note['content'][:100] + '...' if len(note['content']) > 100 else note['content']
            }
            result['notes_summary'].append(summary)
            
            # 检测邀请码
            codes = self.detect_invite_codes(note['content'])
            for code_info in codes:
                result['invite_codes'].append({
                    'code': code_info['code'],
                    'context': code_info['context'],
                    'from_note': note['title']
                })
            
            # 检查标题中是否包含邀请码
            title_codes = self.detect_invite_codes(note['title'])
            for code_info in title_codes:
                result['invite_codes'].append({
                    'code': code_info['code'],
                    'context': code_info['context'],
                    'from_note': f"{note['title']} (标题)"
                })
            
        # 去重邀请码
        unique_codes = {}
        for code_info in result['invite_codes']:
            code = code_info['code']
            if code not in unique_codes:
                unique_codes[code] = code_info
        
        result['invite_codes'] = list(unique_codes.values())
        
        return result
    
    def monitor_user(self, user_url: str) -> List[InviteCodeInfo]:
        """监控指定用户"""
        new_invite_codes = []
        
        try:
            # 获取用户主页内容
            html_content = self.get_user_page(user_url)
            if not html_content:
                return new_invite_codes
            
            # 提取笔记信息
            notes = self.extract_notes_info(html_content)
            
            # 分析每个笔记
            for note in notes:
                # 检测笔记内容中的邀请码
                content_codes = self.detect_invite_codes(note['content'])
                for code_info in content_codes:
                    hash_id = self.generate_hash_id(
                        code_info['code'], 'note_content', code_info['context']
                    )
                    if hash_id not in self.known_codes:
                        invite_info = InviteCodeInfo(
                            content=code_info['code'],
                            source='note_content',
                            note_id=note['id'],
                            note_title=note['title'],
                            note_url=f"https://www.xiaohongshu.com/user/profile/58953dcb3460945280efcf7b",
                            timestamp=datetime.now().isoformat(),
                            hash_id=hash_id,
                            context=code_info['context']
                        )
                        new_invite_codes.append(invite_info)
                        self.known_codes.add(hash_id)
                        logger.info(f"发现新邀请码: {code_info['code']} (来源: 笔记内容)")
                
                # 检测笔记标题中的邀请码
                title_codes = self.detect_invite_codes(note['title'])
                for code_info in title_codes:
                    hash_id = self.generate_hash_id(
                        code_info['code'], 'note_title', code_info['context']
                    )
                    if hash_id not in self.known_codes:
                        invite_info = InviteCodeInfo(
                            content=code_info['code'],
                            source='note_title',
                            note_id=note['id'],
                            note_title=f"{note['title']} (标题)",
                            note_url=f"https://www.xiaohongshu.com/user/profile/58953dcb3460945280efcf7b",
                            timestamp=datetime.now().isoformat(),
                            hash_id=hash_id,
                            context=code_info['context']
                        )
                        new_invite_codes.append(invite_info)
                        self.known_codes.add(hash_id)
                        logger.info(f"发现新邀请码: {code_info['code']} (来源: 笔记标题)")
            
        except Exception as e:
            logger.error(f"监控用户异常: {e}")
        
        return new_invite_codes
    
    def send_email_notification(self, invite_codes: List[InviteCodeInfo]=None, new_notes: List[NoteInfo]=None):
        """发送邮件通知，可以是邀请码或新笔记"""
        if not invite_codes and not new_notes:
            logger.info("没有新的邀请码或笔记，不发送邮件")
            return
        
        try:
            email_config = self.config.get('email', {})
            if not email_config:
                logger.warning("邮件配置不完整，跳过邮件发送")
                return
            
            if invite_codes:
                logger.info(f"准备发送邮件通知 {len(invite_codes)} 个新邀请码")
            if new_notes:
                logger.info(f"准备发送邮件通知 {len(new_notes)} 篇新笔记")
            
            # 创建邮件内容
            if invite_codes and not new_notes:
                subject = f"🎉 小红书邀请码监控提醒 - 发现 {len(invite_codes)} 个新邀请码"
            elif new_notes and not invite_codes:
                subject = f"📝 小红书监控提醒 - 发现 {len(new_notes)} 篇新笔记"
            else:
                subject = f"🎉 小红书监控提醒 - 发现 {len(invite_codes)} 个新邀请码和 {len(new_notes)} 篇新笔记"
            
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; }}
                    .header {{ background: linear-gradient(135deg, #ff2442, #ff6b6b); color: white; padding: 30px 20px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 24px; }}
                    .content {{ padding: 30px 20px; }}
                    .summary {{ background-color: #fff3f3; border-left: 4px solid #ff2442; padding: 15px; margin-bottom: 20px; }}
                    .invite-code, .note-item {{ 
                        background-color: #f8f9fa; 
                        border: 1px solid #e9ecef;
                        border-radius: 8px;
                        padding: 20px; 
                        margin: 15px 0; 
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .code {{ 
                        font-weight: bold; 
                        font-size: 20px; 
                        color: #ff2442; 
                        background-color: #fff; 
                        padding: 8px 15px; 
                        border-radius: 6px; 
                        display: inline-block; 
                        border: 2px dashed #ff2442;
                        font-family: 'Courier New', monospace;
                    }}
                    .note-title {{
                        font-weight: bold;
                        font-size: 18px;
                        color: #ff2442;
                        margin-bottom: 10px;
                    }}
                    .source {{ 
                        display: inline-block;
                        background-color: #007bff;
                        color: white;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-size: 12px;
                        margin-left: 10px;
                    }}
                    .context, .note-content {{ 
                        background-color: #e9ecef; 
                        padding: 10px; 
                        border-radius: 4px; 
                        margin-top: 10px; 
                        font-style: italic;
                        color: #495057;
                        white-space: pre-line;
                    }}
                    .meta {{ color: #6c757d; font-size: 12px; margin-top: 15px; }}
                    .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; }}
                    .btn {{ 
                        display: inline-block; 
                        background-color: #ff2442; 
                        color: white; 
                        padding: 10px 20px; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 10px 0;
                    }}
                    .section-title {{
                        margin-top: 30px;
                        margin-bottom: 15px;
                        font-size: 20px;
                        font-weight: bold;
                        color: #333;
                        border-bottom: 1px solid #ddd;
                        padding-bottom: 5px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎉 小红书监控提醒</h1>
                        <p>发现了新的内容！</p>
                    </div>
                    <div class="content">
                        <div class="summary">
                            <strong>监控摘要：</strong>在小美的小红书账号中发现了新的内容，请及时查看！
                        </div>
            """
            
            # 添加新笔记部分
            if new_notes:
                html_content += f"""
                    <div class="section-title">新笔记 ({len(new_notes)} 篇)</div>
                """
                
                for i, note_info in enumerate(new_notes, 1):
                    # 截取内容的前500个字符，避免邮件过大
                    content_preview = note_info.content[:500] + '...' if len(note_info.content) > 500 else note_info.content
                    html_content += f"""
                        <div class="note-item">
                            <div class="note-title">{note_info.title}</div>
                            <div class="note-content">{content_preview}</div>
                            <div class="meta">
                                <div>📅 发现时间：{note_info.timestamp}</div>
                                <div>🔗 <a href="{note_info.url}" target="_blank">查看小美主页</a></div>
                            </div>
                        </div>
                    """
            
            # 添加邀请码部分
            if invite_codes:
                html_content += f"""
                    <div class="section-title">新邀请码 ({len(invite_codes)} 个)</div>
                """
                
                for i, code_info in enumerate(invite_codes, 1):
                    source_text = {"note_title": "📌 笔记标题", "note_content": "📝 笔记内容"}.get(code_info.source, "📄 内容")
                    html_content += f"""
                        <div class="invite-code">
                            <div style="margin-bottom: 10px;">
                                <span class="code">{code_info.content}</span>
                                <span class="source">{source_text}</span>
                            </div>
                            <div><strong>来源：</strong>{code_info.note_title}</div>
                            <div class="context">
                                <strong>上下文：</strong>{code_info.context}
                            </div>
                            <div class="meta">
                                <div>📅 发现时间：{code_info.timestamp}</div>
                                <div>🔗 <a href="{code_info.note_url}" target="_blank">查看小美主页</a></div>
                            </div>
                        </div>
                    """
            
            html_content += f"""
                    </div>
                    <div class="footer">
                        <a href="https://www.xiaohongshu.com/user/profile/58953dcb3460945280efcf7b" class="btn" target="_blank">
                            访问小美主页
                        </a>
                        <p>监控时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p>此邮件由小红书邀请码监控系统自动发送</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # 发送邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = email_config['sender']
            msg['To'] = email_config['receiver']
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            server = smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port'])
            server.login(email_config['sender'], email_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"邮件发送成功，通知了 {len(invite_codes)} 个新邀请码")
            
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
    
    def check_new_notes(self, notes: List[Dict]) -> List[NoteInfo]:
        """检查是否有新笔记"""
        new_notes = []
        
        for note in notes:
            hash_id = hashlib.md5(f"{note['title']}_{note['id']}".encode('utf-8')).hexdigest()
            if hash_id not in self.known_notes:
                note_info = NoteInfo(
                    note_id=note['id'],
                    title=note['title'],
                    content=note['content'],
                    url=f"https://www.xiaohongshu.com/user/profile/58953dcb3460945280efcf7b",
                    timestamp=datetime.now().isoformat(),
                    hash_id=hash_id
                )
                new_notes.append(note_info)
                self.known_notes.add(hash_id)
                logger.info(f"发现新笔记: {note['title']}")
        
        return new_notes
    
    def run_monitor(self):
        """执行一次监控"""
        logger.info("开始执行监控任务")
        
        try:
            # 使用配置文件中的目标用户ID
            target_user_id = self.config.get('target_user_id', '58953dcb3460945280efcf7b')
            target_url = f"https://www.xiaohongshu.com/user/profile/{target_user_id}"
            
            # 获取用户主页内容
            html_content = self.get_user_page(target_url)
            if not html_content:
                logger.error("获取用户主页内容失败")
                return
                
            # 提取笔记信息
            notes = self.extract_notes_info(html_content)
            
            # 打印完整笔记内容
            logger.info(f"共发现 {len(notes)} 篇笔记")
            for i, note in enumerate(notes, 1):
                print(f"\n=== 笔记 {i}: {note['title']} ===")
                print(note['content'])
                print("=" * 50)
            
            # 检查是否有新笔记
            new_notes = self.check_new_notes(notes)
            if new_notes:
                logger.info(f"发现 {len(new_notes)} 篇新笔记")
                self.save_notes_history(new_notes)
            
            # 监控邀请码
            new_codes = self.monitor_user(target_url)
            if new_codes:
                logger.info(f"发现 {len(new_codes)} 个新邀请码")
                for code in new_codes:
                    logger.info(f"新邀请码: {code.content} (来源: {code.source})")
                self.save_history(new_codes)
            else:
                logger.info("未发现新的邀请码")
            
            # 如果有新笔记或新邀请码，发送邮件通知
            if new_notes or new_codes:
                self.send_email_notification(new_codes, new_notes)
            
        except Exception as e:
            logger.error(f"监控执行异常: {e}")
            # 记录异常详情
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")
        
        logger.info("监控任务完成")
    
    def start_scheduler(self):
        """启动定时任务"""
        # 使用配置文件中的间隔，默认为1分钟
        interval = self.config.get('monitor_interval', 1)  # 默认每分钟运行一次
        logger.info(f"启动定时监控，每{interval}分钟执行一次")
        
        # 立即执行一次
        self.run_monitor()
        
        # 设置定时任务
        schedule.every(interval).minutes.do(self.run_monitor)
        
        # 打印下一次执行时间
        next_run = schedule.next_run()
        if next_run:
            logger.info(f"下一次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(10)  # 每10秒检查一次是否有任务需要执行
            except KeyboardInterrupt:
                logger.info("接收到中断信号，正在停止...")
                break
            except Exception as e:
                logger.error(f"定时任务异常: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续

def main():
    """主函数"""
    logger.info("=== 小红书小美邀请码监控程序启动 ===")
    logger.info("使用配置文件：config.json")
    
    monitor = XHSMonitor()
    
    try:
        # 打印当前时间
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"当前时间: {current_time}")
        
        # 启动定时器
        monitor.start_scheduler()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        # 记录异常详情
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
    finally:
        logger.info("=== 小红书小美邀请码监控程序结束 ===")

if __name__ == "__main__":
    main()
