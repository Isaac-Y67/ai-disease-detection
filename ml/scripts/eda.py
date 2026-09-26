import pandas as pd

# Load the dataset
df = pd.read_csv("ml/data/raw/heart_disease.csv")

# 1. Basic shape and structure
print("=" * 50)
print("DATASET SHAPE:", df.shape)
print("=" * 50)

print("\nCOLUMN DATA TYPES:")
print(df.dtypes)

# 2. Check for missing values
print("\n" + "=" * 50)
print("MISSING VALUES PER COLUMN:")
print(df.isnull().sum())

# 3. Check for duplicate rows
print("\n" + "=" * 50)
print("DUPLICATE ROWS:", df.duplicated().sum())

# 4. Summary statistics
print("\n" + "=" * 50)
print("SUMMARY STATISTICS:")
print(df.describe())

# 5. Target class distribution
print("\n" + "=" * 50)
print("TARGET CLASS DISTRIBUTION:")
print(df["target"].value_counts())
print(df["target"].value_counts(normalize=True) * 100)

# 6. Show FULL summary stats (no truncation)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
print("\n" + "=" * 50)
print("FULL SUMMARY STATISTICS (no truncation):")
print(df.describe())

# 7. Outlier detection using IQR method (as per methodology)
print("\n" + "=" * 50)
print("OUTLIER COUNT PER COLUMN (IQR method):")
for col in df.columns:
    if col == "target":
        continue  # skip the target column, it's categorical (0/1), not a measurement
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
    print(f"{col}: {len(outliers)} outliers")