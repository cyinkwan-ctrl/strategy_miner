import json

d = json.load(open('strategies.json'))
p = [s for s in d['strategies'] if s['status'] == 'pending']
i = [s for s in d['strategies'] if s['status'] == 'invalid']

print('='*60)
print('📊 Strategy Miner 当前状态')
print('='*60)
print('待验证策略:', len(p))
print('无效(需重新验证):', len(i))
print('总计:', len(d['strategies']))
print()
print('待验证策略:')
for s in p:
    print('  -', s['title'][:50])
    print('    来源:', s['source'], '|', s['author'])
print('='*60)
