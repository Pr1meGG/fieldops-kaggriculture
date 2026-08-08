import json
import os

class ObservatoryExporter:
    def __init__(self, out_dir="observatory_data"):
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)
        self.metadata = {
            "Phase": "Phase 1",
            "Bot Version": "V1 (Observatory Setup)",
            "Git Commit": "8c597b9040d9c45ebd4a23aed8c4a4f2a20dc59a",
            "Git Tag": "phase-0-foundation"
        }
        
    def export_game(self, seed, game_data):
        game_data["metadata"] = self.metadata
        filepath = os.path.join(self.out_dir, f"game_{seed:03d}.json")
        with open(filepath, "w") as f:
            json.dump(game_data, f, indent=2)
            
    def export_summary(self, summary_data):
        filepath = os.path.join(self.out_dir, "summary.json")
        with open(filepath, "w") as f:
            json.dump(summary_data, f, indent=2)
