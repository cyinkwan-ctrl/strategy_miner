
<!DOCTYPE html>
<html>
<head>
<meta charset='UTF-8'>
<meta http-equiv='refresh' content='30'>
<title>TradingView Sentiment Dashboard</title>
<style>
*{box-sizing:border-box}
body{font-family:sans-serif;background:#1a1a2e;color:#fff;margin:0;padding:20px}
h1{color:#00d4ff}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0}
.stat{background:rgba(255,255,255,0.1);padding:20px;text-align:center;border-radius:8px}
.stat-val{font-size:32px;color:#00d4ff}
table{width:100%;border-collapse:collapse;background:rgba(255,255,255,0.05);border-radius:8px}
th,td{padding:10px;text-align:left;border-bottom:1px solid #333}
th{background:rgba(0,212,255,0.2)}
</style>
</head>
<body>
<h1>TradingView Sentiment Dashboard</h1>
<p>更新时间: TIMEPLACEHOLDER</p>
<div class='stats'>
<div class='stat'><div class='stat-val'>RECORDSPLACEHOLDER</div><div>情绪记录</div></div>
<div class='stat'><div class='stat-val'>VALIDATIONSPLACEHOLDER</div><div>验证次数</div></div>
<div class='stat'><div class='stat-val'>ASSETSPLACEHOLDER</div><div>涉及资产</div></div>
</div>
<h2>验证结果</h2>
<table><tr><th>资产</th><th>窗口</th><th>准确率</th><th>相关性</th></tr>
ROWSPLACEHOLDER
</table>
<p><em>每30秒自动刷新</em></p>
</body>
</html>
