#!/usr/bin/env python3
"""
简易HTTP服务器 + 自动更新看板
"""

import http.server
import socketserver
import json
import os
import time
import feedparser
import re
from collections import defaultdict
from datetime import datetime

PORT = 8501
DATA_FILE = '/Users/januswing/.openclaw/workspace/strategy_miner/sentiment_validator_state.json'

# 情绪关键词
BULLISH_KEYWORDS = ['bullish', 'buy', 'long', 'up', 'higher', 'breakout', 'call', 'support', 'bounce']
BEARISH_KEYWORDS = ['bearish', 'sell', 'short', 'down', 'lower', 'breakdown', 'put', 'resistance']

ASSET_MAPPING = {
    'BTCUSDT': 'BTC', 'BTCUSD': 'BTC', 'BTC': 'BTC',
    'ETHUSDT': 'ETH', 'ETHUSD': 'ETH', 'ETH': 'ETH',
    'XAUUSD': 'XAU', 'XAU': 'XAU', 'GOLD': 'XAU',
}

def analyze_sentiment(text):
    text_lower = text.lower()
    bullish = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
    return 'bullish' if bullish > bearish else ('bearish' if bearish > bullish else 'neutral')

def get_current_sentiment():
    """获取当前情绪"""
    try:
        feed = feedparser.parse('https://www.tradingview.com/feed/')
    except:
        return []

    asset_counts = defaultdict(lambda: {'bullish': 0, 'bearish': 0, 'neutral': 0})
    seen_ids = set()

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
            for r in data.get('records', []):
                seen_ids.add(r['id'])

    for entry in feed.entries:
        idea_id = re.search(r'/([a-zA-Z0-9-]+)/?$', entry.get('link', ''))
        if idea_id and idea_id.group(1) in seen_ids:
            continue

        url = entry.get('link', '')
        asset_match = re.search(r'/chart/([A-Z]+)/', url)
        raw_asset = asset_match.group(1) if asset_match else 'OTHER'
        asset = ASSET_MAPPING.get(raw_asset, raw_asset)

        sentiment = analyze_sentiment(entry.get('title', '') + ' ' + entry.get('summary', ''))
        asset_counts[asset][sentiment] += 1

    snapshots = []
    for asset, counts in asset_counts.items():
        total = sum(counts.values())
        if total > 0:
            snapshots.append({
                'asset': asset,
                'total': total,
                'bullish': counts['bullish'],
                'bearish': counts['bearish'],
                'bullish_ratio': counts['bullish'] / total
            })
    return snapshots

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/sentiment':
            snapshots = get_current_sentiment()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(snapshots).encode())
        elif self.path == '/api/state':
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(f.read().encode())
            else:
                self.send_response(404)
        else:
            self.path = self.path.replace('/Users/januswing/.openclaw/workspace/strategy_miner', '.')
            super().do_GET()

def main():
    print(f"启动看板服务器: http://localhost:{PORT}")
    print("按 Ctrl+C 停止")
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()

if __name__ == '__main__':
    main()
