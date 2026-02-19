#!/usr/bin/env python3
"""TradingView Sentiment Dashboard - Minimal"""
import json, os, http.server, socketserver, webbrowser
from pathlib import Path
from datetime import datetime as dt

PORT = 8700
DATA_FILE = Path(__file__).parent / 'sentiment_validator_state.json'

class ReuseAddr(socketserver.TCPServer):
    allow_reuse_address = True

def make_html(state):
    records = state.get('records', [])
    validations = state.get('validations', [])
    rec_cnt = len(records)
    val_cnt = len(validations)
    assets = set(v.get('asset') for v in validations)
    
    by_asset = {}
    for v in validations:
        a = v.get('asset', 'Unknown')
        if a not in by_asset:
            by_asset[a] = []
        by_asset[a].append(v)
    
    rows = ""
    for a, vals in sorted(by_asset.items()):
        vals.sort(key=lambda x: x.get('window', 0))
        for v in vals:
            acc = v.get('accuracy', 0)
            acc_txt = "%.0f%%" % (acc * 100) if acc else "-"
            corr = v.get('correlation', 0)
            corr_txt = "%.2f" % corr if corr else "-"
            w = str(v.get('window', '?'))
            c = '#00ff88' if acc > 0.5 else '#ff6b6b'
            rows += "<tr><td><strong>%s</strong></td><td>%smin</td><td style='color:%s'>%s</td><td>%s</td></tr>" % (a, w, c, acc_txt, corr_txt)
    
    if not rows:
        rows = "<tr><td colspan='4'>No data yet</td></tr>"
    
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset='UTF-8'>
<meta http-equiv='refresh' content='30'>
<title>Sentiment Dashboard</title>
</head>
<body style='background:#1a1a2e;color:#fff;font-family:sans-serif;margin:0;padding:20px'>
<h1 style='color:#00d4ff'>TradingView Sentiment Dashboard</h1>
<p>Updated: %s</p>
<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0'>
<div style='background:rgba(255,255,255,0.1);padding:20px;text-align:center;border-radius:8px'>
<div style='font-size:32px;color:#00d4ff'>%d</div><div>Records</div></div>
<div style='background:rgba(255,255,255,0.1);padding:20px;text-align:center;border-radius:8px'>
<div style='font-size:32px;color:#00d4ff'>%d</div><div>Validations</div></div>
<div style='background:rgba(255,255,255,0.1);padding:20px;text-align:center;border-radius:8px'>
<div style='font-size:32px;color:#00d4ff'>%d</div><div>Assets</div></div>
</div>
<h2>Validation Results</h2>
<table style='width:100%%25;border-collapse:collapse;background:rgba(255,255,255,0.05);border-radius:8px'>
<tr><th style='padding:10px;text-align:left;border-bottom:1px solid #333;background:rgba(0,212,255,0.2)'>Asset</th>
<th style='padding:10px;text-align:left;border-bottom:1px solid #333'>Window</th>
<th style='padding:10px;text-align:left;border-bottom:1px solid #333'>Accuracy</th>
<th style='padding:10px;text-align:left;border-bottom:1px solid #333'>Correlation</th></tr>
%s</table>
<p><em>Auto-refresh every 30 seconds</em></p>
</body>
</html>""" % (dt.now().strftime('%H:%M:%S'), rec_cnt, val_cnt, len(assets), rows)
    return html

class D(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/index.html']:
            state = {}
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    state = json.load(f)
            html = make_html(state)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())

print("=" * 50)
print("TradingView Sentiment Dashboard")
print("Browser: http://localhost:%d" % PORT)
print("=" * 50)
webbrowser.open('http://localhost:%d' % PORT)
with ReuseAddr(("", PORT), D) as httpd:
    httpd.serve_forever()
