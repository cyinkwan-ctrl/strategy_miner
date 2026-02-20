#!/usr/bin/env python3
"""
RSI 策略交易脚本
参数: RSI7 | RSI<20买入 | RSI>45卖出 | RSI>65做空 | RSI<35平空
"""

import os
import sys
import json
import ccxt
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 配置
CONFIG = {
    'symbol': 'BTC/USDT',
    'rsi_period': 7,
    'oversold': 20,      # RSI < 20 买入
    'overbought_exit': 45,  # RSI > 45 卖出
    'short_level': 65,   # RSI > 65 做空
    'short_cover': 35,   # RSI < 35 平空
}

STATE_FILE = Path(__file__).parent / 'rsi_state.json'
LOG_FILE = Path(__file__).parent / 'logs' / 'rsi_trades.log'

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'position': 0, 'entry_price': 0, 'entry_rsi': 0, 'entry_time': '', 'type': ''}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def calc_rsi(prices, period=7):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    return 100 - (100 / (1 + avg_gain / avg_loss))

def get_data():
    """获取最新数据"""
    exchange = ccxt.binance({'enableRateLimit': True})
    ohlcv = exchange.fetch_ohlcv(CONFIG['symbol'], '1d', limit=50)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df['rsi'] = calc_rsi(df['close'], CONFIG['rsi_period'])
    return df

def check_signals(df):
    """检查交易信号"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    rsi = latest['rsi']
    price = latest['close']
    
    state = load_state()
    position = state.get('position', 0)
    
    signals = []
    
    # 做多信号: RSI < oversold 且无持仓
    if rsi < CONFIG['oversold'] and position == 0:
        signals.append({
            'action': 'BUY_LONG',
            'price': price,
            'rsi': rsi,
            'reason': f'RSI={rsi:.1f} < {CONFIG["oversold"]} (超卖)'
        })
    
    # 平多信号: RSI > overbought_exit 且有多仓
    elif rsi > CONFIG['overbought_exit'] and position > 0:
        signals.append({
            'action': 'SELL_LONG',
            'price': price,
            'rsi': rsi,
            'reason': f'RSI={rsi:.1f} > {CONFIG["overbought_exit"]} (超买)'
        })
    
    # 做空信号: RSI > short_level 且无持仓
    elif rsi > CONFIG['short_level'] and position == 0:
        signals.append({
            'action': 'SHORT',
            'price': price,
            'rsi': rsi,
            'reason': f'RSI={rsi:.1f} > {CONFIG["short_level"]} (超买)'
        })
    
    # 平空信号: RSI < short_cover 且有空仓
    elif rsi < CONFIG['short_cover'] and position < 0:
        signals.append({
            'action': 'COVER_SHORT',
            'price': price,
            'rsi': rsi,
            'reason': f'RSI={rsi:.1f} < {CONFIG["short_cover"]} (超卖)'
        })
    
    return signals, rsi, price

def main():
    print(f"\n{'='*50}")
    print(f"📊 RSI 策略信号检查 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    try:
        df = get_data()
        signals, rsi, price = check_signals(df)
        
        print(f"\n当前: BTC ${price:.2f} | RSI: {rsi:.1f}")
        print(f"持仓: {load_state()}")
        
        if signals:
            for s in signals:
                print(f"\n⚡️ 信号: {s['action']}")
                print(f"   价格: ${s['price']:.2f}")
                print(f"   原因: {s['reason']}")
                
                # 更新状态
                state = load_state()
                if s['action'] == 'BUY_LONG':
                    state = {'position': 1, 'entry_price': s['price'], 'entry_rsi': s['rsi'], 'entry_time': str(datetime.now()), 'type': 'LONG'}
                elif s['action'] == 'SELL_LONG':
                    state = {'position': 0, 'entry_price': 0, 'entry_rsi': 0, 'entry_time': '', 'type': ''}
                elif s['action'] == 'SHORT':
                    state = {'position': -1, 'entry_price': s['price'], 'entry_rsi': s['rsi'], 'entry_time': str(datetime.now()), 'type': 'SHORT'}
                elif s['action'] == 'COVER_SHORT':
                    state = {'position': 0, 'entry_price': 0, 'entry_rsi': 0, 'entry_time': '', 'type': ''}
                
                save_state(state)
                
                # 输出 JSON 供 cron 读取
                print(f"\n📤 SIGNAL_JSON: {json.dumps(s)}")
        else:
            print("\n✅ 无新信号")
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
