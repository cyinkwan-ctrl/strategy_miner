#!/usr/bin/env python3
import http.server, socketserver, json, os, webbrowser
from datetime import datetime
PORT=8600

class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/index.html']:
            with open('dashboard.py', 'r') as f:
                html = f.read()
            
            state = json.load(open('sentiment_validator_state.json'))
            rec = len(state.get('records', []))
            val = len(state.get('validations', []))
            assets = len(set(v.get('asset') for v in state.get('validations', [])))
            
            rows = ''
            by_asset = {}
            for v in state.get('validations', []):
                a = v.get('asset', 'Unknown')
                if a not in by_asset:
                    by_asset[a] = []
                by_asset[a].append(v)
            
            for a, vals in sorted(by_asset.items()):
                for v in vals:
                    acc = v.get('accuracy', 0)
                    acc_pct = '%.0f%%' % (acc * 100) if acc else '-'
                    corr = v.get('correlation', 0)
                    corr_str = '%.2f' % corr if corr else '-'
                    w = str(v.get('window', '?'))
                    c = '#00ff88' if acc > 0.5 else '#ff6b6b'
                    rows += '<tr><td><strong>%s</strong></td><td>%smin</td><td style="color:%s">%s</td><td>%s</td></tr>' % (a, w, c, acc_pct, corr_str)
            
            if not rows:
                rows = '<tr><td colspan="4">Waiting for data...</td></tr>'
            
            html = html.replace('TIMEPLACEHOLDER', datetime.now().strftime('%H:%M:%S'))
            html = html.replace('RECORDSPLACEHOLDER', str(rec))
            html = html.replace('VALIDATIONSPLACEHOLDER', str(val))
            html = html.replace('ASSETSPLACEHOLDER', str(assets))
            html = html.replace('ROWSPLACEHOLDER', rows)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_response(404)

class ReuseAddr(socketserver.TCPServer):
    allow_reuse_address = True

PORT = 8800

with ReuseAddr(('', PORT), H) as httpd:
    print('Dashboard: http://localhost:%d' % PORT)
    webbrowser.open('http://localhost:%d' % PORT)
    httpd.serve_forever()
