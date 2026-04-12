import json
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest



# ============================================================
# 1. DATA LOADING
# ============================================================

def load_baseline(path):
    df = pd.read_csv(path)
    return df  # contains id,d1..d8


def load_events(path):
    df = pd.read_csv(path)

    # Convert CAN ID from hex string -> int
    def clean_id(x):
        x = str(x).replace("000000", "")
        return int(x, 16)

    df["ID"] = df["ID"].apply(clean_id)

    # Convert byte fields from hex to int
    byte_cols = ["D1","D2","D3","D4","D5","D6","D7","D8"]
    for c in byte_cols:
        df[c] = df[c].apply(lambda x: int(str(x), 16))

    return df


def load_actions(path):
    with open(path, "r") as f:
        return json.load(f)



# ============================================================
# 2. PARSE EXCLUSIVE IDS TEXT
# ============================================================

def parse_relevant_ids_from_text(text):
    """
    Input (exclusive_ids.txt):

      Driver Door:
        0040: b49(12)
      Foot Brake:
        0032: b54(5), ...

    Output:
        {
          "Driver Door": [0x40],
          "Foot Brake": [0x32],
          ...
        }
    """
    action_map = {}
    current_action = None

    for line in text.splitlines():
        line = line.rstrip()

        # Detect an action (e.g. "Driver Door:")
        if re.match(r"^\s*\S.*:$", line):
            current_action = line.replace(":", "").strip()
            action_map[current_action] = []
            continue

        # Detect CAN ID (e.g. "0040:")
        match = re.match(r"^\s*([0-9A-Fa-f]{4}):", line)
        if match and current_action is not None:
            hex_id = match.group(1)
            action_map[current_action].append(int(hex_id, 16))

    return action_map



# ============================================================
# 3. GLOBAL AUTOENCODER (1 MODEL ONLY!)
# ============================================================

class GlobalAE(nn.Module):
    def __init__(self, input_dim=8):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8),
            nn.ReLU(),
            nn.Linear(8, 3)
        )
        self.decoder = nn.Sequential(
            nn.Linear(3, 8),
            nn.ReLU(),
            nn.Linear(8, input_dim)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))



def train_global_ae(all_baseline_vectors, epochs=25, lr=0.001):
    """
    Train ONE autoencoder on ALL baseline bytes from ALL IDs.
    """
    device = "cpu"  # CPU is fastest for small batches

    X_tensor = torch.tensor(all_baseline_vectors, dtype=torch.float32).to(device)

    model = GlobalAE(8).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    # Manual batching (avoids DataLoader overhead)
    batch_size = 64

    model.train()
    for epoch in range(epochs):
        perm = torch.randperm(len(X_tensor))
        X_tensor = X_tensor[perm]

        for i in range(0, len(X_tensor), batch_size):
            xb = X_tensor[i:i+batch_size]

            optimizer.zero_grad()
            recon = model(xb)
            loss = loss_fn(recon, xb)
            loss.backward()
            optimizer.step()

    return model



# ============================================================
# 4. TRAIN ISOLATION FOREST PER ID
# ============================================================

def train_isolation_forests(baseline_df):
    """
    Train a separate IsolationForest per CAN ID.
    """
    id_models = {}
    id_scalers = {}

    for can_id in baseline_df["id"].unique():
        rows = baseline_df[baseline_df["id"] == can_id]
        X_raw = rows.iloc[:, 1:].values  # d1..d8

        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)

        iso = IsolationForest(
            contamination=0.02,
            warm_start=True,
            n_estimators=50
        )
        iso.fit(X)

        id_models[can_id] = iso
        id_scalers[can_id] = scaler

    return id_models, id_scalers



# ============================================================
# 5. DEVIATION SCORING
# ============================================================

def compute_deviation(event_df, actions_json, action_to_ids,
                      global_ae, id_models, id_scalers):

    device = "cpu"
    results = {}

    for action_name, action_info in actions_json.items():

        # Extract segment list
        segments = []
        idx = 1
        while True:
            s = "start_index" if idx == 1 else f"start_index_{idx}"
            e = "end_index"   if idx == 1 else f"end_index_{idx}"

            if s in action_info and e in action_info:
                segments.append((action_info[s], action_info[e]))
                idx += 1
            else:
                break

        # Relevant IDs for this action
        relevant_ids = set(action_to_ids.get(action_name, []))

        # To accumulate per-segment scores
        scores_per_id = {cid: [] for cid in relevant_ids}

        for (start, end) in segments:
            seg = event_df.iloc[start:end]

            for can_id in seg["ID"].unique():
                if can_id not in relevant_ids:
                    continue
                if can_id not in id_models:
                    continue

                iso = id_models[can_id]
                scaler = id_scalers[can_id]

                rows = seg[seg["ID"] == can_id]
                X_raw = rows[["D1","D2","D3","D4","D5","D6","D7","D8"]].values

                X = scaler.transform(X_raw)

                # ---- Global AE reconstruction error ----
                with torch.no_grad():
                    xt = torch.tensor(X, dtype=torch.float32).to(device)
                    recon = global_ae(xt)
                    ae_error = ((xt - recon)**2).mean(dim=1).mean().item()

                # ---- IsolationForest anomaly score ----
                iso_score = -iso.score_samples(X).mean()

                scores_per_id[can_id].append(ae_error + iso_score)

        # Final combined score across segments
        out = {}
        for can_id, arr in scores_per_id.items():
            if arr:
                out[f"0x{can_id:X}"] = float(np.mean(arr))

        results[action_name] = out

    return results



def run_full_ml_pipeline(baseline_path, events_path, actions_path, exclusive_ids_text):
    baseline = load_baseline(baseline_path)
    events = load_events(events_path)
    actions_json = load_actions(actions_path)

    action_to_ids = parse_relevant_ids_from_text(exclusive_ids_text)

    baseline_vectors = baseline.iloc[:, 1:].values.astype(np.float32)

    global_ae = train_global_ae(baseline_vectors)
    id_models, id_scalers = train_isolation_forests(baseline)

    deviations = compute_deviation(
        event_df=events,
        actions_json=actions_json,
        action_to_ids=action_to_ids,
        global_ae=global_ae,
        id_models=id_models,
        id_scalers=id_scalers
    )

    return deviations

# ============================================================
# 6. MAIN PIPELINE
# ============================================================

def main():
    baseline_file = "./event-bits/input/baseline-export.csv"
    events_file = "./event-bits/input/raw-export.csv"
    actions_file = "./event-bits/input/event_indexes.json"
    exclusive_ids_file = "./event-bits/input/analysis.txt"   # Your text block file

    print("Loading...")
    baseline = load_baseline(baseline_file)
    events = load_events(events_file)
    actions_json = load_actions(actions_file)

    with open(exclusive_ids_file, "r") as f:
        text_ids = f.read()

    print("Parsing relevant IDs...")
    action_to_ids = parse_relevant_ids_from_text(text_ids)

    print("Preparing global AE training data...")
    # Stack all d1..d8 from baseline
    baseline_vectors = baseline.iloc[:, 1:].values  # ignore id column
    baseline_vectors = baseline_vectors.astype(np.float32)

    print("Training global autoencoder (one model only)...")
    global_ae = train_global_ae(baseline_vectors)

    print("Training per-ID IsolationForest models...")
    id_models, id_scalers = train_isolation_forests(baseline)

    print("Computing deviations...")
    deviations = compute_deviation(
        event_df=events,
        actions_json=actions_json,
        action_to_ids=action_to_ids,
        global_ae=global_ae,
        id_models=id_models,
        id_scalers=id_scalers
    )

    print("\n=== FINAL RESULT ===")
    print(json.dumps(deviations, indent=4))

    with open("deviations_output.json", "w") as f:
        json.dump(deviations, f, indent=4)

    print("\nSaved → deviations_output.json")



if __name__ == "__main__":
    main()