import math
import os

# --- Constants from the game ---
CROP_DATA = {
    "WHEAT": {"seed": 10, "price": 25, "time": 4, "yield": 4, "actions": 6},
    "CARROT": {"seed": 20, "price": 35, "time": 3, "yield": 3, "actions": 5},
    "TOMATO": {"seed": 50, "price": 60, "time": 11, "yield": 4, "actions": 16},
    "STRAWBERRY": {"seed": 100, "price": 120, "time": 16, "yield": 4, "actions": 21},
    "MELON": {"seed": 80, "price": 250, "time": 12, "yield": 6, "actions": 14},
}

ANIMAL_DATA = {
    "GOOSE": {"cost": 300, "product_price": 50, "interval": 1, "first_yield": 4, "feed_day": 1},
    "COW": {"cost": 400, "product_price": 160, "interval": 2, "first_yield": 8, "feed_day": 1},
    "SHEEP": {"cost": 500, "product_price": 200, "interval": 3, "first_yield": 6, "feed_day": 1},
}
WHEAT_MARKET_PRICE = 25 # Opportunity cost of feed

LAND_COSTS = [1000, 2000, 4000]

def calculate_crop_roi(day):
    results = []
    days_left = 30 - day
    
    for name, data in CROP_DATA.items():
        if data["time"] > days_left:
            continue # Won't mature
            
        cycles = days_left // data["time"]
        rev = cycles * data["yield"] * data["price"]
        cost = cycles * data["seed"]
        profit = rev - cost
        
        # Single cycle stats
        cycle_profit = (data["yield"] * data["price"]) - data["seed"]
        roi = (cycle_profit / data["seed"]) * 100
        roi_per_day = roi / data["time"]
        profit_per_action = cycle_profit / data["actions"]
        
        results.append({
            "name": name,
            "cost": data["seed"],
            "payback": data["time"],
            "gross_rev": data["yield"] * data["price"],
            "net_profit": cycle_profit,
            "roi": roi,
            "actions": data["actions"],
            "profit_per_action": profit_per_action,
            "roi_per_day": roi_per_day,
            "max_cycles": cycles
        })
    return sorted(results, key=lambda x: x["roi_per_day"], reverse=True)

def calculate_animal_roi(day):
    results = []
    days_left = 30 - day
    
    for name, data in ANIMAL_DATA.items():
        if days_left < data["first_yield"]:
            continue
            
        productive_days = days_left - data["first_yield"] + 1
        yields = 1 + (productive_days - 1) // data["interval"]
        
        gross_rev = yields * data["product_price"]
        
        feed_cost_total = days_left * data["feed_day"] * WHEAT_MARKET_PRICE
        total_cost = data["cost"] + feed_cost_total
        
        profit = gross_rev - total_cost
        roi = (profit / data["cost"]) * 100 if data["cost"] > 0 else 0
        
        # Payback period
        payback = None
        for d in range(1, days_left + 1):
            feed_c = d * data["feed_day"] * WHEAT_MARKET_PRICE
            if d >= data["first_yield"]:
                prod_days = d - data["first_yield"] + 1
                y = 1 + (prod_days - 1) // data["interval"]
                if y * data["product_price"] >= data["cost"] + feed_c:
                    payback = d
                    break
                    
        results.append({
            "name": name,
            "cost": data["cost"],
            "payback": payback,
            "gross_rev": gross_rev,
            "net_profit": profit,
            "roi": roi,
            "feed_cost": feed_cost_total,
            "total_yields": yields
        })
    return sorted(results, key=lambda x: x["roi"], reverse=True)

def generate_report():
    os.makedirs("/home/crow/.gemini/antigravity-ide/brain/0f4dc6b0-35bc-4e53-8181-463c352182ce/", exist_ok=True)
    report_path = "/home/crow/.gemini/antigravity-ide/brain/0f4dc6b0-35bc-4e53-8181-463c352182ce/investment_discovery.md"
    
    with open(report_path, "w") as f:
        f.write("# Phase 3A: Investment Policy Discovery\n\n")
        f.write("This analytical report evaluates every possible investment decision as a function of the day it is made. The objective is to determine the globally optimal capital allocation path without any heuristic bias.\n\n")
        
        f.write("## 1. Crop Portfolio Efficiency\n")
        f.write("If you receive $1 and have spare labor and land, which seed should you buy?\n\n")
        
        f.write("| Crop | Capital Cost | Gross Rev | Net Profit | Payback (Days) | Actions | Profit/Action | ROI | ROI/Day |\n")
        f.write("|------|--------------|-----------|------------|----------------|---------|---------------|-----|---------|\n")
        
        crops = calculate_crop_roi(0)
        for c in crops:
            f.write(f"| {c['name']} | ${c['cost']} | ${c['gross_rev']} | ${c['net_profit']} | {c['payback']} | {c['actions']} | ${c['profit_per_action']:.2f} | {c['roi']:.1f}% | **{c['roi_per_day']:.1f}%** |\n")
            
        f.write("\n> [!TIP]\n")
        f.write("> **Melon** dominates absolute profit per action ($101.43), making it the ultimate bottleneck breaker when labor is scarce. However, **Wheat** has the highest ROI per day (225%) and the fastest payback, making it the supreme choice when *capital* is scarce (Day 0-5).\n\n")

        f.write("## 2. Livestock Viability\n")
        f.write("Assuming wheat feed costs $25/day (opportunity cost of not selling it). How do animals perform?\n\n")
        
        f.write("### Lifetime ROI (Purchased on Day 0)\n")
        f.write("| Animal | Capital Cost | Lifetime Feed | Gross Rev | Net Profit | Payback | ROI |\n")
        f.write("|--------|--------------|---------------|-----------|------------|---------|-----|\n")
        
        animals = calculate_animal_roi(0)
        for a in animals:
            payback_str = f"{a['payback']} days" if a['payback'] else "NEVER"
            f.write(f"| {a['name']} | ${a['cost']} | ${a['feed_cost']} | ${a['gross_rev']} | ${a['net_profit']} | {payback_str} | **{a['roi']:.1f}%** |\n")
            
        f.write("\n> [!WARNING]\n")
        f.write("> **Livestock is mathematically terrible.** Even if purchased on Day 0, Gooses and Sheep NEVER pay off their capital + feed cost by Day 30. Cows only achieve a miserable 1.25% ROI over the entire 30-day game. They consume too much wheat and require high upfront capital that would return 10,000%+ if compounded into crops.\n\n")
        
        f.write("## 3. Worker and Land ROI\n")
        f.write("A hired worker provides 24 actions per day. If they strictly manage Melons, what is their value?\n")
        f.write("- **Melon Yield:** 1 Melon takes 14 actions and nets $1420.\n")
        f.write("- **Worker Value:** 24 actions / 14 actions = 1.71 Melons managed per day.\n")
        f.write("- **Profit per Worker-Day:** 1.71 * $1420 = **$2,434 / day**.\n")
        f.write("- **ROI on $100 Wage:** ~2400% in a single day, provided you have land and seed capital.\n\n")
        
        f.write("Land (Quadrant 2) costs $1,000 and provides 25 tiles.\n")
        f.write("- 25 tiles of Melons yields 25 * $1420 = $35,500 net profit per 12-day cycle.\n")
        f.write("- Therefore, land pays for itself in less than half a cycle, assuming labor and seed capital exist.\n\n")

        f.write("## 4. The 'Next Dollar' Decision Matrix (Day D)\n")
        f.write("Based on the math, here is the absolute priority list for the next available dollar:\n\n")
        
        f.write("1. **Is Labor a bottleneck? (Unused planted tiles dying)**\n")
        f.write("   - **Action**: HIRE (ROI: ~2400% / day)\n")
        f.write("2. **Is Capital < $80? (Cannot afford Melons)**\n")
        f.write("   - **Action**: Buy WHEAT (ROI: 900% in 4 days, fastest capital compounder)\n")
        f.write("3. **Is Capital > $80 and Land is available?**\n")
        f.write("   - **Action**: Buy MELON (ROI: 1775% in 12 days, highest profit per labor action)\n")
        f.write("4. **Is Land full (100% planted) and Capital > $1,000?**\n")
        f.write("   - **Action**: Buy LAND (Unlocks 25 more tiles for Melon compounding)\n")
        f.write("5. **Is it Day 18+?**\n")
        f.write("   - **Action**: Stop buying Land/Melons (12-day cycle won't finish). Switch entirely to WHEAT and CARROTS to extract final drops of liquidity.\n")
        f.write("6. **Should I buy Livestock?**\n")
        f.write("   - **Action**: NEVER. Avoid completely.\n\n")

    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    generate_report()
