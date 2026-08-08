import os
import sys
import json
import statistics
import time
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath('src'))
from kaggle_environments import make

from fieldops.experimental.reconstruction_agent import agent_factory

def evaluate_ablation(name: str, config: Dict[str, bool], seeds: List[int]) -> Dict[str, Any]:
    rewards = []
    metrics = {
        'max_cash': [],
        'min_cash': [],
        'workers': [],
        'hires': [],
        'land': [],
        'movement_actions': [],
        'productive_actions': [],
        'pass_actions': [],
        'wheat': [],
        'melon': [],
        'strawberry': [],
        'livestock': [],
        'milk': [],
        'wool': [],
        'fertilizer': []
    }
    
    for seed in seeds:
        env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
        trainer = env.train([None, "random"])
        
        agent = agent_factory(config)
        
        obs = trainer.reset()
        done = False
        
        # Local trackers for the episode
        max_c = float('-inf')
        min_c = float('inf')
        hires = 0
        movement = 0
        productive = 0
        passes = 0
        
        while not env.done:
            # We don't have done from step, kaggle environments is env.done
            # also, we should ensure the observation is dict
            obs_dict = obs
            if not isinstance(obs, dict): 
                # If using kaggle_environments, it wraps obs in a struct
                obs_dict = obs.__dict__ if hasattr(obs, '__dict__') else obs
                
            if 'step' not in obs_dict:
                obs_dict = {'step': env.steps[-1][0].observation.step, 'farms': env.steps[-1][0].observation.farms}
                
            # Actually with trainer, obs is the observation
            try:
                action = agent(obs)
            except ValueError as e:
                if 'out of range' in str(e):
                    break
                raise e
            
            # Record some action stats
            for ma in action.get('market', []):
                if isinstance(ma, list) and ma[0] == 'HIRE':
                    hires += 1
                    
            for w_act in action.get('hands', []) + [action.get('farmer', ['PASS'])]:
                if not isinstance(w_act, list) or not w_act:
                    w_act = ['PASS']
                cmd = w_act[0]
                if cmd in ['N', 'S', 'E', 'W']:
                    movement += 1
                elif cmd == 'PASS':
                    passes += 1
                else:
                    productive += 1
                    
            obs, reward, done, info = trainer.step(action)
            
            # kaggle trainer steps return obs, reward, done, info
            if hasattr(obs, 'farms'):
                farm = obs.farms[0]
            else:
                farm = obs['farms'][0]
                
            cash = farm.get('money', 0) if isinstance(farm, dict) else farm.money
            max_c = max(max_c, cash)
            min_c = min(min_c, cash)
            
        final_cash = obs['farms'][0].get('money', 0) if isinstance(obs['farms'][0], dict) else obs['farms'][0].money
        rewards.append(final_cash)
        metrics['max_cash'].append(max_c)
        metrics['min_cash'].append(min_c)
        metrics['hires'].append(hires)
        metrics['movement_actions'].append(movement)
        metrics['productive_actions'].append(productive)
        metrics['pass_actions'].append(passes)
        
        if hasattr(obs, 'farms'):
            farm = obs.farms[0]
        else:
            farm = obs['farms'][0]
        metrics['workers'].append(len(farm.get('hands', [])) if isinstance(farm, dict) else len(farm.hands))
        metrics['land'].append((len(farm.get('tiles', [])) // 4) if isinstance(farm, dict) else (len(farm.tiles) // 4))
        
    return {
        'name': name,
        'config': config,
        'rewards': rewards,
        'mean_reward': statistics.mean(rewards),
        'median_reward': statistics.median(rewards),
        'min_reward': min(rewards),
        'max_reward': max(rewards),
        'metrics': {k: statistics.mean(v) if v else 0.0 for k, v in metrics.items()}
    }

def main():
    SEEDS = [42, 43, 44, 45, 46]
    
    print("Running Ablation A (Control)...")
    res_A = evaluate_ablation("A_Control", {}, SEEDS)
    
    print("Running Ablation B (Aggressive Reinvestment)...")
    res_B = evaluate_ablation("B_Reinvest", {"AGGRESSIVE_REINVESTMENT": True}, SEEDS)
    
    print("Running Ablation C (Dynamic Workforce)...")
    res_C = evaluate_ablation("C_Workforce", {"AGGRESSIVE_REINVESTMENT": True, "DYNAMIC_WORKERS": True}, SEEDS)
    
    print("Running Ablation D (Dynamic Land)...")
    res_D = evaluate_ablation("D_Land", {"AGGRESSIVE_REINVESTMENT": True, "DYNAMIC_WORKERS": True, "DYNAMIC_LAND": True}, SEEDS)
    
    report = f"""# Ablation Results (Batch 2)

## Experiment A: Control (Baseline 2-Worker/12-Melon)
* **Mean Reward:** ${res_A['mean_reward']:.2f}
* **Max Cash:** ${res_A['metrics']['max_cash']:.2f} | **Min Cash:** ${res_A['metrics']['min_cash']:.2f}
* **Hires:** {res_A['metrics']['hires']:.1f} | **Workers:** {res_A['metrics']['workers']:.1f}
* **Land:** {res_A['metrics']['land']:.1f}
* **Productive / Movement / Pass:** {res_A['metrics']['productive_actions']:.1f} / {res_A['metrics']['movement_actions']:.1f} / {res_A['metrics']['pass_actions']:.1f}

## Experiment B: Aggressive Reinvestment (Capacity Maxing)
* **Mean Reward:** ${res_B['mean_reward']:.2f} (Delta: ${res_B['mean_reward'] - res_A['mean_reward']:.2f})
* **Max Cash:** ${res_B['metrics']['max_cash']:.2f} | **Min Cash:** ${res_B['metrics']['min_cash']:.2f}
* **Hires:** {res_B['metrics']['hires']:.1f} | **Workers:** {res_B['metrics']['workers']:.1f}
* **Land:** {res_B['metrics']['land']:.1f}
* **Productive / Movement / Pass:** {res_B['metrics']['productive_actions']:.1f} / {res_B['metrics']['movement_actions']:.1f} / {res_B['metrics']['pass_actions']:.1f}

## Experiment C: B + Dynamic Workforce
* **Mean Reward:** ${res_C['mean_reward']:.2f} (Delta: ${res_C['mean_reward'] - res_A['mean_reward']:.2f})
* **Max Cash:** ${res_C['metrics']['max_cash']:.2f} | **Min Cash:** ${res_C['metrics']['min_cash']:.2f}
* **Hires:** {res_C['metrics']['hires']:.1f} | **Workers:** {res_C['metrics']['workers']:.1f}
* **Land:** {res_C['metrics']['land']:.1f}
* **Productive / Movement / Pass:** {res_C['metrics']['productive_actions']:.1f} / {res_C['metrics']['movement_actions']:.1f} / {res_C['metrics']['pass_actions']:.1f}

## Experiment D: C + Dynamic Land
* **Mean Reward:** ${res_D['mean_reward']:.2f} (Delta: ${res_D['mean_reward'] - res_A['mean_reward']:.2f})
* **Max Cash:** ${res_D['metrics']['max_cash']:.2f} | **Min Cash:** ${res_D['metrics']['min_cash']:.2f}
* **Hires:** {res_D['metrics']['hires']:.1f} | **Workers:** {res_D['metrics']['workers']:.1f}
* **Land:** {res_D['metrics']['land']:.1f}
* **Productive / Movement / Pass:** {res_D['metrics']['productive_actions']:.1f} / {res_D['metrics']['movement_actions']:.1f} / {res_D['metrics']['pass_actions']:.1f}

"""

    with open('opponent_reconstruction_batch2.md', 'w') as f:
        f.write(report)
        
    print(f"Results saved to opponent_reconstruction_batch2.md")

if __name__ == '__main__':
    main()
