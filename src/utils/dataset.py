"""
Sample dataset generator.
Generates a synthetic California Housing dataset with intentional missing values and outliers.
Run as: python -m src.utils.dataset
"""

import os
import numpy as np
import pandas as pd

from src.config import DATA_DIR


def generate_housing_dataset(n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic housing dataset resembling California Housing."""
    rng = np.random.default_rng(seed)

    med_inc = rng.lognormal(mean=1.5, sigma=0.5, size=n_samples)
    house_age = rng.uniform(1, 52, size=n_samples)
    ave_rooms = rng.uniform(2, 10, size=n_samples)
    ave_bedrms = ave_rooms * rng.uniform(0.15, 0.35, size=n_samples)
    population = rng.lognormal(mean=6.0, sigma=0.8, size=n_samples)
    ave_occup = rng.uniform(1.5, 5.0, size=n_samples)
    latitude = rng.uniform(32.5, 42.0, size=n_samples)
    longitude = rng.uniform(-124.5, -114.3, size=n_samples)

    # House value correlated with income and location (simplified)
    med_house_val = (
        med_inc * 0.5
        + (52 - house_age) * 0.01
        + ave_rooms * 0.05
        - ave_occup * 0.02
        + rng.normal(0, 0.3, size=n_samples)
    ).clip(0.15, 5.0)

    df = pd.DataFrame(
        {
            "MedInc": med_inc,
            "HouseAge": house_age,
            "AveRooms": ave_rooms,
            "AveBedrms": ave_bedrms,
            "Population": population,
            "AveOccup": ave_occup,
            "Latitude": latitude,
            "Longitude": longitude,
            "MedHouseVal": med_house_val,
        }
    )

    # Inject ~5% missing values across several columns
    missing_rate = 0.05
    for col in ["MedInc", "HouseAge", "AveRooms", "AveBedrms", "Population"]:
        mask = rng.random(size=n_samples) < missing_rate
        df.loc[mask, col] = np.nan

    # Inject a handful of extreme outliers
    outlier_indices = rng.choice(n_samples, size=10, replace=False)
    df.loc[outlier_indices[:5], "MedInc"] = rng.uniform(20, 30, size=5)
    df.loc[outlier_indices[5:], "Population"] = rng.uniform(30000, 50000, size=5)

    return df


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, "housing.csv")
    df = generate_housing_dataset()
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path} ({len(df)} rows, {df.shape[1]} columns)")
    print(f"Missing values injected:\n{df.isnull().sum()}")


if __name__ == "__main__":
    main()
