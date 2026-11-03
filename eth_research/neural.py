"""Small CPU-friendly PyTorch candidates with chronological early stopping."""
import copy

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset


class WindowDataset(Dataset):
    def __init__(self, x, y, indices, window):
        self.x, self.y, self.indices, self.window = x, y, indices, window

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, item):
        i = self.indices[item]
        return self.x[i - self.window + 1:i + 1], self.y[i]


class Network(nn.Module):
    def __init__(self, kind, features, hidden=32):
        super().__init__()
        self.kind = kind
        if kind == "mlp":
            self.encoder = nn.Sequential(nn.Linear(features, hidden * 2), nn.ReLU(), nn.Dropout(.2),
                                         nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Dropout(.1))
        elif kind == "lstm":
            self.encoder = nn.LSTM(features, hidden, num_layers=1, batch_first=True)
        elif kind == "cnn":
            self.encoder = nn.Sequential(nn.Conv1d(features, hidden, 3, padding=2, dilation=1), nn.ReLU(),
                                         nn.Conv1d(hidden, hidden, 3, padding=4, dilation=2), nn.ReLU(),
                                         nn.AdaptiveAvgPool1d(1))
        else:
            raise ValueError(kind)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        if self.kind == "mlp":
            encoded = self.encoder(x[:, -1])
        elif self.kind == "lstm":
            encoded = self.encoder(x)[0][:, -1]
        else:
            encoded = self.encoder(x.transpose(1, 2)).squeeze(-1)
        return self.head(encoded).squeeze(-1)


class TorchClassifier:
    def __init__(self, kind, hidden=32, learning_rate=.001, epochs=8, batch_size=512, sequence_length=24, seed=42):
        self.config = dict(kind=kind, hidden=hidden, learning_rate=learning_rate, epochs=epochs,
                           batch_size=batch_size, sequence_length=sequence_length, seed=seed)
        self.scaler = StandardScaler()
        self.history = []

    def fit(self, all_x, all_y, indices):
        cfg = self.config
        torch.manual_seed(cfg["seed"])
        torch.set_num_threads(4)
        # Internal tail is solely for epoch selection; outer validation is never used here.
        cut = int(len(indices) * .85)
        train, valid = indices[:cut - 2], indices[cut:]
        first = train[0] - cfg["sequence_length"] + 1
        self.scaler.fit(all_x[first:train[-1] + 1])
        x = self.scaler.transform(all_x).clip(-12, 12).astype(np.float32)
        y = np.nan_to_num(all_y).astype(np.float32)
        window = 1 if cfg["kind"] == "mlp" else cfg["sequence_length"]
        self.net = Network(cfg["kind"], x.shape[1], cfg["hidden"])
        optimizer = torch.optim.AdamW(self.net.parameters(), lr=cfg["learning_rate"], weight_decay=.01)
        criterion = nn.BCEWithLogitsLoss()
        train_loader = DataLoader(WindowDataset(x, y, train, window), batch_size=cfg["batch_size"], shuffle=True)
        valid_loader = DataLoader(WindowDataset(x, y, valid, window), batch_size=cfg["batch_size"])
        best, patience, state = float("inf"), 0, None
        for epoch in range(cfg["epochs"]):
            self.net.train()
            train_loss = 0.
            for xb, yb in train_loader:
                optimizer.zero_grad()
                loss = criterion(self.net(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), 1.)
                optimizer.step()
                train_loss += loss.item() * len(yb)
            self.net.eval()
            total, count = 0., 0
            with torch.no_grad():
                for xb, yb in valid_loader:
                    total += criterion(self.net(xb), yb).item() * len(yb)
                    count += len(yb)
            val_loss = total / count
            self.history.append({"epoch": epoch + 1, "train_loss": train_loss / len(train), "validation_loss": val_loss})
            if val_loss < best - 1e-5:
                best, patience, state = val_loss, 0, copy.deepcopy(self.net.state_dict())
                self.best_epoch = epoch + 1
            else:
                patience += 1
                if patience >= 2:
                    break
        self.net.load_state_dict(state)
        self.net.eval()
        return self

    def predict_probability(self, all_x, indices):
        cfg = self.config
        x = self.scaler.transform(all_x).clip(-12, 12).astype(np.float32)
        window = 1 if cfg["kind"] == "mlp" else cfg["sequence_length"]
        loader = DataLoader(WindowDataset(x, np.zeros(len(x), dtype=np.float32), indices, window),
                            batch_size=cfg["batch_size"])
        outputs = []
        self.net.eval()
        with torch.no_grad():
            for xb, _ in loader:
                outputs.append(torch.sigmoid(self.net(xb)).numpy())
        return np.concatenate(outputs)

    def export(self):
        return {"config": self.config, "scaler": self.scaler, "history": self.history,
                "best_epoch": self.best_epoch,
                "weights": {key: value.detach().cpu().numpy() for key, value in self.net.state_dict().items()}}

    @classmethod
    def restore(cls, bundle, features):
        model = cls(**bundle["config"])
        model.scaler = bundle["scaler"]
        model.net = Network(model.config["kind"], features, model.config["hidden"])
        model.net.load_state_dict({key: torch.from_numpy(value) for key, value in bundle["weights"].items()})
        model.net.eval()
        return model
