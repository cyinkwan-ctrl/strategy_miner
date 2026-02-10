#!/usr/bin/env python3
"""
策略验证引擎
将自然语言策略转换为可执行逻辑并回测验证
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np

# 加载配置
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/januswing/.openclaw/workspace/strategy_miner/logs/validator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('strategy_validator')

@dataclass
class BacktestResult:
    """回测结果"""
    annual_return: float  # 年化收益率
    max_drawdown: float  # 最大回撤
    win_rate: float  # 胜率
    total_trades: int  # 总交易数
    profit_factor: float  # 盈亏比
    sharpe_ratio: float  # 夏普比率
    avg_trade_return: float  # 平均交易收益
    holding_period_days: float  # 平均持仓天数
    equity_curve: List[float]  # 资金曲线

class StrategyParser:
    """策略解析器 - 将自然语言转换为交易逻辑"""
    
    def __init__(self):
        self.patterns = {
            'ma_crossover': [
                r'(?:ma|moving average|simple moving average|sma)\s*(\d+)',
                r'(\d+)[- ]?day\s*(?:ma|moving average)',
                r'(?:golden cross|death cross)',
            ],
            'rsi_oversold': [
                r'(?:rsi)\s*(?:below|under|<)\s*(\d+)',
                r'(?:oversold|rsi\s*<)\s*(\d+)',
            ],
            'rsi_overbought': [
                r'(?:rsi)\s*(?:above|over|>)\s*(\d+)',
                r'(?:overbought|rsi\s*>)\s*(\d+)',
            ],
            'bollinger_bands': [
                r'(?:bollinger|bb)\s*(?:bands?)?',
                r'(?:touch|break)\s*(?:upper|lower)\s*(?:band|bb)',
            ],
            'trend_following': [
                r'(?:trend|trendline)',
                r'(?:higher\s*highs?|higher\s*lows?)',
                r'(?:uptrend|downtrend)',
            ],
            'support_resistance': [
                r'(?:support|resistance)',
                r'(?:breakout|pullback)',
            ],
            'stop_loss': [
                r'(?:stop[- ]?loss|sl)\s*(\d+)%',
                r'(?:stop[- ]?loss|sl)\s*at\s*(\d+)',
            ],
            'take_profit': [
                r'(?:take[- ]?profit|tp)\s*(\d+)%',
                r'(?:take[- ]?profit|tp)\s*at\s*(\d+)',
            ],
        }
    
    def parse(self, logic_text: str) -> Dict[str, Any]:
        """解析策略逻辑"""
        result = {
            'type': 'unknown',
            'parameters': {},
            'entry_conditions': [],
            'exit_conditions': [],
            'stop_loss': None,
            'take_profit': None,
        }
        
        text_lower = logic_text.lower()
        
        # MA 交叉策略
        if any(re.search(p, text_lower) for p in self.patterns['ma_crossover']):
            result['type'] = 'ma_crossover'
            ma_match = re.search(r'(\d+)[- ]?day', text_lower)
            if ma_match:
                result['parameters']['fast_ma'] = 10
                result['parameters']['slow_ma'] = int(ma_match.group(1))
        
        # RSI 策略
        rsi_under = re.search(r'rsi\s*(?:below|under|<)\s*(\d+)', text_lower)
        rsi_over = re.search(r'rsi\s*(?:above|over|>)\s*(\d+)', text_lower)
        
        if rsi_under:
            result['type'] = 'rsi_oversold'
            result['parameters']['rsi_oversold'] = int(rsi_under.group(1))
        elif rsi_over:
            result['type'] = 'rsi_overbought'
            result['parameters']['rsi_overbought'] = int(rsi_over.group(1))
        
        # 布林带策略
        if any(re.search(p, text_lower) for p in self.patterns['bollinger_bands']):
            result['type'] = 'bollinger_bands'
        
        # 趋势跟踪
        if any(re.search(p, text_lower) for p in self.patterns['trend_following']):
            result['type'] = 'trend_following'
        
#         # 支撑阻力
#         if any(re.search(p, text_lower) for p in self.patterns['support_resistance']):
#             result['type'] = 'breakout'
        
        # 止损止盈
        sl_match = re.search(r'(?:stop[- ]?loss|sl)\s*(\d+)%', text_lower)
        if sl_match:
            result['stop_loss'] = int(sl_match.group(1)) / 100
        
        tp_match = re.search(r'(?:take[- ]?profit|tp)\s*(\d+)%', text_lower)
        if tp_match:
            result['take_profit'] = int(tp_match.group(1)) / 100
        
        # 通用买入/卖出条件
        if 'buy' in text_lower or 'long' in text_lower:
            result['entry_conditions'].append('buy_signal')
        if 'sell' in text_lower or 'short' in text_lower:
            result['exit_conditions'].append('sell_signal')
        
        return result

class MarketDataFetcher:
    """市场数据获取器"""
    
    def __init__(self):
        self.exchange_id = os.getenv('EXCHANGE_ID', 'binance')
        self.symbol = os.getenv('SYMBOL', 'BTC/USDT')
        self.timeframe = os.getenv('TIMEFRAME', '1d')
        self.exchange = None
        
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            self.exchange = getattr(ccxt, self.exchange_id)({
                'enableRateLimit': True,
                'timeout': 30000,
            })
            logger.info(f"已连接交易所: {self.exchange_id}")
        except Exception as e:
            logger.error(f"连接交易所失败: {e}")
    
    def fetch_ohlcv(self, since: str = None, limit: int = 1000) -> pd.DataFrame:
        """获取K线数据"""
        if not self.exchange:
            self._init_exchange()
        
        try:
            # 默认获取最近的数据
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol,
                self.timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"获取到 {len(df)} 条K线数据")
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return pd.DataFrame()

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self):
        self.initial_capital = float(os.getenv('INITIAL_CAPITAL', 10000))
        self.fee_rate = 0.001  # 0.1% 手续费
    
    def add_indicators(self, df: pd.DataFrame, strategy_type: str, params: Dict) -> pd.DataFrame:
        """添加技术指标"""
        df = df.copy()
        
        # 移动平均线
        if 'ma' in strategy_type:
            period = params.get('slow_ma', 20)
            df['ma_slow'] = df['close'].rolling(window=period).mean()
            df['ma_fast'] = df['close'].rolling(window=10).mean()
        
        # RSI
        if 'rsi' in strategy_type:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        
        # 布林带
        if 'bollinger' in strategy_type:
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        
        return df
    
    def run_ma_crossover(self, df: pd.DataFrame, params: Dict) -> Tuple[List, List]:
        """MA交叉策略回测"""
        trades = []
        position = None
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # 买入信号：快线突破慢线
            if position is None:
                if prev_row['ma_fast'] <= prev_row['ma_slow'] and row['ma_fast'] > row['ma_slow']:
                    position = {
                        'entry_price': row['close'],
                        'entry_time': row.name,
                        'size': self.initial_capital / row['close']
                    }
                    trades.append({
                        'type': 'long',
                        'entry_price': row['close'],
                        'entry_time': row.name,
                        'exit_price': None,
                        'exit_time': None
                    })
            
            # 卖出信号：快线下穿慢线
            else:
                if prev_row['ma_fast'] >= prev_row['ma_slow'] and row['ma_fast'] < row['ma_slow']:
                    position['exit_price'] = row['close']
                    position['exit_time'] = row.name
                    trades[-1]['exit_price'] = row['close']
                    position['exit_time'] = row.name
                    position = None
        
        # 平仓未结束的持仓
        if position:
            trades[-1]['exit_price'] = df.iloc[-1]['close']
            trades[-1]['exit_time'] = df.iloc[-1].name
        
        return trades, df
    
    def run_rsi_strategy(self, df: pd.DataFrame, params: Dict) -> Tuple[List, pd.DataFrame]:
        """RSI策略回测"""
        oversold = params.get('rsi_oversold', 30)
        trades = []
        position = None
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            
            # 买入信号：RSI低于超卖线
            if position is None:
                if row['rsi'] < oversold:
                    position = {
                        'entry_price': row['close'],
                        'entry_time': row.name
                    }
                    trades.append({
                        'type': 'long',
                        'entry_price': row['close'],
                        'entry_time': row.name,
                        'exit_price': None,
                        'exit_time': None
                    })
            
            # 卖出信号：RSI回到50以上
            else:
                if row['rsi'] > 50:
                    position['exit_price'] = row['close']
                    position['exit_time'] = row.name
                    trades[-1]['exit_price'] = row['close']
                    trades[-1]['exit_time'] = row.name
                    position = None
        
        # 平仓未结束的持仓
        if position and trades:
            trades[-1]['exit_price'] = df.iloc[-1]['close']
            trades[-1]['exit_time'] = df.iloc[-1].name
        
        return trades, df
    
    def calculate_metrics(self, trades: List, df: pd.DataFrame) -> BacktestResult:
        """计算回测指标"""
        if not trades:
            return BacktestResult(
                annual_return=0,
                max_drawdown=1,
                win_rate=0,
                total_trades=0,
                profit_factor=0,
                sharpe_ratio=0,
                avg_trade_return=0,
                holding_period_days=0,
                equity_curve=[]
            )
        
        # 计算权益曲线
        equity = [self.initial_capital]
        current_capital = self.initial_capital
        wins = 0
        losses = 0
        gross_profit = 0
        gross_loss = 0
        total_holding_days = 0
        
        for trade in trades:
            if trade['exit_price']:
                entry = trade['entry_price']
                exit = trade['exit_price']
                return_pct = (exit - entry) / entry
                
                # 计算手续费
                fee = current_capital * self.fee_rate
                current_capital = current_capital * (1 + return_pct) - fee
                
                if return_pct > 0:
                    wins += 1
                    gross_profit += current_capital
                else:
                    losses += 1
                    gross_loss += abs(current_capital)
                
                equity.append(current_capital)
                
                # 持仓天数
                if trade['exit_time'] and trade['entry_time']:
                    days = (trade['exit_time'] - trade['entry_time']).days
                    total_holding_days += days
        
        # 年化收益率
        total_days = (df.index[-1] - df.index[0]).days
        total_return = (equity[-1] - equity[0]) / equity[0]
        annual_return = ((1 + total_return) ** (365 / total_days)) - 1 if total_days > 0 else 0
        
        # 最大回撤
        peak = equity[0]
        max_drawdown = 0
        for value in equity:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 胜率
        total = wins + losses
        win_rate = wins / total if total > 0 else 0
        
        # 盈亏比
        avg_win = gross_profit / wins if wins > 0 else 0
        avg_loss = gross_loss / losses if losses > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 夏普比率
        returns = np.diff(equity) / equity[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # 平均持仓天数
        avg_holding_days = total_holding_days / total if total > 0 else 0
        
        return BacktestResult(
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            avg_trade_return=total_return / total if total > 0 else 0,
            holding_period_days=avg_holding_days,
            equity_curve=equity
        )

class StrategyValidator:
    """策略验证主类"""
    
    def __init__(self):
        self.data_fetcher = MarketDataFetcher()
        self.parser = StrategyParser()
        self.backtest_engine = BacktestEngine()
        self.strategies_file = '/Users/januswing/.openclaw/workspace/strategy_miner/strategies.json'
        
        # 验证阈值
        self.min_annual_return = float(os.getenv('MIN_ANNUAL_RETURN', 0.12))
        self.max_drawdown = float(os.getenv('MAX_DRAWDOWN', 0.10))
        self.min_trades = int(os.getenv('MIN_TRADES', 100))
        self.min_win_rate = float(os.getenv('MIN_WIN_RATE', 0.55))
    
    def validate(self, strategy_id: int) -> Dict:
        """验证指定策略"""
        # 读取策略
        with open(self.strategies_file, 'r') as f:
            data = json.load(f)
        
        strategy = None
        for s in data['strategies']:
            if s['id'] == strategy_id:
                strategy = s
                break
        
        if not strategy:
            logger.error(f"策略不存在: {strategy_id}")
            return None
        
        logger.info(f"开始验证策略: {strategy['title']}")
        logger.info(f"策略逻辑: {strategy['extracted_logic']}")
        
        # 解析策略
        parsed = self.parser.parse(strategy['extracted_logic'])
        logger.info(f"解析结果: {parsed}")
        
        # 获取市场数据
        df = self.data_fetcher.fetch_ohlcv()
        if df.empty:
            logger.error("无法获取市场数据")
            return None
        
        # 添加指标
        df = self.backtest_engine.add_indicators(df, parsed['type'], parsed['parameters'])
        
        # 执行回测
        if parsed['type'] == 'ma_crossover':
            trades, df = self.backtest_engine.run_ma_crossover(df, parsed['parameters'])
        elif 'rsi' in parsed['type']:
            trades, df = self.backtest_engine.run_rsi_strategy(df, parsed['parameters'])
        else:
            # 默认使用MA策略
            logger.warning(f"未知策略类型 {parsed['type']}，使用MA交叉策略")
            trades, df = self.backtest_engine.run_ma_crossover(df, parsed.get('parameters', {}))
        
        # 计算指标
        result = self.backtest_engine.calculate_metrics(trades, df)
        
        # 验证结果
        passed = (
            result.annual_return >= self.min_annual_return and
            result.max_drawdown <= self.max_drawdown and
            result.total_trades >= self.min_trades and
            result.win_rate >= self.min_win_rate
        )
        
        # 更新策略状态
        for s in data['strategies']:
            if s['id'] == strategy_id:
                s['validated_at'] = datetime.now().isoformat()
                s['status'] = 'passed' if passed else 'rejected'
                s['backtest_result'] = {
                    'annual_return': round(result.annual_return * 100, 2),
                    'max_drawdown': round(result.max_drawdown * 100, 2),
                    'win_rate': round(result.win_rate * 100, 2),
                    'total_trades': result.total_trades,
                    'profit_factor': round(result.profit_factor, 2),
                    'sharpe_ratio': round(result.sharpe_ratio, 2),
                    'parsed_strategy': parsed
                }
                
                if passed:
                    data['metadata']['passed'] += 1
                else:
                    data['metadata']['rejected'] += 1
                
                break
        
        # 保存
        with open(self.strategies_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"验证完成: {'通过' if passed else '拒绝'}")
        logger.info(f"年化收益: {result.annual_return*100:.2f}%, "
                   f"最大回撤: {result.max_drawdown*100:.2f}%, "
                   f"胜率: {result.win_rate*100:.2f}%, "
                   f"交易数: {result.total_trades}")
        
        return {
            'passed': passed,
            'metrics': {
                'annual_return': result.annual_return * 100,
                'max_drawdown': result.max_drawdown * 100,
                'win_rate': result.win_rate * 100,
                'total_trades': result.total_trades,
                'profit_factor': result.profit_factor,
                'sharpe_ratio': result.sharpe_ratio
            }
        }
    
    def validate_pending(self) -> List[Dict]:
        """验证所有待验证的策略"""
        with open(self.strategies_file, 'r') as f:
            data = json.load(f)
        
        results = []
        for strategy in data['strategies']:
            if strategy['status'] == 'pending':
                result = self.validate(strategy['id'])
                if result:
                    results.append({
                        'id': strategy['id'],
                        'title': strategy['title'],
                        **result
                    })
        
        return results

if __name__ == "__main__":
    import sys
    
    # 确保logs目录存在
    os.makedirs('/Users/januswing/.openclaw/workspace/strategy_miner/logs', exist_ok=True)
    
    validator = StrategyValidator()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--all':
        # 验证所有待验证策略
        results = validator.validate_pending()
        print(f"\n验证完成，共处理 {len(results)} 个策略:")
        for r in results:
            status = "✅ 通过" if r['passed'] else "❌ 拒绝"
            print(f"  {r['id']}. {r['title'][:50]}... - {status}")
            if r['passed']:
                print(f"     年化: {r['metrics']['annual_return']:.2f}%, "
                      f"回撤: {r['metrics']['max_drawdown']:.2f}%, "
                      f"胜率: {r['metrics']['win_rate']:.2f}%")
    elif len(sys.argv) > 1:
        # 验证指定策略
        strategy_id = int(sys.argv[1])
        result = validator.validate(strategy_id)
        if result:
            status = "✅ 通过" if result['passed'] else "❌ 拒绝"
            print(f"\n策略 {strategy_id} 验证结果: {status}")
            print(f"  年化收益: {result['metrics']['annual_return']:.2f}%")
            print(f"  最大回撤: {result['metrics']['max_drawdown']:.2f}%")
            print(f"  胜率: {result['metrics']['win_rate']:.2f}%")
            print(f"  交易数: {result['metrics']['total_trades']}")
    else:
        print("用法:")
        print("  python strategy_validator.py <strategy_id>  # 验证指定策略")
        print("  python strategy_validator.py --all          # 验证所有待验证策略")
