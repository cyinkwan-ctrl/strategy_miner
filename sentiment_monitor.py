#!/usr/bin/env python3
"""
TradingView 情绪监控器
- 增量采集社区观点
- 按资产聚合情绪得分
- 验证准确率
"""

import os
from pathlib import Path
import sys
import json
import re
import time
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'logs' / 'sentiment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('sentiment')


@dataclass
class SentimentIdea:
    """情绪观点"""
    id: str
    title: str
    url: str
    sentiment: str  # bullish/bearish/neutral
    asset: str  # BTC/XAU/USD等
    timeframe: str  # 15m/1h/4h/daily
    published_at: str
    description: str = ""


@dataclass
class AssetSentiment:
    """资产情绪得分"""
    asset: str
    total_ideas: int = 0
    bullish: int = 0
    bearish: int = 0
    neutral: int = 0
    bullish_ratio: float = 0.0
    last_updated: str = ""
    ideas: List[Dict] = field(default_factory=list)


class TradingViewSentimentMonitor:
    """TradingView情绪监控器"""

    FEED_URL = "https://www.tradingview.com/feed/"

    # 情绪关键词
    BULLISH_KEYWORDS = [
        'bullish', 'buy', 'long', 'up', 'higher', 'breakout', 'call',
        'support', 'bounce', 'recovery', 'ascending', 'continuation', 'target'
    ]
    BEARISH_KEYWORDS = [
        'bearish', 'sell', 'short', 'down', 'lower', 'breakdown', 'put',
        'resistance', 'reject', 'drop', 'descending', 'correction', 'stop'
    ]

    # 时间框架关键词
    TIMEFRAMES = {
        '15m': ['15 min', '15m', 'm15'],
        '1h': ['1 hour', '1h', 'hourly', 'h1'],
        '4h': ['4 hour', '4h', '4h', 'h4'],
        'daily': ['daily', 'day', '4h', 'higher timeframe']
    }

    # 验证时间窗口 (分钟)
    VALIDATION_WINDOWS = [15, 30, 60, 120, 240, 1440]  # 15min, 30min, 1h, 2h, 4h, 24h

    # 资产映射 (合并不同标识)
    ASSET_MAPPING = {
        'BTCUSDT': 'BTC',
        'BTCUSD': 'BTC',
        'BTC': 'BTC',
        'ETHUSDT': 'ETH',
        'ETHUSD': 'ETH',
        'ETH': 'ETH',
        'XAUUSD': 'XAU',
        'XAU': 'XAU',
        'GOLD': 'XAU',
        'XAGUSD': 'XAG',
        'XAG': 'XAG',
        'SILVER': 'XAG',
    }

    def __init__(self):
        self.state_file = Path(__file__).parent / 'sentiment_state.json'
        self.state = self._load_state()
        self.session_state = defaultdict(list)  # asset -> ideas

    def _load_state(self) -> Dict:
        """加载状态"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'last_fetched_id': None,
            'last_fetched_time': None,
            'processed_ideas': [],  # 记录已处理的idea ID
            'sentiment_history': {},  # asset -> [{time, bullish_ratio, actual_return}]
            'accuracy_history': []  # [{time, accuracy}]
        }

    def _save_state(self):
        """保存状态"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def fetch_ideas(self) -> List[Dict]:
        """获取最新ideas（增量）"""
        ideas = []
        try:
            feed = feedparser.parse(self.FEED_URL)
            for entry in feed.entries:
                idea_id = self._extract_id(entry.get('link', ''))

                # 增量去重
                if idea_id in self.state['processed_ideas']:
                    continue

                ideas.append({
                    'id': idea_id,
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'description': entry.get('summary', ''),
                    'published_at': entry.get('published', ''),
                    'author': entry.get('author', 'Unknown'),
                })

        except Exception as e:
            logger.error(f"获取ideas失败: {e}")

        return ideas

    def _extract_id(self, url: str) -> str:
        """从URL提取ID"""
        match = re.search(r'/([a-zA-Z0-9-]+)/?$', url)
        return match.group(1) if match else url

    def _extract_asset(self, title: str, url: str) -> str:
        """提取资产名称"""
        # 从URL提取
        match = re.search(r'/chart/([A-Z]+)/', url)
        if match:
            return match.group(1)

        # 从标题提取
        title_upper = title.upper()
        if 'BTC' in title_upper:
            return 'BTC'
        elif 'ETH' in title_upper:
            return 'ETH'
        elif 'GOLD' in title_upper or 'XAU' in title_upper:
            return 'XAU'
        elif 'OIL' in title_upper or 'WTI' in title_upper:
            return 'OIL'
        else:
            return 'OTHER'

    def _analyze_sentiment(self, title: str, description: str) -> Tuple[str, str]:
        """分析情绪倾向和时间框架"""
        text = (title + ' ' + description).lower()

        # 情绪分析
        bullish_score = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text)
        bearish_score = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text)

        if bullish_score > bearish_score:
            sentiment = 'bullish'
        elif bearish_score > bullish_score:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        # 时间框架分析
        timeframe = 'unknown'
        for tf, keywords in self.TIMEFRAMES.items():
            if any(kw in text for kw in keywords):
                timeframe = tf
                break

        return sentiment, timeframe

    def process_ideas(self, ideas: List[Dict]) -> List[SentimentIdea]:
        """处理ideas"""
        processed = []

        for idea in ideas:
            sentiment, timeframe = self._analyze_sentiment(
                idea['title'], idea['description']
            )
            asset = self._extract_asset(idea['title'], idea['url'])

            processed_idea = SentimentIdea(
                id=idea['id'],
                title=idea['title'],
                url=idea['url'],
                sentiment=sentiment,
                asset=asset,
                timeframe=timeframe,
                published_at=idea['published_at'],
                description=idea['description'][:200]
            )

            processed.append(processed_idea)

            # 记录已处理
            self.state['processed_ideas'].append(idea['id'])

        # 限制历史数量（只保留最近500个）
        if len(self.state['processed_ideas']) > 500:
            self.state['processed_ideas'] = self.state['processed_ideas'][-500:]

        return processed

    def aggregate_sentiment(self, ideas: List[SentimentIdea]) -> Dict[str, AssetSentiment]:
        """聚合情绪"""
        assets = defaultdict(lambda: AssetSentiment(asset='unknown'))

        for idea in ideas:
            asset_data = assets[idea.asset]
            asset_data.asset = idea.asset
            asset_data.total_ideas += 1
            asset_data.ideas.append({
                'id': idea.id,
                'title': idea.title[:50],
                'sentiment': idea.sentiment,
                'timeframe': idea.timeframe,
                'published_at': idea.published_at
            })

            if idea.sentiment == 'bullish':
                asset_data.bullish += 1
            elif idea.sentiment == 'bearish':
                asset_data.bearish += 1
            else:
                asset_data.neutral += 1

        # 计算比率
        for asset, data in assets.items():
            if data.total_ideas > 0:
                data.bullish_ratio = data.bullish / data.total_ideas
            data.last_updated = datetime.now().isoformat()

        return dict(assets)

    def run(self, fetch_interval_minutes: int = 15):
        """运行监控"""
        logger.info(f"启动情绪监控，采集间隔: {fetch_interval_minutes}分钟")

        while True:
            try:
                # 获取新ideas
                ideas = self.fetch_ideas()
                logger.info(f"获取到 {len(ideas)} 个新ideas")

                if ideas:
                    # 处理
                    processed = self.process_ideas(ideas)

                    # 聚合
                    sentiment = self.aggregate_sentiment(processed)

                    # 保存状态
                    self._save_state()

                    # 输出报告
                    self.print_report(sentiment)

                # 等待
                time.sleep(fetch_interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("监控已停止")
                break
            except Exception as e:
                logger.error(f"错误: {e}")
                time.sleep(60)

    def print_report(self, sentiment: Dict[str, AssetSentiment]):
        """打印报告"""
        print(f"\n{'='*60}")
        print(f"TradingView 情绪监控报告")
        print(f"{'='*60}")

        for asset, data in sorted(sentiment.items(), key=lambda x: -x[1].total_ideas):
            if data.total_ideas == 0:
                continue

            ratio = data.bullish_ratio * 100
            bars = '█' * int(ratio / 5) + '░' * (20 - int(ratio / 5))

            print(f"\n{asset}:")
            print(f"  {bars} {ratio:.0f}%")
            print(f"  总: {data.total_ideas} | 看涨: {data.bullish} | 看跌: {data.bearish} | 中性: {data.neutral}")

        print(f"{'='*60}\n")


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='TradingView情绪监控')
    parser.add_argument('--interval', type=int, default=15, help='采集间隔(分钟)')
    parser.add_argument('--once', action='store_true', help='只运行一次')
    args = parser.parse_args()

    monitor = TradingViewSentimentMonitor()

    if args.once:
        ideas = monitor.fetch_ideas()
        processed = monitor.process_ideas(ideas)
        sentiment = monitor.aggregate_sentiment(processed)
        monitor.print_report(sentiment)
    else:
        monitor.run(fetch_interval_minutes=args.interval)


if __name__ == '__main__':
    main()
