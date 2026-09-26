"""Generate a realistic synthetic e-commerce dataset (Jan 2023 - Dec 2024).

Built-in behaviours the analysis should rediscover:
  - growth trend + Nov/Dec holiday peak
  - acquisition channels with different repeat-purchase propensity
  - heavy-tailed customer value (a few customers drive most revenue)
  - categories with different price points, margins and return rates
  - bigger discounts -> bigger baskets but thinner margins
Plus deliberate data-quality issues so the cleaning step has real work to do.
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = Path(__file__).parent / "raw"
OUT.mkdir(exist_ok=True)

N_CUSTOMERS = 6000
START, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")
SEASON = np.array([0.85, 0.80, 0.90, 0.95, 1.00, 0.95, 0.90, 0.95, 1.00, 1.05, 1.45, 1.70])

CHANNELS = {  # name: (share of new customers, repeat-purchase multiplier)
    "Organic Search": (0.30, 1.00),
    "Paid Search": (0.25, 0.70),
    "Social Media": (0.20, 0.55),
    "Email": (0.10, 1.50),
    "Referral": (0.15, 1.30),
}
REGIONS = {"South": 0.33, "West": 0.27, "Northeast": 0.22, "Midwest": 0.18}
CATEGORIES = {  # name: (min price, max price, margin, return rate, popularity, product nouns)
    "Electronics": (40, 900, 0.18, 0.09, 0.18, ["Headphones", "Smartwatch", "Speaker", "Tablet", "Monitor", "Webcam"]),
    "Home & Kitchen": (15, 250, 0.35, 0.05, 0.22, ["Blender", "Cookware Set", "Lamp", "Coffee Maker", "Knife Set", "Bedding"]),
    "Apparel": (12, 120, 0.50, 0.14, 0.24, ["Jacket", "Sneakers", "Hoodie", "Jeans", "T-Shirt", "Dress"]),
    "Beauty": (8, 80, 0.60, 0.04, 0.16, ["Serum", "Moisturizer", "Lipstick", "Shampoo", "Perfume", "Face Mask"]),
    "Sports & Outdoors": (15, 300, 0.38, 0.06, 0.12, ["Yoga Mat", "Tent", "Dumbbells", "Backpack", "Bike Helmet", "Water Bottle"]),
    "Books": (6, 45, 0.25, 0.02, 0.08, ["Novel", "Cookbook", "Biography", "Guidebook", "Workbook", "Comic"]),
}
BRANDS = ["Nova", "Apex", "Luma", "Orbit", "Terra", "Vista", "Zenith", "Pulse"]

# --- products -------------------------------------------------------------
products = []
for cat, (lo, hi, margin, _, pop, nouns) in CATEGORIES.items():
    for _ in range(int(300 * pop)):
        price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi))))) - 0.01
        products.append({
            "product_id": f"P{len(products) + 1:04d}",
            "product_name": f"{rng.choice(BRANDS)} {rng.choice(nouns)} {rng.integers(100, 999)}",
            "category": cat,
            "unit_price": price,
            "unit_cost": round(price * (1 - margin * rng.uniform(0.8, 1.2)), 2),
        })
products = pd.DataFrame(products)
by_cat = {c: g.index.to_numpy() for c, g in products.groupby("category")}
cat_names = list(CATEGORIES)
cat_pop = np.array([v[4] for v in CATEGORIES.values()])
cat_pop /= cat_pop.sum()

# --- customers (signups follow trend x seasonality) -------------------------
days = pd.date_range(START, END, freq="D")
w = (1 + 0.8 * np.arange(len(days)) / len(days)) * SEASON[days.month - 1]
customers = pd.DataFrame({
    "customer_id": [f"C{i:05d}" for i in range(1, N_CUSTOMERS + 1)],
    "signup_date": np.sort(rng.choice(days, N_CUSTOMERS, p=w / w.sum())),
    "acquisition_channel": rng.choice(list(CHANNELS), N_CUSTOMERS, p=[v[0] for v in CHANNELS.values()]),
    "region": rng.choice(list(REGIONS), N_CUSTOMERS, p=list(REGIONS.values())),
})

# --- orders & line items ----------------------------------------------------
orders, items = [], []
for c in customers.itertuples():
    lam = 1.6 * CHANNELS[c.acquisition_channel][1] * rng.gamma(0.7, 1 / 0.7)  # heavy-tailed loyalty
    mean_gap = rng.uniform(30, 120)
    d = c.signup_date + pd.Timedelta(days=int(rng.integers(0, 3)))
    dates = [d] if d <= END else []
    for _ in range(rng.poisson(lam)):
        d += pd.Timedelta(days=int(rng.exponential(mean_gap)) + 1)
        if d > END:
            break
        if rng.random() < SEASON[d.month - 1] / SEASON.max() + 0.3:  # repeat orders cluster in holidays
            dates.append(d)

    for d in dates:
        order_id = f"O{len(orders) + 1:06d}"
        holiday = d.month in (11, 12)
        discount = int(rng.choice([0, 10, 15, 20, 30], p=[.40, .20, .10, .18, .12] if holiday else [.65, .15, .10, .08, .02]))
        status = "Cancelled" if rng.random() < 0.025 else "Completed"
        orders.append({"order_id": order_id, "customer_id": c.customer_id, "order_date": d,
                       "status": status, "discount_pct": discount})
        for _ in range(1 + rng.poisson(0.35 + discount / 40)):
            cat = rng.choice(cat_names, p=cat_pop)
            p = products.loc[rng.choice(by_cat[cat])]
            items.append({"order_id": order_id, "product_id": p.product_id,
                          "quantity": 1 + int(rng.random() < 0.15) + int(rng.random() < 0.03),
                          "unit_price": p.unit_price,
                          "returned": status == "Completed" and rng.random() < CATEGORIES[cat][3]})
orders, items = pd.DataFrame(orders), pd.DataFrame(items)

# --- inject real-world data-quality issues ----------------------------------
bad = rng.choice(N_CUSTOMERS, 180, replace=False)
customers.loc[bad, "region"] = [rng.choice([r.upper(), r.lower(), f" {r} "]) for r in customers.loc[bad, "region"]]
customers.loc[rng.choice(N_CUSTOMERS, 60, replace=False), "region"] = np.nan

orders["order_date"] = orders["order_date"].dt.strftime("%Y-%m-%d")
odd = rng.choice(len(orders), int(0.03 * len(orders)), replace=False)
orders.loc[odd, "order_date"] = pd.to_datetime(orders.loc[odd, "order_date"]).dt.strftime("%d-%b-%Y")
orders = pd.concat([orders, orders.sample(frac=0.01, random_state=1)]).sort_values("order_id")

items.loc[rng.choice(len(items), 40, replace=False), "quantity"] = rng.choice([0, -1], 40)
items.loc[rng.choice(len(items), 50, replace=False), "unit_price"] = np.nan

customers.to_csv(OUT / "customers.csv", index=False, date_format="%Y-%m-%d")
products.to_csv(OUT / "products.csv", index=False)
orders.to_csv(OUT / "orders.csv", index=False)
items.to_csv(OUT / "order_items.csv", index=False)
print(f"customers={len(customers):,} products={len(products):,} orders={len(orders):,} items={len(items):,}")
