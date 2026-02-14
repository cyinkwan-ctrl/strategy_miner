#!/usr/bin/env python3
"""
TradingView 情绪分级验证器
- 多时间窗口验证情绪有效性
- 计算相关性/准确率
- 发现最佳交易窗口
"""

import os
import sys
import json
import re
import time
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import ccxt
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/januswing/.openclaw/workspace/strategy_miner/logs/sentiment_validator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('sentiment_validator')


@dataclass
class SentimentRecord:
    """情绪记录"""
    id: str
    asset: str  # BTC, XAU, ETH
    sentiment: str  # bullish/bearish/neutral
    bullish_ratio: float  # 看涨比例
    total_count: int  # 样本数
    recorded_at: str  # ISO时间
    snapshot_time: float  # Unix时间戳


@dataclass
class ValidationResult:
    """验证结果"""
    asset: str
    window_minutes: int  # 验证窗口
    sample_count: int  # 验证样本数
    correct_predictions: int  # 正确预测数
    accuracy: float  # 准确率
    avg_return: float  # 平均收益
    correlation: float  # 情绪与收益相关性
    p_value: float  # 统计显著性


class SentimentValidator:
    """情绪分级验证器"""

    # 验证时间窗口 (分钟)
    VALIDATION_WINDOWS = [15, 30, 60, 120, 240, 1440]

    # 情绪关键词
    BULLISH_KEYWORDS = [
        'bullish', 'buy', 'long', 'up', 'higher', 'breakout', 'call',
        'support', 'bounce', 'recovery', 'ascending', 'continuation'
    ]
    BEARISH_KEYWORDS = [
        'bearish', 'sell', 'short', 'down', 'lower', 'breakdown', 'put',
        'resistance', 'reject', 'drop', 'descending', 'correction'
    ]

    # 资产映射
    ASSET_MAPPING = {
        'BTCUSDT': 'BTC', 'BTCUSD': 'BTC', 'BTC': 'BTC',
        'ETHUSDT': 'ETH', 'ETHUSD': 'ETH', 'ETH': 'ETH',
        'XAUUSD': 'XAU', 'XAU': 'XAU', 'GOLD': 'XAU',
        'XAGUSD': 'XAG', 'XAG': 'XAG',
    }

    def __init__(self):
        self.state_file = '/Users/januswing/.openclaw/workspace/strategy_miner/sentiment_validator_state.json'
        self.state = self._load_state()
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})

    def _load_state(self) -> Dict:
        """加载状态"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'records': [],  # 情绪记录
            'validations': [],  # 验证结果
            'asset_stats': {}  # 资产统计
        }

    def _save_state(self):
        """保存状态"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _extract_asset(self, title: str, url: str) -> str:
        """提取并标准化资产名称"""
        match = re.search(r'/chart/([A-Z]+)/', url)
        raw_asset = match.group(1) if match else 'OTHER'
        return self.ASSET_MAPPING.get(raw_asset, raw_asset)

    def _analyze_sentiment(self, title: str, description: str) -> str:
        """分析情绪"""
        text = (title + ' ' + description).lower()
        bullish = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text)
        bearish = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text)

        if bullish > bearish:
            return 'bullish'
        elif bearish > bullish:
            return 'bearish'
        return 'neutral'

    def fetch_and_snapshot(self) -> List[SentimentRecord]:
        """获取并快照当前情绪"""
        try:
            feed = feedparser.parse('https://www.tradingview.com/feed/')
        except Exception as e:
            logger.error(f"获取feed失败: {e}")
            return []

        # 按资产分组统计
        asset_counts = defaultdict(lambda: {'bullish': 0, 'bearish': 0, 'neutral': 0, 'ids': []})
        seen_ids = set(r['id'] for r in self.state['records'])

        for entry in feed.entries:
            idea_id = re.search(r'/([a-zA-Z0-9-]+)/?$', entry.get('link', ''))
            if not idea_id:
                continue
            idea_id = idea_id.group(1)

            if idea_id in seen_ids:
                continue

            asset = self._extract_asset(entry.get('title', ''), entry.get('link', ''))
            sentiment = self._analyze_sentiment(entry.get('title', ''), entry.get('summary', ''))

            asset_counts[asset]['ids'].append(idea_id)
            asset_counts[asset][sentiment] += 1

        # 创建快照
        snapshot_time = time.time()
        records = []

        for asset, counts in asset_counts.items():
            total = counts['bullish'] + counts['bearish'] + counts['neutral']
            if total == 0:
                continue

            bullish_ratio = counts['bullish'] / total

            record = SentimentRecord(
                id=counts['ids'][0],  # 使用第一个ID
                asset=asset,
                sentiment='bullish' if bullish_ratio > 0.5 else ('bearish' if counts['bullish'] < counts['bearish'] else 'neutral'),
                bullish_ratio=bullish_ratio,
                total_count=total,
                recorded_at=datetime.now().isoformat(),
                snapshot_time=snapshot_time
            )
            records.append(record)

            # 添加到状态
            self.state['records'].append({
                'id': record.id,
                'asset': record.asset,
                'sentiment': record.sentiment,
                'bullish_ratio': record.bullish_ratio,
                'total_count': record.total_count,
                'recorded_at': record.recorded_at,
                'snapshot_time': record.snapshot_time
            })

        # 清理旧记录 (只保留7天)
        cutoff = snapshot_time - 7 * 24 * 3600
        self.state['records'] = [r for r in self.state['records'] if r['snapshot_time'] > cutoff]

        self._save_state()
        logger.info(f"创建了 {len(records)} 个情绪快照")

        return records

    def get_price_change(self, asset: str, window_minutes: int) -> Optional[float]:
        """获取价格变化"""
        symbol_map = {
            'BTC': 'BTC/USDT',
            'ETH': 'ETH/USDT',
            'XAU': 'XAU/USD',
            'XAG': 'XAG/USD',
        }
        symbol = symbol_map.get(asset)
        if not symbol:
            return None

        # 选择合适的时间框架
        if window_minutes <= 15:
            timeframe = '15m'
        elif window_minutes <= 60:
            timeframe = '1h'
        elif window_minutes <= 240:
            timeframe = '4h'
        else:
            timeframe = '1d'
        
        limit = max(int(window_minutes / 15) + 2, 5)
        if timeframe == '1h' and limit > 100:
            limit = 100
        if timeframe == '4h':
            limit = max(int(window_minutes / 240) + 2, 3)
        if timeframe == '1d':
            limit = max(int(window_minutes / 1440) + 2, 3)

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if len(ohlcv) < 2:
                return None

            start_price = ohlcv[0][4]  # close
            end_price = ohlcv[-1][4]
            return (end_price - start_price) / start_price

        except Exception as e:
            logger.warning(f"获取{asset}价格失败: {e}")
            return None

    def validate_window(self, window_minutes: int) -> List[ValidationResult]:
        """验证指定时间窗口"""
        results = []
        snapshot_time = time.time()
        window_seconds = window_minutes * 60

        # 按资产分组验证
        asset_records = defaultdict(list)
        for record in self.state['records']:
            age = snapshot_time - record['snapshot_time']
            if abs(age - window_seconds) < window_seconds * 0.5:  # 匹配时间窗口
                asset_records[record['asset']].append(record)

        for asset, records in asset_records.items():
            if len(records) < 2:
                continue

            price_change = self.get_price_change(asset, window_minutes)
            if price_change is None:
                continue

            # 计算预测正确数
            correct = 0
            returns = []

            for r in records:
                expected_up = r['bullish_ratio'] > 0.5
                actual_up = price_change > 0

                if expected_up == actual_up:
                    correct += 1

                returns.append(r['bullish_ratio'] * price_change)

            if len(records) > 0:
                avg_return = np.mean(returns)
                accuracy = correct / len(records)

                # 简化相关性计算
                correlation = np.corrcoef(
                    [r['bullish_ratio'] for r in records],
                    [1 if price_change > 0 else 0 for _ in records]
                )[0, 1] if len(records) > 1 else 0

                results.append(ValidationResult(
                    asset=asset,
                    window_minutes=window_minutes,
                    sample_count=len(records),
                    correct_predictions=correct,
                    accuracy=accuracy,
                    avg_return=avg_return,
                    correlation=correlation if not np.isnan(correlation) else 0,
                    p_value=0.05  # 简化
                ))

        return results

    def run_full_validation(self):
        """运行完整验证"""
        logger.info("开始情绪分级验证...")

        # 1. 获取新快照
        new_records = self.fetch_and_snapshot()

        # 2. 验证所有时间窗口
        all_results = []
        for window in self.VALIDATION_WINDOWS:
            results = self.validate_window(window)
            all_results.extend(results)

        # 3. 打印报告
        self.print_validation_report(all_results)

        # 4. 保存验证结果
        self.state['validations'].extend([
            {
                'asset': r.asset,
                'window': r.window_minutes,
                'accuracy': r.accuracy,
                'correlation': r.correlation,
                'validated_at': datetime.now().isoformat()
            }
            for r in all_results
        ])
        self._save_state()

        return all_results

    def print_validation_report(self, results: List[ValidationResult]):
        """打印验证报告"""
        print(f"\n{'='*70}")
        print(f"TradingView 情绪验证报告")
        print(f"{'='*70}")

        # 按资产分组
        by_asset = defaultdict(list)
        for r in results:
            by_asset[r.asset].append(r)

        for asset, res_list in sorted(by_asset.items(), key=lambda x: -len(x)):
            print(f"\n{asset}:")

            # 按准确率排序
            res_list.sort(key=lambda x: -x.accuracy)

            best = res_list[0]
            print(f"  最佳窗口: {best.window_minutes}分钟 | 准确率: {best.accuracy*100:.0f}% | 样本: {best.sample_count}")

            print(f"\n  时间窗口 -> 准确率 | 收益 | 相关性")
            print(f"  {'-'*50}")

            for r in res_list:
                acc_bar = '█' * int(r.accuracy * 10) + '░' * (10 - int(r.accuracy * 10))
                print(f"  {r.window_minutes:>5}min   {acc_bar} {r.accuracy*100:>5.0f}% | {r.avg_return*100:>+6.1f}% | {r.correlation:>+5.2f}")

        print(f"\n{'='*70}")
        print("建议: 关注准确率 >50% 的时间窗口，该窗口内情绪信号更可靠")
        print(f"{'='*70}\n")

    def get_best_window(self, asset: str) -> Optional[int]:
        """获取最佳交易窗口"""
        validations = [
            v for v in self.state['validations']
            if v['asset'] == asset and v['accuracy'] > 0.5
        ]

        if not validations:
            return None

        # 返回准确率最高的
        validations.sort(key=lambda x: -x['accuracy'])
        return validations[0]['window']


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='TradingView情绪验证')
    parser.add_argument('--validate', action='store_true', help='运行验证')
    parser.add_argument('--best', type=str, help='查询某资产最佳窗口')
    args = parser.parse_args()

    validator = SentimentValidator()

    if args.validate:
        validator.run_full_validation()
    elif args.best:
        window = validator.get_best_window(args.best.upper())
        if window:
            print(f"{args.best} 最佳交易窗口: {window}分钟")
        else:
            print(f"{args.best} 数据不足，无法确定最佳窗口")
    else:
        print("用法:")
        print("  python sentiment_validator.py --validate   # 运行验证")
        print("  python sentiment_validator.py --best BTC   # 查询BTC最佳窗口")


if __name__ == '__main__':
    main()
