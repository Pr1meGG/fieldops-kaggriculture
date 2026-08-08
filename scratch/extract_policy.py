import json
import statistics
import math

def extract_forensics(filepath, p_idx=1):
    with open(filepath, 'r') as f:
        data = json.load(f)

    steps = data.get('steps', [])
    
    # We will track daily aggregates
    days = []
    
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
        sales = []
        units_sold = {}
        crops_planted = 0
        crops_harvested = 0
        fertilizer_used = 0
        min_cash = float('inf')
        max_cash = float('-inf')
        worker_count_start = 0
        worker_count_end = 0
        land_owned_start = 0
        land_owned_end = 0
        
        if start_step < len(steps):
            obs = steps[start_step][1].get('observation', {})
            if 'farms' in obs:
                farm = obs['farms'][p_idx]
                cash_start = farm.get('money', 0)
                worker_count_start = len(farm.get('hands', []))
                land_owned_start = len(farm.get('tiles', [])) // 4  # Quadrants approx
                min_cash = min(min_cash, cash_start)
                max_cash = max(max_cash, cash_start)

        for i in range(start_step, end_step):
            p = steps[i][p_idx]
            obs = p.get('observation', {})
            
            if 'farms' in obs:
                farm = obs['farms'][p_idx]
                c = farm.get('money', 0)
                min_cash = min(min_cash, c)
                max_cash = max(max_cash, c)
                worker_count_end = len(farm.get('hands', []))
                land_owned_end = len(farm.get('tiles', [])) // 4
                
            act = p.get('action', {})
            market_acts = act.get('market', [])
            for ma in market_acts:
                if not isinstance(ma, list): continue
                cmd = ma[0]
                if cmd == 'HIRE':
                    hires += 1
                elif cmd == 'BUY_LAND':
                    land_purchases += 1
                elif cmd == 'BUY_SEED':
                    seeds_purchased += ma[2] if len(ma) > 2 else 1
                elif cmd == 'BUY_ANIMAL':
                    animals_purchased += 1
                elif cmd == 'SELL':
                    if len(ma) > 2:
                        item = ma[1]
                        count = ma[2]
                        units_sold[item] = units_sold.get(item, 0) + count
                        sales.append({"item": item, "count": count, "step": i})
                        
            all_w = [act.get('farmer', [])] + act.get('hands', [])
            for wa in all_w:
                if not isinstance(wa, list): continue
                if len(wa) == 0: continue
                cmd = wa[0]
                if cmd == 'PLANT': crops_planted += 1
                elif cmd == 'HARVEST': crops_harvested += 1
                elif cmd == 'FERTILIZE': fertilizer_used += 1

        if end_step - 1 < len(steps):
            obs = steps[end_step - 1][1].get('observation', {})
            if 'farms' in obs:
                cash_end = obs['farms'][p_idx].get('money', 0)

        days.append({
            'day': day,
            'cash_start': cash_start,
            'cash_end': cash_end,
            'min_cash': min_cash,
            'max_cash': max_cash,
            'worker_count': worker_count_end,
            'hires': hires,
            'land_owned': land_owned_end,
            'land_purchases': land_purchases,
            'animals_purchased': animals_purchased,
            'seeds_purchased': seeds_purchased,
            'crops_planted': crops_planted,
            'crops_harvested': crops_harvested,
            'sales': sales,
            'units_sold': units_sold
        })
        
    return days

def generate_policy(days):
    policy = {
        "starting_liquidation": {
            "observed": False,
            "details": {}
        },
        "capital_policy": {
            "minimum_observed_cash": 0,
            "maximum_observed_cash": 0,
            "reinvestment_style": ""
        },
        "workforce_scaling": {
            "hiring_events": []
        },
        "land_expansion": {
            "purchase_events": []
        },
        "production_mix": {
            "early_game": [],
            "mid_game": [],
            "late_game": []
        },
        "timeline_summary": {
            "DAY_0": {},
            "DAYS_1_5": {},
            "DAYS_6_10": {},
            "DAYS_11_20": {},
            "DAYS_21_29": {}
        }
    }
    
    # 1. Starting Liquidation
    day0 = days[0]
    if day0['units_sold'].get('WHEAT', 0) > 100:
        policy["starting_liquidation"]["observed"] = True
        policy["starting_liquidation"]["details"] = {
            "units_sold": day0['units_sold']['WHEAT']
        }
        
    # 2. Capital Policy
    min_cash = min([d['min_cash'] for d in days])
    max_cash = max([d['max_cash'] for d in days])
    policy["capital_policy"]["minimum_observed_cash"] = min_cash
    policy["capital_policy"]["maximum_observed_cash"] = max_cash
    if min_cash < 100:
        policy["capital_policy"]["reinvestment_style"] = "Aggressive (cash drops near 0)"
    else:
        policy["capital_policy"]["reinvestment_style"] = "Reserve-based"
        
    # 3. Workforce Scaling
    for d in days:
        if d['hires'] > 0:
            policy["workforce_scaling"]["hiring_events"].append({
                "day": d['day'],
                "hires": d['hires'],
                "workers_after": d['worker_count']
            })
            
    # 4. Land Expansion
    for d in days:
        if d['land_purchases'] > 0:
            policy["land_expansion"]["purchase_events"].append({
                "day": d['day'],
                "purchases": d['land_purchases'],
                "land_after": d['land_owned']
            })
            
    # 5. Production Mix
    early = set()
    for d in days[1:10]:
        early.update(d['units_sold'].keys())
    mid = set()
    for d in days[10:20]:
        mid.update(d['units_sold'].keys())
    late = set()
    for d in days[20:30]:
        late.update(d['units_sold'].keys())
        
    policy["production_mix"]["early_game"] = list(early)
    policy["production_mix"]["mid_game"] = list(mid)
    policy["production_mix"]["late_game"] = list(late)
    
    # 6. Timeline summary
    def sum_metric(start, end, key):
        if isinstance(days[start][key], dict):
            res = {}
            for i in range(start, end):
                for k, v in days[i][key].items():
                    res[k] = res.get(k, 0) + v
            return res
        return sum([days[i][key] for i in range(start, end)])
        
    policy["timeline_summary"]["DAY_0"] = {
        "hires": day0['hires'],
        "cash_end": day0['cash_end']
    }
    policy["timeline_summary"]["DAYS_1_5"] = {
        "hires": sum_metric(1, 6, 'hires'),
        "land_purchases": sum_metric(1, 6, 'land_purchases'),
        "units_sold": sum_metric(1, 6, 'units_sold')
    }
    policy["timeline_summary"]["DAYS_6_10"] = {
        "hires": sum_metric(6, 11, 'hires'),
        "land_purchases": sum_metric(6, 11, 'land_purchases'),
        "animals_purchased": sum_metric(6, 11, 'animals_purchased'),
        "units_sold": sum_metric(6, 11, 'units_sold')
    }
    policy["timeline_summary"]["DAYS_11_20"] = {
        "hires": sum_metric(11, 21, 'hires'),
        "land_purchases": sum_metric(11, 21, 'land_purchases'),
        "units_sold": sum_metric(11, 21, 'units_sold')
    }
    policy["timeline_summary"]["DAYS_21_29"] = {
        "hires": sum_metric(21, 30, 'hires'),
        "land_purchases": sum_metric(21, 30, 'land_purchases'),
        "units_sold": sum_metric(21, 30, 'units_sold'),
        "cash_end": days[-1]['cash_end']
    }

    with open('opponent_policy.json', 'w') as f:
        json.dump(policy, f, indent=2)
        
    print("opponent_policy.json generated successfully.")

if __name__ == '__main__':
    days = extract_forensics('/home/crow/Desktop/first_battle.json')
    generate_policy(days)
