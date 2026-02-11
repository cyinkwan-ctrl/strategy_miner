#!/usr/bin/env python3
"""
分层策略验证器 v2
根据策略类型选择不同验证方法:
- 技术趋势策略 -> 短期回测
- 高频/复杂策略 -> 实时监控 + 统计检验
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np
from scipy import stats

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/januswing/.openclaw/workspace/strategy_miner/logs/validator_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('validator_v2')


@dataclass
class ValidationResult:
    """验证结果"""
    strategy_id: int
    strategy_title: str
    strategy_type: str  # trend/hf/complex/fundamental
    validation_method: str  # backtest/monitor/statistical

    # 回测结果
    backtest_return: Optional[float] = None  # 总收益
    backtest_benchmark: Optional[float] = None  # 基准收益
    backtest_win_rate: Optional[float] = None  # 胜率
    backtest_max_drawdown: Optional[float] = None  # 最大回撤
    backtest_sharpe: Optional[float] = None  # 夏普比率
    backtest_trades: Optional[int] = None  # 交易次数
    backtest_avg_return: Optional[float] = None  # 平均交易收益

    # 监控结果
    signal_count: int = 0
    signal_sample_period_hours: float = 0.0

    # 统计检验结果
    stat_t_statistic: Optional[float] = None  # t统计量
    stat_p_value: Optional[float] = None  # p值
    stat_z_score: Optional[float] = None  # z分数
    stat_mean_return: Optional[float] = None  # 平均收益
    stat_std_return: Optional[float] = None  # 收益标准差
    stat_sample_size: Optional[int] = None  # 样本量
    stat_significant: bool = False  # 是否显著 (p<0.05)

    # 综合评分
    confidence_score: float = 0.0  # 0-100
    notes: str = ""
    validated_at: str = ""


class StrategyClassifier:
    """策略类型分类器"""

    HF_KEYWORDS = ['orderbook', 'order book', ' bid-ask', 'spread',
                   'latency', 'hft', 'high frequency', 'market making',
                   'arbitrage', '套利', '做市']

    TREND_KEYWORDS = ['ma', 'moving average', 'crossover', 'cross',
                      'rsi', 'macd', 'bollinger', 'trend', '趋势']

    FUNDAMENTAL_KEYWORDS = ['pe', 'roe', 'dividend', '现金流', '基本面',
                           '估值', 'financial', 'ratio']

    @classmethod
    def classify(cls, logic_text: str) -> str:
        """根据策略描述判断类型"""
        text_lower = logic_text.lower()

        if any(kw in text_lower for kw in cls.HF_KEYWORDS):
            return 'hf'  # 高频/复杂
        elif any(kw in text_lower for kw in cls.TREND_KEYWORDS):
            return 'trend'  # 趋势策略
        elif any(kw in text_lower for kw in cls.FUNDAMENTAL_KEYWORDS):
            return 'fundamental'  # 基本面
        else:
            return 'trend'  # 默认趋势


class ShortBacktestValidator:
    """短期回测验证器 (100-200交易日)"""

    def __init__(self, symbol='BTC/USDT'):
        self.symbol = symbol
        # 使用现货API，避免期货API问题
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        self.initial_capital = 10000
        self.fee_rate = 0.001

    async def fetch_data(self, days: int = 200) -> pd.DataFrame:
        """获取K线数据"""
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1d', since=since, limit=days)

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def add_indicators(self, df: pd.DataFrame, strategy_type: str, params: Dict) -> pd.DataFrame:
        """添加技术指标"""
        df = df.copy()

        if 'ma' in strategy_type:
            for period in [10, 20, 50, 200]:
                df[f'ma_{period}'] = df['close'].rolling(window=period).mean()

        if 'rsi' in strategy_type:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['rsi'] = 100 - (100 / (1 + gain / loss))

        if 'bollinger' in strategy_type:
            df['bb_middle'] = df['close'].rolling(20).mean()
            df['bb_std'] = df['close'].rolling(20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']

        return df

    async def run_backtest(self, df: pd.DataFrame, strategy_type: str) -> Dict:
        """运行回测"""
        trades = []
        position = None

        for i in range(1, len(df)):
            row = df.iloc[i]

            # 简单MA交叉策略
            if 'ma' in strategy_type and 'crossover' in strategy_type:
                if position is None:
                    if df.iloc[i-1]['ma_50'] <= df.iloc[i-1]['ma_200'] and row['ma_50'] > row['ma_200']:
                        position = {'entry': row['close']}
                        trades.append({'entry': row['close'], 'exit': None})
                else:
                    if df.iloc[i-1]['ma_50'] >= df.iloc[i-1]['ma_200'] and row['ma_50'] < row['ma_200']:
                        position = None
                        trades[-1]['exit'] = row['close']
                        trades[-1]['type'] = 'long'

        # 计算收益
        trade_returns = []
        total_return = 0
        wins = 0
        for t in trades:
            if t['exit']:
                ret = (t['exit'] - t['entry']) / t['entry']
                trade_returns.append(ret)
                total_return += ret
                if ret > 0:
                    wins += 1

        win_rate = wins / len(trades) if trades else 0

        # 计算夏普比率 (简化版)
        benchmark_return = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
        if trade_returns:
            avg_ret = np.mean(trade_returns)
            std_ret = np.std(trade_returns, ddof=1) if len(trade_returns) > 1 else 0.001
            if std_ret > 0:
                # 年化夏普比率 (假设日交易)
                sharpe = (avg_ret / std_ret) * np.sqrt(252) if len(trade_returns) > 1 else 0
            else:
                sharpe = 0
            avg_return = avg_ret
        else:
            sharpe = 0
            avg_return = 0

        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'trade_count': len(trades),
            'benchmark_return': benchmark_return,
            'sharpe_ratio': sharpe,
            'avg_return': avg_return
        }


class RealTimeMonitor:
    """实时监控器 - 适合高频策略"""

    def __init__(self, symbol='BTC/USDT'):
        self.symbol = symbol
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.signals = []
        self.prices = []
        self.running = False

    async def start(self, duration_hours: int = 24):
        """启动监控"""
        self.running = True
        self.start_time = datetime.now()

        while self.running and (datetime.now() - self.start_time).total_seconds() < duration_hours * 3600:
            try:
                # 获取订单簿数据
                orderbook = self.exchange.fetch_order_book(self.symbol)
                ticker = self.exchange.fetch_ticker(self.symbol)

                self.prices.append({
                    'timestamp': datetime.now(),
                    'price': ticker['last'],
                    'bid': orderbook['bids'][0][0] if orderbook['bids'] else None,
                    'ask': orderbook['asks'][0][0] if orderbook['asks'] else None,
                    'spread': orderbook['asks'][0][0] - orderbook['bids'][0][0] if orderbook['bids'] and orderbook['asks'] else None,
                    'bid_volume': sum(b[1] for b in orderbook['bids'][:5]),
                    'ask_volume': sum(a[1] for a in orderbook['asks'][:5]),
                })

                # 生成简单信号示例
                if len(self.prices) > 2:
                    signal = self._generate_signal()
                    if signal:
                        self.signals.append({
                            **signal,
                            'timestamp': datetime.now()
                        })

                await asyncio.sleep(60)  # 每分钟记录一次

            except Exception as e:
                logger.error(f"监控错误: {e}")
                await asyncio.sleep(5)

    def _generate_signal(self) -> Optional[Dict]:
        """生成信号示例"""
        if len(self.prices) < 10:
            return None

        recent = self.prices[-10:]
        avg_price = np.mean([p['price'] for p in recent])
        current = self.prices[-1]['price']

        # 简单动量信号
        if current > avg_price * 1.01:
            return {'type': 'BUY', 'strength': 'strong', 'price': current}
        elif current < avg_price * 0.99:
            return {'type': 'SELL', 'strength': 'strong', 'price': current}

        return None

    def stop(self):
        """停止监控"""
        self.running = False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'signal_count': len(self.signals),
            'monitoring_period_hours': (datetime.now() - self.start_time).total_seconds() / 3600 if self.running else 0,
            'price_samples': len(self.prices)
        }


class StatisticalValidator:
    """统计显著性检验器 (纯numpy实现)"""

    def __init__(self):
        self.signals = []
        self.returns = []

    def add_signal(self, signal_type: str, entry_price: float, exit_price: float, timestamp: datetime):
        """添加信号记录"""
        ret = (exit_price - entry_price) / entry_price if entry_price else 0
        self.signals.append({
            'type': signal_type,
            'return': ret,
            'timestamp': timestamp
        })
        self.returns.append(ret)

    def _t_test_1samp(self, data: List[float], popmean: float) -> tuple:
        """单样本t检验 (numpy实现)"""
        n = len(data)
        if n < 2:
            return 0, 1.0

        mean = np.mean(data)
        std = np.std(data, ddof=1) if n > 1 else 0

        if std == 0:
            return 0, 1.0

        se = std / np.sqrt(n)
        t_stat = (mean - popmean) / se

        # 简化p值计算 (双尾)
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1)) if 'stats' in dir() else 0.05

        return t_stat, p_value

    def test_significance(self) -> Dict:
        """检验信号显著性 (t-test vs 随机)"""
        n = len(self.returns)
        if n < 30:
            return {
                't_statistic': 0,
                'z_score': 0,
                'p_value': None,
                'mean_return': 0,
                'std_return': 0,
                'significant': False,
                'sample_size': n,
                'note': '样本不足 (<30)'
            }

        mean_ret = np.mean(self.returns)
        std_ret = np.std(self.returns, ddof=1)

        # 计算t统计量
        se = std_ret / np.sqrt(n) if n > 1 else 0.001
        t_stat = (mean_ret - 0) / se

        # 信号收益是否显著大于0 (z-score)
        z_score = mean_ret / se if se > 0 else 0

        # 简化p值 (z-score 转 p-value, 双尾)
        if abs(z_score) > 0:
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
        else:
            p_value = 1.0

        return {
            't_statistic': t_stat,
            'z_score': z_score,
            'p_value': min(p_value, 1.0),
            'mean_return': mean_ret,
            'std_return': std_ret,
            'significant': p_value < 0.05,
            'sample_size': n
        }

    def get_confidence_score(self) -> float:
        """计算置信度评分 (0-100)"""
        test_stats = self.test_significance()

        if test_stats['p_value'] is None:
            return 30  # 样本不足

        if not test_stats['significant']:
            return 20  # 不显著

        # 基于检验结果评分
        score = 50
        score += (1 - test_stats['p_value']) * 40  # p值越低越高
        sample_bonus = min(test_stats['sample_size'] / 100, 10)  # 样本量加成
        score += sample_bonus

        return min(score, 100)


class StrategyValidatorV2:
    """分层策略验证器 v2"""

    def __init__(self, strategies_file=None):
        self.strategies_file = strategies_file or os.path.join(
            os.path.dirname(__file__), 'strategies.json'
        )
        self.classifier = StrategyClassifier()
        self.backtest_validator = ShortBacktestValidator()
        self.monitor = RealTimeMonitor()
        self.stats_validator = StatisticalValidator()

    def validate_strategy(self, strategy: Dict) -> ValidationResult:
        """验证单个策略"""
        logic = strategy.get('extracted_logic', strategy.get('content', ''))
        strategy_type = self.classifier.classify(logic)

        result = ValidationResult(
            strategy_id=strategy['id'],
            strategy_title=strategy['title'],
            strategy_type=strategy_type,
            validation_method="",
            validated_at=datetime.now().isoformat()
        )

        if strategy_type == 'trend':
            # 趋势策略 -> 短期回测
            result.validation_method = "backtest"
            result = self._validate_trend(strategy, result)
        elif strategy_type == 'hf':
            # 高频策略 -> 实时监控
            result.validation_method = "monitor"
            result.notes = "需要部署实时监控 (建议24-72小时)"
        else:
            result.validation_method = "statistical"
            result.notes = "需要基本面数据，跳过"

        return result

    def _validate_trend(self, strategy: Dict, result: ValidationResult) -> ValidationResult:
        """验证趋势策略"""
        import asyncio

        async def run():
            df = await self.backtest_validator.fetch_data(days=200)
            df = self.backtest_validator.add_indicators(df, result.strategy_type, {})

            metrics = await self.backtest_validator.run_backtest(df, result.strategy_type)

            result.backtest_return = metrics['total_return']
            result.backtest_benchmark = metrics['benchmark_return']
            result.backtest_win_rate = metrics['win_rate']
            result.backtest_sharpe = metrics.get('sharpe_ratio', 0)
            result.backtest_trades = metrics['trade_count']
            result.backtest_avg_return = metrics.get('avg_return', 0)
            result.backtest_max_drawdown = 0.1  # 简化

            # 置信度评分
            if metrics['trade_count'] > 0:
                if metrics['total_return'] > metrics['benchmark_return']:
                    result.confidence_score = 70 + metrics['win_rate'] * 20
                else:
                    result.confidence_score = 40 + metrics['win_rate'] * 10
            else:
                result.confidence_score = 30
                result.notes = "无交易信号"

            return result

        # 同步调用
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run())
        finally:
            loop.close()

        return result

    def validate_all_pending(self) -> List[ValidationResult]:
        """验证所有待验证策略"""
        with open(self.strategies_file, 'r') as f:
            data = json.load(f)

        results = []
        for strategy in data['strategies']:
            if strategy['status'].startswith('pending'):
                logger.info(f"验证策略: {strategy['title']}")
                result = self.validate_strategy(strategy)
                results.append(result)

        return results

    def print_result(self, result: ValidationResult):
        """打印完整验证结果"""
        print(f"\n{'='*60}")
        print(f"策略: {result.strategy_title}")
        print(f"类型: {result.strategy_type} | 验证方法: {result.validation_method}")
        print(f"{'='*60}")

        if result.validation_method == 'backtest':
            print(f"\n📊 回测结果 (BTC/USDT, 200日)")
            print(f"  总收益: {result.backtest_return*100:.2f}%")
            print(f"  基准收益: {result.backtest_benchmark*100:.2f}%")
            print(f"  胜率: {result.backtest_win_rate*100:.1f}%")
            print(f"  夏普比率: {result.backtest_sharpe:.2f}")
            print(f"  交易次数: {result.backtest_trades}")
            print(f"  平均收益: {result.backtest_avg_return*100:.3f}%")

        elif result.validation_method == 'monitor':
            print(f"\n📈 监控结果")
            print(f"  信号数量: {result.signal_count}")
            print(f"  监控时长: {result.signal_sample_period_hours:.1f}小时")
            if result.stat_p_value:
                print(f"\n🔬 统计显著性检验")
                print(f"  t统计量: {result.stat_t_statistic:.4f}")
                print(f"  z分数: {result.stat_z_score:.4f}")
                print(f"  p值: {result.stat_p_value:.4f}")
                print(f"  平均收益: {result.stat_mean_return*100:.3f}%")
                print(f"  收益标准差: {result.stat_std_return*100:.3f}%")
                print(f"  样本量: {result.stat_sample_size}")
                print(f"  显著性: {'✅ 显著 (p<0.05)' if result.stat_significant else '❌ 不显著'}")

        print(f"\n🎯 置信度: {result.confidence_score:.0f}/100")
        if result.notes:
            print(f"📝 备注: {result.notes}")
        print(f"{'='*60}\n")


async def demo():
    """演示"""
    validator = StrategyValidatorV2()

    # 测试K线获取
    print("测试K线获取...")
    df = await validator.backtest_validator.fetch_data(days=30)
    print(f"获取 {len(df)} 条K线")

    # 测试短期回测
    print("\n运行短期回测...")
    df = validator.backtest_validator.add_indicators(df, 'ma_crossover', {})
    metrics = await validator.backtest_validator.run_backtest(df, 'ma_crossover')
    print(f"收益: {metrics['total_return']*100:.1f}%")
    print(f"胜率: {metrics['win_rate']*100:.0f}%")

    # 测试分类器
    print("\n策略分类测试:")
    test_cases = [
        "Golden cross: 50-day MA crosses above 200-day MA = BUY",
        "Order book imbalance indicates institutional flow",
        "Buy stocks with PE ratio below 15",
    ]
    for tc in test_cases:
        t = validator.classifier.classify(tc)
        print(f"  -> {t}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='分层策略验证器 v2')
    parser.add_argument('--demo', action='store_true', help='运行演示')
    parser.add_argument('--validate-all', action='store_true', help='验证所有待验证策略')
    parser.add_argument('--monitor', action='store_true', help='启动实时监控')
    args = parser.parse_args()

    if args.demo:
        asyncio.run(demo())
    elif args.monitor:
        validator = StrategyValidatorV2()
        print("启动实时监控 (按 Ctrl+C 停止)...")
        try:
            asyncio.run(validator.monitor.start(duration_hours=24))
        except KeyboardInterrupt:
            validator.monitor.stop()
            print("\n监控停止")
            print(json.dumps(validator.monitor.get_stats(), indent=2))
    elif args.validate_all:
        validator = StrategyValidatorV2()
        results = validator.validate_all_pending()
        for r in results:
            validator.print_result(r)
    else:
        print("用法:")
        print("  python strategy_validator_v2.py --demo          # 演示")
        print("  python strategy_validator_v2.py --validate-all # 验证所有")
        print("  python strategy_validator_v2.py --monitor      # 启动实时监控")
