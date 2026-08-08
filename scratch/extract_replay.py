import json
import sys
import os

def analyze(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    steps = data.get('steps', [])
    print(f"Loaded {len(steps)} steps.")
    
    # We want to track Player 0 and Player 1
    p0_history = []
    p1_history = []
    market_history = []
    
    for i, step in enumerate(steps):
        if not step or len(step) < 2:
            continue
        p0 = step[0]
        p1 = step[1]
        
        obs0 = p0.get('observation', {})
        if 'farms' not in obs0:
            continue
            
        farm0 = obs0['farms'][0]
        farm1 = obs0['farms'][1]
        market = obs0.get('market', {})
        
        p0_history.append((i, farm0, p0.get('reward', 0), p0.get('action', {})))
        p1_history.append((i, farm1, p1.get('reward', 0), p1.get('action', {})))
        market_history.append(market)

    def extract_stats(history):
        stats = []
        for step, farm, reward, action in history:
            money = farm.get('money', 0)
            hands = len(farm.get('hands', []))
            shed = farm.get('shed', {})
            seeds = farm.get('seeds', {})
            animals = farm.get('animals', [])
            
            # Count tiles
            tiles = farm.get('tiles', [])
            weeds = 0
            plants = 0
            empty = 0
            locked = 0
            for row in tiles:
                for t in row:
                    if isinstance(t, dict):
                        k = t.get('kind')
                        if k == 'WEED': weeds += 1
                        elif k == 'PLANT': plants += 1
                        elif k == 'LOCKED': locked += 1
                        elif k == 'EMPTY': empty += 1
            
            total_land = empty + plants + weeds
            stats.append({
                'step': step,
                'money': money,
                'hands': hands,
                'shed': shed,
                'seeds': seeds,
                'animals': animals,
                'plants': plants,
                'weeds': weeds,
                'total_land': total_land,
                'action': action
            })
        return stats

    s0 = extract_stats(p0_history)
    s1 = extract_stats(p1_history)
    
    print(f"P0 Final Money: {s0[-1]['money']}, Hands: {s0[-1]['hands']}")
    print(f"P1 Final Money: {s1[-1]['money']}, Hands: {s1[-1]['hands']}")
    
    # Find critical divergence
    for i in range(len(s0)):
        if abs(s0[i]['money'] - s1[i]['money']) > 500:
            print(f"Critical divergence around step {s0[i]['step']}: P0=${s0[i]['money']} vs P1=${s1[i]['money']}")
            break

    # Dump a detailed summary for P1 (the opponent who scored 151k)
    with open('p1_analysis.json', 'w') as f:
        json.dump(s1, f, indent=2)
        
    with open('market_analysis.json', 'w') as f:
        json.dump(market_history, f, indent=2)
        
    print("Analysis saved to p1_analysis.json and market_analysis.json")

if __name__ == '__main__':
    analyze('/home/crow/Desktop/first_battle.json')
