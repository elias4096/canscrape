from typing import List

import pandas as pd
from sklearn.ensemble import IsolationForest

from models import SimpleCanFrame

def likelihood_from_frames(
    training_csv: str,
    event_frames: List[SimpleCanFrame],
    allowed_ids: List[int]
):
    idle_df = pd.read_csv(training_csv)
    event_df = pd.DataFrame([vars(f) for f in event_frames])

    #idle_df = idle_df.drop_duplicates()
    #event_df = event_df.drop_duplicates()

    #idle_df = idle_df[idle_df["id"].isin(allowed_ids)]
    event_df = event_df[event_df["id"].isin(allowed_ids)]

    cols = ["id","d1","d2","d3","d4","d5","d6","d7","d8"]
    idle_features = idle_df[cols].to_numpy()
    event_features = event_df[cols].to_numpy()

    iso = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
    iso.fit(idle_features)

    scores = iso.decision_function(event_features)
    norm = (scores - scores.min()) / (scores.max() - scores.min())
    likelihood = norm * 100

    event_df["iso_score"] = scores
    event_df["likelihood"] = likelihood

    ranked = event_df.sort_values("likelihood", ascending=False)
    return ranked