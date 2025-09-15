# 小红书邀请码监控爬虫

这是一个用于监控小红书账号（小美）最新笔记和评论中邀请码的Python爬虫程序。特别优化了对"6位大写字母"格式邀请码的检测。

笔记目前有三条 ，例如 《一份关于小美邀请码的真诚说明与感谢 》
评论例如 ：本来大家挺有热情的，这么搞，新鲜劲一过完犊子…
有邀请码的评论 ： 感谢大家的热情！我们尽力为大家争取到了今日第二轮暗号：XMGOOD

邀请码为 6位字母，大写

## 功能特点

- 🕐 **定时监控**：每5分钟自动检查一次
- 🔍 **智能识别**：使用多种模式识别邀请码和暗号，特别优化6位大写字母格式
- 📧 **邮件提醒**：发现新邀请码时自动发送邮件通知
- 💾 **历史记录**：避免重复提醒已发现的邀请码
- 🌐 **多种实现**：提供智能监控、简化版和selenium三种实现方式
- 💬 **评论监控**：同时监控笔记内容和评论区

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### 1. 邮件配置

编辑 `config.json` 文件，配置邮件发送信息：

```json
{
  "email": {
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "sender": "your_email@qq.com",
    "password": "your_email_password",
    "receiver": "receiver@example.com"
  }
}
```

**注意：**
- QQ邮箱需要使用授权码而不是登录密码
- 其他邮箱服务商请相应调整smtp_server和smtp_port

### 2. Chrome浏览器配置（Selenium版本）

确保系统已安装Chrome浏览器和ChromeDriver：

```bash
# macOS
brew install chromedriver

# 或者手动下载
# https://chromedriver.chromium.org/
```

## 使用方法

### 必要步骤：更新Cookie信息

由于小红书的反爬机制，需要先更新Cookie信息才能正常访问：

```bash
# 从浏览器复制curl命令，保存到curl_command.txt文件
python3 extract_cookies_simple.py
```

### 使用智能监控版本

可以同时监控笔记内容和评论区，专门优化6位大写字母邀请码检测：

```bash
python3 xhs_smart_monitor.py
```

## 邀请码识别规则

程序会识别以下类型的邀请码：

### 关键词匹配
- 中文：邀请码、激活码、内测码、体验码、测试码、暗号、口令等
- 英文：invite、code、activation、beta、test等

### 格式模式
- `[A-Z]{6}`：6位大写字母（优先级最高）
- `XIAOMEI[0-9]{2,6}`：小美+数字格式
- `XM[A-Z0-9]{4,8}`：小美专属格式
- `[A-Z0-9]{4,12}`：大写字母数字组合
- `[A-Z]{2,4}[0-9]{3,6}`：字母+数字组合

## 文件说明

- `xhs_smart_monitor.py`：智能监控版本（推荐），支持笔记和评论监控
- `extract_cookies_simple.py`：Cookie提取工具
- `config.json`：配置文件
- `invite_codes_history.json`：邀请码历史记录（自动生成）
- `xhs_monitor.log`：运行日志（自动生成）

## 运行日志

程序运行时会在控制台和日志文件中输出详细信息：

```
2024-01-15 10:30:00 - INFO - 开始执行监控任务
2024-01-15 10:30:05 - INFO - 获取到 5 条笔记
2024-01-15 10:30:15 - INFO - 发现 2 个新邀请码
2024-01-15 10:30:16 - INFO - 新邀请码: XM2024 (来源: note)
2024-01-15 10:30:16 - INFO - 新邀请码: XIAOMEI123 (来源: comment)
2024-01-15 10:30:20 - INFO - 邮件发送成功，通知了 2 个新邀请码
2024-01-15 10:30:20 - INFO - 监控任务完成
```

## 注意事项

1. **反爬虫机制**：小红书有较强的反爬虫机制，建议：
   - 适当增加请求间隔
   - 使用代理IP（如需要）
   - 避免频繁访问
   - **必须定期更新Cookie信息**

2. **Cookie管理**：
   - Cookie通常会在几小时内过期
   - 使用`extract_cookies_simple.py`定期更新
   - 从浏览器开发者工具中复制curl命令

3. **邮件配置**：
   - 确保邮箱开启SMTP服务
   - QQ邮箱需要使用授权码
   - 测试邮件发送功能

4. **Chrome驱动**（仅Selenium版本）：
   - 确保ChromeDriver版本与Chrome浏览器版本匹配
   - 可以设置为有头模式进行调试

5. **网络环境**：
   - 确保网络连接稳定
   - 如遇到访问问题，可能需要配置代理

## 故障排除

### 1. 获取用户页面失败
```
2025-09-14 21:50:21,451 - INFO - 成功获取用户主页，内容长度: 4662
```
如果页面内容长度小于10000，可能是获取到了登录页面而非用户页面，需要更新Cookie：

```bash
# 从浏览器复制curl命令到curl_command.txt文件
python3 extract_cookies_simple.py
```

### 2. ChromeDriver问题（Selenium版本）
```bash
# 检查Chrome版本
google-chrome --version

# 下载对应版本的ChromeDriver
# https://chromedriver.chromium.org/downloads
```

### 3. 邮件发送失败
- 检查邮箱配置是否正确
- 确认SMTP服务已开启
- 验证授权码是否正确

### 4. 邀请码检测问题
- 检查邀请码格式是否符合预期
- 可以使用`test_invite_detection.py`测试检测逻辑
- 如需添加新的邀请码格式，修改`code_patterns`变量

## 自定义配置

可以根据需要修改以下参数：

```json
{
  "monitor_interval": 5,           // 监控间隔（分钟）
  "max_notes_per_check": 20,       // 每次检查的最大笔记数
  "max_comments_per_note": 50,     // 每篇笔记的最大评论数
  "target_user_id": "58953dcb3460945280efcf7b"  // 目标用户ID（小美）
}
```

## 版本对比

| 功能 | 智能版 | 简化版 | Selenium版 |
|---------|---------|---------|------------|
| 笔记监控 | ✅ | ✅ | ✅ |
| 评论监控 | ✅ | ✅ | ✅ |
| 6位大写字母优化 | ✅ | ❌ | ❌ |
| 无需浏览器 | ✅ | ✅ | ❌ |
| 定期更新Cookie | 需要 | 需要 | 可选 |
| 资源占用 | 低 | 低 | 高 |
| 稳定性 | 高 | 中 | 低 |

## 许可证

本项目仅供学习和研究使用，请遵守相关网站的使用条款。
