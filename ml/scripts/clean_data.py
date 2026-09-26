import pandas as pd

# Load raw data
df = pd.read_csv("ml/data/raw/heart_disease.csv")
print(f"Original shape: {df.shape}")

# Remove exact duplicate rows
df = df.drop_duplicates()
print(f"Shape after removing duplicates: {df.shape}")

# Save the cleaned dataset to the 'processed' folder
# (raw/ stays untouched — always keep an original copy)
df.to_csv("ml/data/processed/heart_disease_clean.csv", index=False)
print("Cleaned dataset saved to ml/data/processed/heart_disease_clean.csv")