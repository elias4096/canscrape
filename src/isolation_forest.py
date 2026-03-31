from typing import List
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from models import SimpleCanFrame


def byte_entropy(byte_array):
    values, counts = np.unique(byte_array, return_counts=True)
    probs = counts / counts.sum()
    return -np.sum(probs * np.log2(probs))


def likelihood_from_score(score):
    return 100 / (1 + np.exp(-12 * (score - 0)))


def likelihood_from_frames(
    training_csv: str,
    event_frames: List[SimpleCanFrame],
    allowed_ids: List[int]
):
    idle_df = pd.read_csv(training_csv)

    cols = ["id", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"]

    event_df = pd.DataFrame([
        {c: getattr(f, c, 0) for c in cols}
        for f in event_frames
    ])

    idle_df = idle_df.drop_duplicates()
    event_df = event_df.drop_duplicates()

    idle_df = idle_df[idle_df["id"].isin(allowed_ids)]
    event_df = event_df[event_df["id"].isin(allowed_ids)]

    byte_cols = ["d1","d2","d3","d4","d5","d6","d7","d8"]

    idle_df["byte_sum"] = idle_df[byte_cols].sum(axis=1)
    event_df["byte_sum"] = event_df[byte_cols].sum(axis=1)

    idle_df["byte_entropy"] = idle_df[byte_cols].apply(lambda r: byte_entropy(r.to_numpy()), axis=1)
    event_df["byte_entropy"] = event_df[byte_cols].apply(lambda r: byte_entropy(r.to_numpy()), axis=1)

    cols = ["id"] + byte_cols + ["byte_sum", "byte_entropy"]

    idle_features = idle_df[cols].to_numpy()
    event_features = event_df[cols].to_numpy()

    scaler = StandardScaler()
    idle_scaled = scaler.fit_transform(idle_features)
    event_scaled = scaler.transform(event_features)

    iso = IsolationForest(
        n_estimators=400,
        contamination=0.003,
        max_samples=0.7,
        bootstrap=True,
        random_state=42
    )
    iso.fit(idle_scaled)

    scores = iso.decision_function(event_scaled)
    event_df["iso_score"] = scores
    event_df["likelihood"] = [likelihood_from_score(s) for s in scores]

    ranked = event_df.sort_values("likelihood", ascending=False)
    return ranked