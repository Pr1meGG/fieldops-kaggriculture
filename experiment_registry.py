import csv
import os
import datetime
from dataclasses import dataclass
from typing import List, Optional

CSV_FILE = "experiments.csv"
MD_FILE = "experiments.md"
HYPOTHESIS_FILE = "top_hypotheses.md"

@dataclass
class ExperimentResult:
    experiment_id: str
    category: str
    branch: str
    champion_version: str
    date: str
    independent_variable: str
    parameter_values: str
    sample_size: int
    benchmark_seeds: str
    mean_reward: float
    median_reward: float
    std_dev: float
    win_rate: float
    p_value: Optional[float]
    effect_size: Optional[float]
    economic_attribution: str
    decision: str
    git_commit: str
    git_tag: str

class ExperimentRegistry:
    def __init__(self, csv_path=CSV_FILE, md_path=MD_FILE, hyp_path=HYPOTHESIS_FILE):
        self.csv_path = csv_path
        self.md_path = md_path
        self.hyp_path = hyp_path
        self._ensure_csv_headers()
        
    def _ensure_csv_headers(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Experiment ID", "Category", "Branch", "Champion Version", "Date", 
                    "Independent Variable", "Parameter Values", "Sample Size", 
                    "Benchmark Seeds", "Mean Reward", "Median Reward", "Std Dev", 
                    "Win Rate", "p-value", "Effect Size", "Economic Attribution", 
                    "Decision", "Git Commit", "Git Tag"
                ])

    def log_experiment(self, result: ExperimentResult):
        # 1. Update CSV
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                result.experiment_id, result.category, result.branch, result.champion_version, result.date,
                result.independent_variable, result.parameter_values, result.sample_size,
                result.benchmark_seeds, f"{result.mean_reward:.2f}", f"{result.median_reward:.2f}", 
                f"{result.std_dev:.2f}", f"{result.win_rate:.4f}", 
                f"{result.p_value:.6f}" if result.p_value is not None else "N/A", 
                f"{result.effect_size:.4f}" if result.effect_size is not None else "N/A", 
                result.economic_attribution, result.decision, result.git_commit, result.git_tag
            ])
            
        # 2. Update MD
        self._regenerate_markdown()

    def _regenerate_markdown(self):
        with open(self.csv_path, 'r') as f:
            reader = csv.DictReader(f)
            experiments = list(reader)
            
        with open(self.md_path, 'w') as f:
            f.write("# Operations Research Experiment Registry\n\n")
            f.write("A chronological record of all rigorously validated economic hypotheses.\n\n")
            
            # --- Category Statistics ---
            stats = defaultdict(lambda: {"total": 0, "promoted": 0, "ev_sum": 0, "ev_count": 0})
            for exp in experiments:
                cat = exp["Category"]
                stats[cat]["total"] += 1
                if exp["Decision"] == "PROMOTE":
                    stats[cat]["promoted"] += 1
                    try:
                        # Simple extraction for EV from attribution (e.g. "+$5,060")
                        import re
                        match = re.search(r'\+\$([0-9,]+)', exp["Economic Attribution"])
                        if match:
                            stats[cat]["ev_sum"] += int(match.group(1).replace(",", ""))
                            stats[cat]["ev_count"] += 1
                    except Exception:
                        pass
                        
            f.write("## Cumulative Statistics\n")
            for cat, c_stats in sorted(stats.items()):
                f.write(f"### {cat}s\n")
                f.write(f"- **Experiments**: {c_stats['total']}\n")
                f.write(f"- **Promoted**: {c_stats['promoted']}\n")
                avg_ev = c_stats["ev_sum"] / max(1, c_stats["ev_count"])
                f.write(f"- **Average EV**: +${avg_ev:.0f}\n\n")
                
            f.write("---\n\n")
            
            for exp in reversed(experiments):
                f.write(f"## {exp['Experiment ID']} [{exp['Category']}] - {exp['Independent Variable']}\n")
                f.write(f"**Date**: {exp['Date']} | **Champion**: {exp['Champion Version']} | **Decision**: {exp['Decision']}\n\n")
                
                f.write("### Benchmark Details\n")
                f.write(f"- **Parameter Values Tested**: {exp['Parameter Values']}\n")
                f.write(f"- **Sample Size**: {exp['Sample Size']} (Seeds: {exp['Benchmark Seeds']})\n")
                f.write(f"- **Mean Reward**: ${float(exp['Mean Reward']):.2f}\n")
                f.write(f"- **Win Rate**: {float(exp['Win Rate'])*100:.2f}%\n")
                if exp['p-value'] != "N/A":
                    f.write(f"- **p-value**: {exp['p-value']}\n")
                
                f.write("\n### Economic Attribution\n")
                f.write(f"{exp['Economic Attribution']}\n\n")
                
                f.write("### Repository State\n")
                f.write(f"- **Branch**: {exp['Branch']}\n")
                f.write(f"- **Commit**: `{exp['Git Commit']}`\n")
                f.write(f"- **Tag**: `{exp['Git Tag']}`\n\n")
                f.write("---\n\n")

    def update_top_hypotheses(self, hypotheses: List[dict]):
        with open(self.hyp_path, 'w') as f:
            f.write("# Next Candidate\n\n")
            for i, hyp in enumerate(hypotheses, 1):
                f.write(f"{i}. {hyp['name']}\n")
                f.write(f"EV: {hyp['ev']}\n")
                f.write(f"Confidence: {hyp['confidence']}\n")
                if 'complexity' in hyp:
                    f.write(f"Engineering Complexity: {hyp['complexity']}\n")
                if 'time' in hyp:
                    f.write(f"Estimated Time: {hyp['time']}\n")
                f.write("\n")

from collections import defaultdict

if __name__ == "__main__":
    import shutil
    if os.path.exists(CSV_FILE):
        os.remove(CSV_FILE) # Reset to rewrite with new headers
        
    registry = ExperimentRegistry()
    
    # Pre-populate with our known history
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-001",
        category="Parameter",
        branch="feature/production-audit",
        champion_version="v1-baseline",
        date="2026-08-06",
        independent_variable="Worker Density (Tiles per Worker)",
        parameter_values="8, 10, 12, 14, 16, 20",
        sample_size=100,
        benchmark_seeds="Random 0-99",
        mean_reward=46685.25,
        median_reward=46312.00,
        std_dev=3800.00,
        win_rate=0.97,
        p_value=0.0000001,
        effect_size=1.35,
        economic_attribution="+$5,060 from dynamic labor scaling preventing early capital starvation. Lower worker counts in early game preserved cash for rapid land expansion, while scaling up later allowed full utilization of newly acquired quadrants without bottlenecking on movement or water limits.",
        decision="PROMOTE",
        git_commit="8636aaf",
        git_tag="champion-worker-density-v2"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-002",
        category="Policy",
        branch="feature/production-audit",
        champion_version="champion-worker-density-v2",
        date="2026-08-07",
        independent_variable="Expansion Utilization Threshold",
        parameter_values="60%, 70%, 80%, 90%, 100%",
        sample_size=40,
        benchmark_seeds="Random 200-239",
        mean_reward=29415.22,
        median_reward=29000.00,
        std_dev=1200.00,
        win_rate=0.00,
        p_value=None,
        effect_size=None,
        economic_attribution="-$17,270 collapse across all thresholds due to systemic Expansion-Labor Deadlock. The solitary farmer could never physically achieve the 60%+ utilization required to trigger Quadrant 2 purchase. Because Quadrant 2 was never purchased, the Worker Density logic never hired additional labor. The farm permanently starved for labor while waiting for utilization that required labor to achieve.",
        decision="REJECT",
        git_commit="N/A",
        git_tag="N/A"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-003",
        category="Policy",
        branch="feature/production-audit",
        champion_version="champion-worker-density-v2",
        date="2026-08-07",
        independent_variable="Crop Portfolio Ratio",
        parameter_values="Wheat vs Melon combinations (Static/Dynamic)",
        sample_size=40,
        benchmark_seeds="Random 300-339",
        mean_reward=39154.55,
        median_reward=39000.00,
        std_dev=3000.00,
        win_rate=0.00,
        p_value=None,
        effect_size=None,
        economic_attribution="All Wheat portfolios collapsed by up to -$40,000. The mathematical ROI model identified Wheat as a Capital compounder, but the game starts with $3,000, meaning the farm is instantly Labor-starved. Every action spent planting Wheat ($15 profit/action) instead of Melon ($101 profit/action) destroys massive opportunity cost.",
        decision="REJECT",
        git_commit="N/A",
        git_tag="N/A"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-004",
        category="Bug Fix",
        branch="feature/production-audit",
        champion_version="champion-worker-density-v2",
        date="2026-08-07",
        independent_variable="Seed Procurement Arithmetic",
        parameter_values="Strict dictionary lookup vs Double-counting loop",
        sample_size=100,
        benchmark_seeds="Random 400-499",
        mean_reward=47088.53,
        median_reward=46800.00,
        std_dev=3800.00,
        win_rate=0.94,
        p_value=0.00001,
        effect_size=0.85,
        economic_attribution="+$1,004 improvement. The base Champion iterated through the seed dictionary and incorrectly double-counted Melon seeds (adding both `.get('MELON')` and the loop value). This math error forced it to systematically under-buy seeds, leaving workers idle without seeds to plant. Fixing to a strict lookup eliminated empty tile starvation.",
        decision="PROMOTE",
        git_commit="2c918bb",
        git_tag="champion-seed-fix-v3"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-005",
        category="Algorithm",
        branch="feature/assignment-optimization",
        champion_version="champion-seed-fix-v3",
        date="2026-08-07",
        independent_variable="Worker Assignment Logic",
        parameter_values="Greedy vs Hungarian",
        sample_size=100,
        benchmark_seeds="Random 700-799",
        mean_reward=46725.12,
        median_reward=46725.00,
        std_dev=0.00,
        win_rate=0.29,
        p_value=None,
        effect_size=None,
        economic_attribution="EV: -$730. Minimum-distance assignment successfully reduced global travel but reduced Final Money. Distributing travel load evenly via Hungarian eliminated instant task execution (Greedy allows one worker to travel 0 steps while another travels 20, whereas Hungarian forces both to travel 10). The delay caused a 48% spike in Water Backlog.",
        decision="REJECT",
        git_commit="N/A",
        git_tag="N/A"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="EXP-006",
        category="Analysis",
        branch="feature/utility-discovery",
        champion_version="champion-seed-fix-v3",
        date="2026-08-07",
        independent_variable="Task Utility Determinants",
        parameter_values="Random Forest Feature Importance",
        sample_size=20,
        benchmark_seeds="Random 800-819",
        mean_reward=0.0,
        median_reward=0.0,
        std_dev=0.0,
        win_rate=0.0,
        p_value=None,
        effect_size=None,
        economic_attribution="Expected Harvest Value (38.9%) and Task Delay (22.5%) are the primary predictors of final monetary contribution. Travel distance accounted for only 6.4%, explaining why Hungarian assignment failed. Planting tasks uniquely carry 12.5% weight due to structural risk. The result generated the utility feature vectors for EXP-007.",
        decision="Hypothesis Generated",
        git_commit="N/A",
        git_tag="N/A"
    ))
    
    registry.log_experiment(ExperimentResult(
        experiment_id="SUB-V3",
        category="Submission",
        branch="main",
        champion_version="champion-seed-fix-v3",
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        independent_variable="Kaggle Submission",
        parameter_values="Submission Archive Size: 13079 bytes",
        sample_size=0,
        benchmark_seeds="N/A",
        mean_reward=46925.00,
        median_reward=46925.00,
        std_dev=0.00,
        win_rate=0.0,
        p_value=None,
        effect_size=None,
        economic_attribution="Submission ID: 89341257. Archive packaged and verified successfully in clean isolated environment.",
        decision="SUBMITTED",
        git_commit="2c918bb",
        git_tag="champion-seed-fix-v3"
    ))
    
    # Generate Top Hypotheses
    hypotheses = [
        {
            "name": "Crop Portfolio Optimization (Wheat vs Melon vs Carrot ratio over time)",
            "ev": "+$3,500",
            "confidence": "High",
            "complexity": "Medium",
            "time": "4 hours"
        },
        {
            "name": "Market Timing Policy (Dynamic Sell Thresholds based on Town Unlocks)",
            "ev": "+$2,500",
            "confidence": "Medium",
            "complexity": "High",
            "time": "6 hours"
        },
        {
            "name": "Dynamic Cash Reserve (Scaling liquidity buffer with total farm size)",
            "ev": "+$1,200",
            "confidence": "Medium",
            "complexity": "Low",
            "time": "2 hours"
        },
        {
            "name": "Targeted Livestock Portfolio (Sheep vs Cows near end-game)",
            "ev": "Unknown",
            "confidence": "Low",
            "complexity": "High",
            "time": "8 hours"
        }
    ]
    registry.update_top_hypotheses(hypotheses)
    
    print("Experiment Registry initialized successfully.")
