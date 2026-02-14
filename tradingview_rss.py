#!/usr/bin/env python3
"""
TradingView RSS 策略发现
使用RSS feed获取最新策略更新
"""

import os
import sys
import json
import re
import feedparser
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TradingViewStrategy:
    """TradingView策略"""
    id: str
    title: str
    url: str
    author: str
    description: str
    published_at: str
    source: str = "tradingview"


def parse_tradingview_feed(feed_url: str) -> List[Dict]:
    """解析TradingView RSS feed"""
    strategies = []

    try:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            # 提取信息
            title = entry.get('title', 'Unknown')
            url = entry.get('link', '')
            author = entry.get('author', 'Unknown')
            published = entry.get('published', datetime.now().isoformat())
            summary = entry.get('summary', '')

            # 清理HTML标签
            description = re.sub(r'<[^>]+>', '', summary)[:500]

            # 生成ID
            match = re.search(r'/([a-zA-Z0-9-]+)/?$', url)
            if match:
                script_id = f"tv_{match.group(1)}"
            else:
                script_id = f"tv_{hash(url) % 100000}"

            strategies.append({
                'id': script_id,
                'title': title,
                'url': url,
                'author': author,
                'description': description,
                'published_at': published,
                'source': 'tradingview',
                'discovered_at': datetime.now().isoformat(),
            })

    except Exception as e:
        print(f"解析RSS失败: {e}")
        return []

    return strategies


def discover_from_rss(max_feeds: int = 5) -> List[Dict]:
    """从多个RSS源发现策略"""
    all_strategies = []

    # TradingView RSS feeds
    rss_urls = [
        "https://www.tradingview.com/feed/",
        "https://www.tradingview.com/ideas/?sort=recently_published",
    ]

    # TradingView脚本RSS (如果有)
    # https://www.tradingview.com/rss/脚本名称

    for url in rss_urls[:max_feeds]:
        print(f"获取: {url}")
        strategies = parse_tradingview_feed(url)
        all_strategies.extend(strategies)
        print(f"  -> {len(strategies)} 个策略")

    return all_strategies


def main():
    """主函数"""
    print("=== TradingView RSS 策略发现 ===\n")

    strategies = discover_from_rss()

    print(f"\n发现 {len(strategies)} 个策略:")

    for s in strategies[:10]:
        print(f"\n- {s['title']}")
        print(f"  作者: {s['author']}")
        print(f"  链接: {s['url']}")

    # 保存
    output_file = '/Users/januswing/.openclaw/workspace/strategy_miner/tradingview_strategies.json'
    with open(output_file, 'w') as f:
        json.dump(strategies, f, indent=2, ensure_ascii=False)

    print(f"\n已保存到: {output_file}")


if __name__ == '__main__':
    main()
