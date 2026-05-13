# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

闲鱼（Xianyu）自动聊天机器人，通过 WebSocket 连接闲鱼消息系统，使用 LLM 自动回复买家咨询。支持三种回复策略：价格议价、技术咨询、默认回复。

## Running the Application

```bash
# 启动机器人
python -m src.main
```

配置通过 `.env` 文件管理，必需变量：
- `COOKIES_STR`: 闲鱼网页版登录后的 Cookie
- `API_KEY`: 阿里云 DashScope API Key
- `MODEL_NAME`: 模型名称（默认 qwen3.5-27b）
- `MODEL_BASE_URL`: API 地址

## Core Architecture

### Message Flow
```
WebSocket (live_client.py) → 解密消息 → MessageHandler.handle() 
    → 分类意图 (classifier.py) → 对应 Agent (price/tech/default) 
    → LLM 生成回复 → 发送消息
```

### Key Components

| File | Purpose |
|------|---------|
| `live_client.py` | WebSocket 客户端，处理 token 刷新、心跳、消息解密 |
| `message_handler.py` | 消息调度核心，控制并发（Semaphore=3）、手动模式切换 |
| `chain_factory.py` | 组合分类器和三个 Agent 链，缓存已构建的 chain |
| `agents/classifier.py` | 意图分类：rule-based 关键字优先，否则调用 LLM |
| `agents/price.py` | 议价逻辑：根据 bargaining count 动态调整 temperature |
| `agents/tech.py` | 技术咨询：启用 search 功能的独立模型实例 |
| `conversation/memory.py` | SQLite 存储对话历史 + bargain_counts 表 |

### Intent Classification Logic
1. **Rule-based first**（快速路径）: tech/price 关键词匹配
2. **LLM fallback**: 模糊语句调用分类器模型
3. Categories: `price` | `tech` | `default` | `no_reply`

### Special Features
- **手动接管模式**: 发送 ` toggle_keywords`（默认"。"）切换手动/自动
- **防风控机制**: Cookie 清理、自动重连、token 过期刷新
- **消息去重**: 过期消息丢弃（MESSAGE_EXPIRE_TIME 默认 300 秒）
- **WAL 模式**: SQLite 开启 WAL 提升并发性能

## Prompt System

Prompts 存储在 `prompts/` 目录：
- `classify_prompt_example.txt`: 意图分类指令
- `price_prompt_example.txt`: 议价策略（含 gradient pricing rules）
- `tech_prompt_example.txt`: 技术参数解释
- `default_prompt_example.txt`: 通用卖家回复

加载顺序：先查自定义文件，再回退到 example 文件 (`agents/base.py:load_prompt`)

## Common Operations

```bash
# 检查登录状态
python -c "from src.utils.xianyu_apis import XianyuApis; api=XianyuApis(); print(api.hasLogin())"

# 查看数据库内容
sqlite3 data/chat_history.db "SELECT * FROM bargain_counts;"
sqlite3 data/chat_history.db "SELECT * FROM items LIMIT 5;"
sqlite3 data/chat_history.db "SELECT * FROM messages LIMIT 10;"
```

## Debugging Tips

- Token 失效时日志显示 "Token API 调用失败"，触发 `hasLogin()` 重新验证
- Cookie 重复会触发 `clear_duplicate_cookies()` 并更新 `.env`
- 风控触发显示 "RGV587_ERROR" 或 "被挤爆啦"，提示用户手动更新 Cookie
- 消息过期会输出 "过期消息丢弃" DEBUG 日志
