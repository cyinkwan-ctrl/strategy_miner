#!/usr/bin/env python3
"""
TradingView 情绪监控看板
Streamlit dashboard for sentiment analysis
"""

import os
from pathlib import Path
import sys
import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import feedparser
import ccxt
import re
from collections import defaultdict

# Page config
st.set_page_config(
    page_title="TradingView Sentiment Dashboard",
    page_icon="📊",
    layout="wide"
)

# Constants
STATE_FILE = Path(__file__).parent / 'sentiment_validator_state.json'
VALIDATION_WINDOWS = [15, 30, 60, 120, 240, 1440]

# Asset mapping
ASSET_MAPPING = {
    'BTCUSDT': 'BTC', 'BTCUSD': 'BTC', 'BTC': 'BTC',
    'ETHUSDT': 'ETH', 'ETHUSD': 'ETH', 'ETH': 'ETH',
    'XAUUSD': 'XAU', 'XAU': 'XAU', 'GOLD': 'XAU',
    'XAGUSD': 'XAG', 'XAG': 'XAG',
}

# Sentiment keywords
BULLISH_KEYWORDS = ['bullish', 'buy', 'long', 'up', 'higher', 'breakout', 'call', 'support', 'bounce', 'recovery']
BEARISH_KEYWORDS = ['bearish', 'sell', 'short', 'down', 'lower', 'breakdown', 'put', 'resistance', 'reject', 'drop']

# Title
st.title("📊 TradingView 情绪监控看板")
st.markdown("---")


def load_state():
    """加载状态数据"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'records': [], 'validations': []}


def analyze_sentiment(text):
    """分析情绪"""
    text_lower = text.lower()
    bullish = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)

    if bullish > bearish:
        return 'bullish'
    elif bearish > bullish:
        return 'bearish'
    return 'neutral'


def get_current_sentiment():
    """获取当前情绪快照"""
    try:
        feed = feedparser.parse('https://www.tradingview.com/feed/')
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return []

    asset_counts = defaultdict(lambda: {'bullish': 0, 'bearish': 0, 'neutral': 0, 'ids': []})
    seen_ids = set()

    state = load_state()
    for r in state.get('records', []):
        seen_ids.add(r['id'])

    for entry in feed.entries:
        idea_id = re.search(r'/([a-zA-Z0-9-]+)/?$', entry.get('link', ''))
        if not idea_id or idea_id.group(1) in seen_ids:
            continue

        url = entry.get('link', '')
        asset_match = re.search(r'/chart/([A-Z]+)/', url)
        raw_asset = asset_match.group(1) if asset_match else 'OTHER'
        asset = ASSET_MAPPING.get(raw_asset, raw_asset)

        sentiment = analyze_sentiment(entry.get('title', '') + ' ' + entry.get('summary', ''))
        asset_counts[asset][sentiment] += 1
        asset_counts[asset]['ids'].append(idea_id.group(1))

    snapshots = []
    for asset, counts in asset_counts.items():
        total = counts['bullish'] + counts['bearish'] + counts['neutral']
        if total > 0:
            snapshots.append({
                'asset': asset,
                'total': total,
                'bullish': counts['bullish'],
                'bearish': counts['bearish'],
                'neutral': counts['neutral'],
                'bullish_ratio': counts['bullish'] / total
            })

    return snapshots


def display_sentiment_gauge(asset_data):
    """显示情绪仪表"""
    ratio = asset_data['bullish_ratio']
    color = 'green' if ratio > 0.6 else ('red' if ratio < 0.4 else 'gray')

    st.markdown(f"**{asset_data['asset']}**")
    st.progress(ratio)

    col1, col2, col3 = st.columns(3)
    col1.metric("看涨", f"{asset_data['bullish']}")
    col2.metric("看跌", f"{asset_data['bearish']}")
    col3.metric("比例", f"{ratio*100:.0f}%")

    return ratio


def display_validation_results():
    """显示验证结果"""
    state = load_state()
    validations = state.get('validations', [])

    if not validations:
        st.info("等待更多数据积累...")
        return

    # 按资产分组
    by_asset = defaultdict(list)
    for v in validations:
        by_asset[v['asset']].append(v)

    st.subheader("📈 验证结果")

    for asset, vals in sorted(by_asset.items(), key=lambda x: -len(x[1])):
        with st.expander(f"{asset} ({len(vals)}条)", expanded=True):
            # 找最佳窗口
            best = max(vals, key=lambda x: x.get('accuracy', 0))

            st.metric("最佳窗口", f"{best.get('window', '?')}分钟",
                     f"{best.get('accuracy', 0)*100:.0f}%准确率" if best.get('accuracy') else "无数据")

            # 显示各窗口
            df = pd.DataFrame(vals)
            if not df.empty:
                df = df.sort_values('window')
                st.dataframe(
                    df[['window', 'accuracy', 'correlation']].rename(columns={
                        'window': '窗口(分钟)',
                        'accuracy': '准确率',
                        'correlation': '相关性'
                    }),
                    hide_index=True
                )


def main():
    state = load_state()

    # 刷新按钮
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 刷新"):
            st.rerun()

    # 显示时间
    st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")

    # 1. 当前情绪快照
    st.subheader("🎯 当前情绪快照")

    snapshots = get_current_sentiment()

    if snapshots:
        # 按样本数排序
        snapshots.sort(key=lambda x: -x['total'])

        # 显示前三
        cols = st.columns(3)
        for i, snap in enumerate(snapshots[:3]):
            with cols[i]:
                display_sentiment_gauge(snap)

        # 完整列表
        with st.expander("查看全部", expanded=False):
            df = pd.DataFrame(snapshots)
            if not df.empty:
                df = df.sort_values('bullish_ratio', ascending=False)
                st.dataframe(
                    df[['asset', 'total', 'bullish', 'bearish', 'bullish_ratio']].rename(columns={
                        'asset': '资产',
                        'total': '样本',
                        'bullish': '看涨',
                        'bearish': '看跌',
                        'bullish_ratio': '看涨比例'
                    }),
                    hide_index=True
                )

        # 情绪分布图
        st.subheader("📊 情绪分布")
        assets = [s['asset'] for s in snapshots]
        bullish_ratios = [s['bullish_ratio'] * 100 for s in snapshots]

        chart_data = pd.DataFrame({
            '资产': assets,
            '看涨比例': bullish_ratios
        })
        st.bar_chart(chart_data.set_index('资产'))

    else:
        st.info("暂无数据")

    # 2. 验证结果
    display_validation_results()

    # 3. 统计信息
    st.subheader("📈 统计信息")
    col1, col2, col3 = st.columns(3)
    col1.metric("情绪记录", len(state.get('records', [])))
    col2.metric("验证次数", len(state.get('validations', [])))
    col3.metric("涉及资产", len(set(v.get('asset') for v in state.get('validations', []))))

    # 4. 建议
    st.subheader("💡 交易建议")
    state = load_state()
    validations = state.get('validations', [])

    if validations:
        by_asset = defaultdict(list)
        for v in validations:
            by_asset[v['asset']].append(v)

        recommendations = []
        for asset, vals in by_asset.items():
            good = [v for v in vals if v.get('accuracy', 0) > 0.5]
            if good:
                best = max(good, key=lambda x: x.get('accuracy', 0))
                recommendations.append({
                    'asset': asset,
                    'window': best.get('window'),
                    'accuracy': best.get('accuracy', 0)
                })

        if recommendations:
            recommendations.sort(key=lambda x: -x['accuracy'])
            for rec in recommendations[:5]:
                st.success(f"**{rec['asset']}**: {rec['window']}分钟窗口, {rec['accuracy']*100:.0f}%准确率")
        else:
            st.warning("暂无高置信度信号")
    else:
        st.info("继续积累数据以获取建议")

    # Auto refresh
    if st.checkbox("自动刷新", value=False):
        time.sleep(30)
        st.rerun()


if __name__ == '__main__':
    main()
