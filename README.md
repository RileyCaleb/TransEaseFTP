```markdown
# FTP服务器管理工具 / FTP Server Manager
# 中英双语文档 / Bilingual Documentation

## 简介 / Introduction
这是一个基于Python和PyQt5开发的FTP服务器管理工具，专为Windows系统优化。  
A Python and PyQt5 based FTP server management tool, optimized for Windows systems.

## 功能特性 / Features
| 中文功能 | English Features |
|---------|------------------|
| 🖥️ 图形化界面管理 | 🖥️ GUI Management |
| ⚡ 一键启动/停止 | ⚡ One-click Start/Stop |
| 📁 自定义根目录 | 📁 Custom Root Directory |
| 🔒 支持匿名访问 | 🔒 Anonymous Access Support |
| 📊 实时连接监控 | 📊 Real-time Connections |
| 📝 日志记录功能 | 📝 Logging System |
| 🛠️ 可配置参数 | 🛠️ Configurable Parameters |
| 🏷️ 系统托盘支持 | 🏷️ System Tray Support |
| 🇨🇳/🇬🇧 双语界面 | 🇨🇳/🇬🇧 Bilingual UI |

## 系统要求 / System Requirements
- Windows 7/10/11
- Python 3.7+
- 推荐GB18030/UTF-8编码  
  Recommended GB18030/UTF-8 encoding

## 安装指南 / Installation
```bash
中文用户额外步骤 / Additional for Chinese users:
pip install PyQt5 pyftpdlib -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 界面说明 / UI Guide
| 中文标签页 | English Tab | 功能描述 |
|-----------|------------|---------|
| 服务器状态 | Server Status | 显示运行状态/Show operation status |
| 配置参数 | Configuration | 端口/编码等设置/Port & encoding settings |
| 用户管理 | User Management | (开发中/In development) |
| 系统日志 | System Log | 实时日志显示/Realtime logging |

## 配置文件示例 / Config Example
```ini
[general]
port = 2121  # 监听端口/Listen port
encoding = gb18030  # 编码方式/Character encoding
```

## 常见问题 / FAQ
Q: 如何解决中文乱码？  
How to fix encoding issues?  
A: 确保客户端使用GB18030编码  
Ensure client uses GB18030 encoding

Q: 最大连接数限制？  
Max connections limit?  
A: 理论上1000，实际取决于系统资源  
Theoretical 1000, depends on system resources

## 开发计划 / Roadmap
- [ ] 用户权限管理 / User permission management
- [ ] SSL/TLS加密支持 / SSL/TLS encryption
- [ ] 多语言增强 / Enhanced multilingual support

## 联系方式 / Contact
中文支持: 2188167718@qq.com  
International: 2188167718@qq.com
```

这个版本的特点：
1. 采用对照表格形式呈现双语内容
2. 保留所有技术细节的同时实现双语对照
3. 关键配置项添加双语注释
4. 常见问题采用问答对照格式
5. 安装指南包含中文环境优化建议
6. 联系方式区分中英文支持渠道

可以根据实际需要调整表格布局或增加更多技术细节的对照翻译。对于代码块和配置项，建议保持英文格式，仅添加中文注释说明。