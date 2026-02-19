# Strategy Miner

从 Reddit、Twitter/X、TradingView 自动发现并验证交易策略的量化系统。

**GitHub:** https://github.com/cyinkwan-ctrl/strategy_miner

---

## 📁 项目结构

```
strategy_miner/
├── reddit_scraper.py          # Reddit 帖子爬虫
├── discover_strategies.py     # 策略发现器
├── strategy_radar.py          # 策略雷达系统
├── strategy_validator.py      # 回测验证器
├── sentiment_validator.py     # 情绪验证 (TradingView)
├── tradingview_scraper.py     # TradingView 策略爬虫
├── x_rss_scanner.py           # Twitter/X RSS 扫描
├── scheduler.py               # 定时任务调度
├── feishu_notify.py           # 飞书通知
├── auto_runner.py             # 自动运行入口
├── config/                    # 配置文件
├── logs/                      # 日志目录
└── strategies.json            # 策略库
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入必要的 API 密钥：

```bash
cp .env.example .env
```

需要配置：
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` - Reddit API
- `TWITTER_API_KEY` / `TWITTER_API_SECRET` - Twitter API (可选)
- `FEISHU_WEBHOOK` - 飞书机器人 Webhook (可选)

### 3. 运行

```bash
# 发现新策略
python discover_strategies.py

# 验证所有策略
python strategy_validator.py --all

# 验证情绪指标
python sentiment_validator.py --validate

# 自动运行 (定时任务)
python auto_runner.py

# 查看状态
python check_status.py
```

---

## 📊 功能说明

### 策略发现
- **Reddit** - 爬取 r/investing, r/stocks, r/wallstreetbets 等 subreddits
- **TradingView** - 抓取公开策略
- **Twitter/X** - RSS 扫描交易信号

### 策略验证
- **回测** - 基于历史数据验证策略表现
- **情绪分析** - 验证社交媒体情绪与市场关系
- **多时间窗口** - 15min, 30min, 60min, 120min, 240min, 1440min

### 自动化
- 定时任务 - 每 4 小时自动运行
- 飞书通知 - 推送验证结果

---

## ⚠️ 已知问题

- 样本量较小，统计结论需谨慎
- 部分技术策略在牛市表现不如买入持有
- 需更多数据验证情绪指标可靠性

---

## 📈 回测结果 (SPY, 2年)

| 策略 | 收益 | vs 基准 | 状态 |
|------|------|---------|------|
| Golden Cross | +16.2% | ❌ -22% | 失败 |
| RSI Oversold | -1.7% | ❌ -40% | 失败 |
| Bollinger Band | +12.3% | ❌ -26% | 失败 |
| Low PE Value | +38.5% | = 持平 | 通过 |
| Support Bounce | +8.5% | ❌ -30% | 失败 |

**结论:** 牛市期间，简单买入持有是最优策略。

---

*最后更新: 2026-02-19*
