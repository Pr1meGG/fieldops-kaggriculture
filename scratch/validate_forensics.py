import json

def validate():
    with open('p1_analysis.json', 'r') as f:
        steps = json.load(f)
    
    val = {
        'liquidation': [],
        'hires': [],
        'capital': {'min_cash': float('inf'), 'min_cash_step': -1, 'trajectory': []},
        'production': {},
        'livestock': {'purchases': [], 'milk_harvests': 0, 'wool_harvests': 0}
    }
    
    for i, step_data in enumerate(steps):
        cash = step_data.get('money', 0)
        hands = step_data.get('hands', 0)
        
        # Capital
        if cash < val['capital']['min_cash']:
            val['capital']['min_cash'] = cash
            val['capital']['min_cash_step'] = i
            
        if i % 24 == 0:
            val['capital']['trajectory'].append({'day': i // 24, 'cash': cash})
            
        act = step_data.get('action', {})
        market_acts = act.get('market', [])
        
        for ma in market_acts:
            if not isinstance(ma, list): continue
            cmd = ma[0]
            if cmd == 'SELL':
                if i < 24 and ma[1] == 'WHEAT':
                    val['liquidation'].append({
                        'step': i,
                        'item': ma[1],
                        'qty': ma[2] if len(ma) > 2 else 1,
                        'cash_before': cash
                    })
                # Production sales
                item = ma[1]
                qty = ma[2] if len(ma) > 2 else 1
                if item not in val['production']:
                    val['production'][item] = {'first_sale': i, 'total_sold': 0, 'sales': 0}
                val['production'][item]['total_sold'] += qty
                val['production'][item]['sales'] += 1
                val['production'][item]['last_sale'] = i
            
            elif cmd == 'HIRE':
                val['hires'].append({
                    'step': i,
                    'day': i // 24,
                    'cash_before': cash,
                    'hands_before': hands
                })
            
            elif cmd == 'BUY_ANIMAL':
                typ = ma[1] if len(ma) > 1 else 'UNKNOWN'
                val['livestock']['purchases'].append({
                    'step': i,
                    'day': i // 24,
                    'type': typ
                })

    for liq in val['liquidation']:
        step_idx = liq['step']
        if step_idx + 1 < len(steps):
            next_cash = steps[step_idx + 1]['money']
            liq['cash_after'] = next_cash
            liq['price_received'] = next_cash - liq['cash_before']

    for h in val['hires']:
        step_idx = h['step']
        if step_idx + 1 < len(steps):
            next_cash = steps[step_idx + 1]['money']
            next_hands = steps[step_idx + 1]['hands']
            h['cash_after'] = next_cash
            h['hands_after'] = next_hands

    print("Liquidation:", val['liquidation'])
    print("Min Cash:", val['capital']['min_cash'], "at step", val['capital']['min_cash_step'])
    print("Hires count:", len(val['hires']))
    print("Production:", val['production'])
    print("Livestock:", val['livestock'])

if __name__ == '__main__':
    validate()
