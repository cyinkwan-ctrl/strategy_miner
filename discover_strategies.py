#!/usr/bin/env python3
"""
模拟Reddit策略发现 - 演示完整的策略发现和验证流程
基于真实的经典交易策略
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict

# 添加模块路径
sys.path.insert(0, '/Users/januswing/.openclaw/workspace/strategy_miner')

def create_sample_strategies() -> List[Dict]:
    """创建示例策略（基于真实策略）"""
    
    strategies = [
        {
            "source": "reddit",
            "author": "TradingView_Signals",
            "url": "https://reddit.com/r/Trading/comments/abc123/moving_average_crossover_strategy/",
            "title": "Golden Cross Strategy - 50/200 MA Crossover",
            "content": "Golden cross is when 50-day MA crosses above 200-day MA. Buy signal. Exit when 50-day MA crosses below 200-day MA. Stop loss at 5%.",
            "extracted_logic": "Golden cross: 50-day MA crosses above 200-day MA = BUY. Exit when 50-day MA crosses below 200-day MA = SELL. Stop loss 5%.",
            "subreddit": "Trading",
            "score": 542,
            "num_comments": 89
        },
        {
            "source": "reddit",
            "author": "OptionsMaster",
            "url": "https://reddit.com/r/options/comments/def456/rsi_oversold_strategy/",
            "title": "RSI Oversold Reversal Strategy",
            "content": "Buy when RSI goes below 30 (oversold). Sell when RSI crosses back above 50. Stop loss at 10%. This mean reversion strategy has 65% win rate historically.",
            "extracted_logic": "Buy when RSI below 30 (oversold). Sell when RSI crosses above 50. Stop loss 10%. Mean reversion.",
            "subreddit": "options",
            "score": 421,
            "num_comments": 67
        },
        {
            "source": "reddit",
            "author": "CryptoTraderPro",
            "url": "https://reddit.com/r/CryptoMoonShots/comments/ghi789/bollinger_band_squeeze/",
            "title": "Bollinger Band Squeeze Breakout Strategy",
            "content": "Bollinger Band squeeze indicates low volatility. Buy when price breaks above upper band. Stop loss at lower band. Take profit at 2:1 risk reward ratio.",
            "extracted_logic": "Buy when price breaks above upper Bollinger Band. Stop loss at lower band. Take profit 2:1 risk reward.",
            "subreddit": "CryptoMoonShots",
            "score": 318,
            "num_comments": 45
        },
        {
            "source": "reddit",
            "author": "ValueInvestor_Real",
            "url": "https://reddit.com/r/SecurityAnalysis/comments/jkl012/pe_ratio_strategy/",
            "title": "Low PE Ratio Value Strategy",
            "content": "Buy stocks with PE ratio below 15. Hold until PE reaches 25 or stop loss at 20% drop. Works best for long-term investing in index funds.",
            "extracted_logic": "Buy stocks with PE ratio below 15. Sell when PE reaches 25. Stop loss 20%. Long-term value strategy.",
            "subreddit": "SecurityAnalysis",
            "score": 287,
            "num_comments": 34
        },
        {
            "source": "reddit",
            "author": "SwingTraderDaily",
            "url": "https://reddit.com/r/stocks/comments/mno345/support_resistance_bounce/",
            "title": "Support Bounce Trading Strategy",
            "content": "Buy when price bounces off major support level. Place stop loss just below support. Target previous resistance. Risk reward 1:2.",
            "extracted_logic": "Buy on support bounce. Stop loss below support. Target resistance. Risk reward 1:2.",
            "subreddit": "stocks",
            "score": 198,
            "num_comments": 28
        },
        {
            "source": "reddit",
            "author": "MacdTrader",
            "url": "https://reddit.com/r/Daytrading/comments/pqr678/macd_crossover_trading/",
            "title": "MACD Crossover Intraday Strategy",
            "content": "MACD histogram turns positive = buy signal. Exit when histogram turns negative. Works on 4hr timeframe. Stop loss 2%.",
            "extracted_logic": "MACD histogram positive = BUY. Exit when histogram negative. 4hr timeframe. Stop loss 2%.",
            "subreddit": "Daytrading",
            "score": 156,
            "num_comments": 23
        }
    ]
    
    return strategies

def save_strategies(strategies: List[Dict]):
    """保存策略到 strategies.json"""
    strategies_file = '/Users/januswing/.openclaw/workspace/strategy_miner/strategies.json'
    
    try:
        with open(strategies_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {
            "strategies": [], 
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_scanned": 0,
                "passed": 0,
                "rejected": 0
            }
        }
    
    existing_urls = {s.get('url') for s in data['strategies']}
    added_count = 0
    
    for strategy in strategies:
        if strategy['url'] in existing_urls:
            continue
        
        new_strategy = {
            'id': len(data['strategies']) + 1,
            'source': strategy['source'],
            'author': strategy['author'],
            'url': strategy['url'],
            'title': strategy['title'],
            'content': strategy['content'],
            'extracted_logic': strategy['extracted_logic'],
            'discovered_at': datetime.now().isoformat(),
            'validated_at': None,
            'status': 'pending',
            'backtest_result': None,
            'keywords': [strategy['subreddit']],
            'data_source': 'reddit',
            'score': strategy['score'],
            'num_comments': strategy['num_comments']
        }
        
        data['strategies'].append(new_strategy)
        data['metadata']['total_scanned'] += 1
        data['metadata']['last_updated'] = datetime.now().isoformat()
        added_count += 1
    
    with open(strategies_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 保存了 {added_count} 个新策略")
    return data

def main():
    """主函数"""
    print("=" * 60)
    print("🎯 策略发现模拟器 - 演示完整工作流")
    print("=" * 60)
    
    # 1. 创建示例策略
    strategies = create_sample_strategies()
    print(f"\n📰 模拟发现 {len(strategies)} 个策略:")
    
    for i, s in enumerate(strategies, 1):
        print(f"{i}. [{s['subreddit']}] {s['title']}")
        print(f"   作者: @{s['author']} | 评分: {s['score']} | 评论: {s['num_comments']}")
        print(f"   逻辑: {s['extracted_logic'][:80]}...")
    
    # 2. 保存策略
    data = save_strategies(strategies)
    
    print(f"\n📊 strategies.json 更新完成")
    print(f"   总策略数: {len(data['strategies'])}")
    print(f"   待验证: {len([s for s in data['strategies'] if s['status'] == 'pending'])}")
    
    return data

if __name__ == "__main__":
    main()
