import json
import re
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest


# ============================================================
# 1. DATA LOADING
# ============================================================

def load_baseline(path):
    return pd.read_csv(path)


def load_events(path):
    df = pd.read_csv(path)

    def clean_id(x):
        x = str(x).replace("000000", "")
        return int(x, 16)

    df["ID"] = df["ID"].apply(clean_id)

    for c in ["D1","D2","D3","D4","D5","D6","D7","D8"]:
        df[c] = df[c].apply(lambda x: int(str(x), 16)).astype(np.float32)

    return df


def load_actions(path):
    with open(path, "r") as f:
        return json.load(f)


# ============================================================
# 2. PARSE EXCLUSIVE IDS TEXT
# ============================================================

def parse_relevant_ids_from_text(text):
    action_map = {}
    current_action = None

    for line in text.splitlines():
        line = line.rstrip()

        if re.match(r"^\s*\S.*:$", line):
            current_action = line.replace(":", "").strip()
            action_map[current_action] = []
            continue

        match = re.match(r"^\s*([0-9A-Fa-f]{4}):", line)
        if match and current_action:
            action_map[current_action].append(int(match.group(1), 16))

    return action_map


# ============================================================
# 3. TRAIN ISOLATION FORESTS (NO CACHING)
# ============================================================

def train_isolation_forests(baseline_df):
    models = {}
    scalers = {}
    baseline_stats = {}

    for can_id, rows in baseline_df.groupby("id"):
        X_raw = rows.iloc[:, 1:].values.astype(np.float32)

        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)

        model = IsolationForest(
            n_estimators=200,
            contamination="auto",
            max_samples="auto",
            random_state=42,
            n_jobs=-1
        )
        model.fit(X)

        baseline_scores = -model.score_samples(X)
        baseline_stats[can_id] = (
            baseline_scores.mean(),
            baseline_scores.std() + 1e-6
        )

        models[can_id] = model
        scalers[can_id] = scaler

    return models, scalers, baseline_stats


# ============================================================
# 4. DEVIATION COMPUTATION (IMPROVED)
# ============================================================

def compute_deviation(events, actions, action_to_ids,
                      models, scalers, baseline_stats):

    results = {}

    for action_name, action_info in actions.items():
        relevant_ids = set(action_to_ids.get(action_name, []))
        scores = {cid: [] for cid in relevant_ids}

        # collect segments
        segments = []
        i = 1
        while True:
            s = "start_index" if i == 1 else f"start_index_{i}"
            e = "end_index"   if i == 1 else f"end_index_{i}"
            if s in action_info and e in action_info:
                segments.append((action_info[s], action_info[e]))
                i += 1
            else:
                break

        for start, end in segments:
            seg = events.iloc[start:end]

            for can_id, rows in seg.groupby("ID"):
                if can_id not in relevant_ids:
                    continue
                if can_id not in models:
                    continue

                X_raw = rows[
                    ["D1","D2","D3","D4","D5","D6","D7","D8"]
                ].values.astype(np.float32)

                X = scalers[can_id].transform(X_raw)

                raw_scores = -models[can_id].score_samples(X)
                window_score = np.percentile(raw_scores, 80)

                mean, std = baseline_stats[can_id]
                z = (window_score - mean) / std

                scores[can_id].append(z)

        results[action_name] = {
            f"0x{cid:X}": float(np.mean(v))
            for cid, v in scores.items() if v
        }

    return results


# ============================================================
# 5. ENTRY POINT
# ============================================================

def run_full_ml_pipeline(
    baseline_path,
    events_path,
    actions_path,
    exclusive_ids_text
):
    baseline = load_baseline(baseline_path)
    events = load_events(events_path)
    actions = load_actions(actions_path)
    action_to_ids = parse_relevant_ids_from_text(exclusive_ids_text)

    models, scalers, baseline_stats = train_isolation_forests(baseline)

    return compute_deviation(
        events,
        actions,
        action_to_ids,
        models,
        scalers,
        baseline_stats
    )
