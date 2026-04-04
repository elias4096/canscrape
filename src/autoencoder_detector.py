from typing import List, Dict
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

from models import SimpleCanFrame


# ============================================================
#  Δ-BYTE FEATURE EXTRACTION
# ============================================================

def compute_delta_bytes(byte_array_2d: np.ndarray) -> np.ndarray:
    """
    Given Nx8 array of raw CAN bytes, return Nx8 array of deltas:
    Δ[i] = bytes[i] - bytes[i-1]
    First row gets 0 deltas.
    """
    if len(byte_array_2d) == 0:
        return byte_array_2d

    deltas = np.zeros_like(byte_array_2d, dtype=float)
    deltas[1:] = byte_array_2d[1:] - byte_array_2d[:-1]
    return deltas


# ============================================================
#  Autoencoder Model (16 features = 8 raw + 8 delta)
# ============================================================

class Autoencoder(nn.Module):
    def __init__(self, input_dim=16):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 8),
            nn.ReLU(),
            nn.Linear(8, 2)
        )

        self.decoder = nn.Sequential(
            nn.Linear(2, 8),
            nn.ReLU(),
            nn.Linear(8, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        latent = self.encoder(x)
        return self.decoder(latent)


# ============================================================
#  Helper: Train autoencoder for one ID
# ============================================================

def train_autoencoder_for_id(idle_bytes: np.ndarray, epochs: int):
    """
    idle_bytes: Nx8 raw CAN data for ONE CAN ID.
    We compute Δ-bytes and train on [raw + delta].
    """
    # Raw bytes
    raw = idle_bytes.astype(float)

    # Δ bytes
    delta = compute_delta_bytes(raw)

    # Concatenate → Nx16
    X = np.hstack([raw, delta])

    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)

    model = Autoencoder(input_dim=X.shape[1])
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Train
    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        recon = model(X_tensor)
        loss = criterion(recon, X_tensor)
        loss.backward()
        optimizer.step()

    return model, scaler


# ============================================================
#  Compute event reconstruction errors for one ID
# ============================================================

def compute_errors_for_id(model, scaler, event_bytes: np.ndarray) -> np.ndarray:
    if len(event_bytes) == 0:
        return np.array([])

    raw = event_bytes.astype(float)
    delta = compute_delta_bytes(raw)
    X = np.hstack([raw, delta])     # Nx16 feature matrix

    X_scaled = scaler.transform(X)
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)

    with torch.no_grad():
        recon = model(X_tensor)
        mse = torch.mean((X_tensor - recon) ** 2, dim=1).numpy()

    return mse


# ============================================================
#  Likelihood mapping
# ============================================================

def likelihood_from_error(err):
    return min((err / 300) * 100, 100)


# ============================================================
#  Main API: per-ID autoencoder detection
# ============================================================

def likelihood_from_frames(
    baseline_csv: str,
    event_frames: List[SimpleCanFrame],
    allowed_ids: List[int],
    epochs: int = 20
):
    """
    One autoencoder PER CAN ID.
    Now uses: RAW bytes + Δ bytes.
    Much more sensitive to small changes.
    """

    # Load idle CSV
    idle_df = pd.read_csv(baseline_csv)

    byte_cols = ["d1","d2","d3","d4","d5","d6","d7","d8"]
    cols = ["id"] + byte_cols

    # Convert event frames -> DataFrame
    event_df = pd.DataFrame([
        {c: getattr(f, c, 0) for c in cols}
        for f in event_frames
    ])

    # Filter IDs
    idle_df = idle_df[idle_df["id"].isin(allowed_ids)]
    event_df = event_df[event_df["id"].isin(allowed_ids)]

    # Group idle/event by CAN ID
    idle_groups = {
        can_id: group[byte_cols].to_numpy()
        for can_id, group in idle_df.groupby("id")
    }

    event_groups = {
        can_id: group[byte_cols].to_numpy()
        for can_id, group in event_df.groupby("id")
    }

    # Train 1 model per ID
    models = {}
    scalers = {}

    for can_id, idle_bytes in idle_groups.items():
        if len(idle_bytes) < 20:
            continue

        model, scaler = train_autoencoder_for_id(idle_bytes, epochs)
        models[can_id] = model
        scalers[can_id] = scaler

    # Compute event reconstruction error per ID
    rows = []

    for can_id, event_bytes in event_groups.items():
        if can_id not in models:
            continue

        model = models[can_id]
        scaler = scalers[can_id]

        errors = compute_errors_for_id(model, scaler, event_bytes)

        for i, e in enumerate(errors):
            rows.append({
                "id": can_id,
                "index_in_event": i,
                "recon_error": e,
                "likelihood": likelihood_from_error(e),
            })

    result_df = pd.DataFrame(rows)

    if result_df.empty:
        return result_df

    return result_df.sort_values("likelihood", ascending=False)