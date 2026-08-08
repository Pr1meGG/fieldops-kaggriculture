import json
import statistics

with open('/home/crow/Desktop/first_battle.json', 'r') as f:
    data = json.load(f)

steps = data.get('steps', [])

timeline = []
for day in range(30):
    start_step = day * 24
    end_step = min((day + 1) * 24, len(steps))
    
    cash_start = 0
    cash_end = 0
    hires = 0
    hire_cost = 0
    land_purchases = 0
    seeds_purchased = 0
    animals_purchased = 0
    sales = 0
    units_sold = {}
    revenue = 0
    
    crops_planted = 0
    crops_harvested = 0
    fertilizer_used = 0
    
    if start_step < len(steps):
        obs = steps[start_step][1].get('observation', {})
        if 'farms' in obs:
            cash_start = obs['farms'][1].get('money', 0)
            
    if end_step - 1 < len(steps):
        obs = steps[end_step - 1][1].get('observation', {})
        if 'farms' in obs:
            cash_end = obs['farms'][1].get('money', 0)
            
    for i in range(start_step, end_step):
        p1 = steps[i][1]
        act = p1.get('action', {})
        market_acts = act.get('market', [])
        
        for ma in market_acts:
            if not isinstance(ma, list): continue
            cmd = ma[0]
            if cmd == 'HIRE':
                hires += 1
            elif cmd == 'BUY_LAND':
                land_purchases += 1
            elif cmd == 'BUY_SEED':
                seeds_purchased += ma[2] if len(ma)>2 else 1
            elif cmd == 'BUY_ANIMAL':
                animals_purchased += 1
            elif cmd == 'SELL':
                sales += 1
                if len(ma) > 2:
                    item = ma[1]
                    count = ma[2]
                    units_sold[item] = units_sold.get(item, 0) + count
                    
        # check worker acts for PLANT, HARVEST, FERTILIZE
        worker_acts = act.get('hands', [])
        farmer_act = act.get('farmer', [])
        all_w = [farmer_act] + worker_acts
        for wa in all_w:
            if not isinstance(wa, list): continue
            cmd = wa[0]
            if cmd == 'PLANT': crops_planted += 1
            elif cmd == 'HARVEST': crops_harvested += 1
            elif cmd == 'FERTILIZE': fertilizer_used += 1

    timeline.append({
        'day': day,
        'cash_start': cash_start,
        'cash_end': cash_end,
        'hires': hires,
        'land_purchases': land_purchases,
        'animals_purchased': animals_purchased,
        'seeds_purchased': seeds_purchased,
        'crops_planted': crops_planted,
        'crops_harvested': crops_harvested,
        'sales': sales,
        'units_sold': units_sold
    })

with open('timeline.md', 'w') as f:
    f.write("# P1 Day-by-Day Timeline\n")
    for t in timeline:
        f.write(f"## Day {t['day']}\n")
        f.write(f"Cash: ${t['cash_start']} -> ${t['cash_end']}\n")
        f.write(f"Hires: {t['hires']}, Land: {t['land_purchases']}, Animals: {t['animals_purchased']}, Seeds: {t['seeds_purchased']}\n")
        f.write(f"Planted: {t['crops_planted']}, Harvested: {t['crops_harvested']}\n")
        f.write(f"Sales: {t['sales']}, Units Sold: {t['units_sold']}\n\n")

print("Timeline written to timeline.md")
