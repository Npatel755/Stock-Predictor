import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
qualifiers = json.load(open(ROOT / 'runs/htf_swing_training_qualifiers.json'))
print(f"Total training qualifiers in htf_swing_training_qualifiers.json: {len(qualifiers)}")

df = pd.DataFrame(qualifiers)
print("\nBreakdown by Symbol and Timeframe:")
print(df.groupby(['sym', 'tf', 'family', 'session']).size())

print("Columns in qualifiers:", list(df.columns))
print(df.head(5).to_string())
