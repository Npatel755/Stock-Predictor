"""Small experimental PyTorch models and Gymnasium environment; paper only."""
import numpy as np
import pandas as pd


def build_network(kind, feature_count, hidden=16):
    import torch
    from torch import nn

    class Network(nn.Module):
        def __init__(self):
            super().__init__()
            self.kind = kind
            if kind == "mlp":
                self.body = nn.Sequential(nn.Linear(feature_count, hidden), nn.ReLU(), nn.Linear(hidden, 1))
            elif kind in ("lstm", "gru"):
                self.body = (nn.LSTM if kind == "lstm" else nn.GRU)(feature_count, hidden, batch_first=True)
                self.head = nn.Linear(hidden, 1)
            elif kind == "tcn":
                # Left padding only, causal temporal convolution.
                self.body = nn.Conv1d(feature_count, hidden, kernel_size=3)
                self.head = nn.Linear(hidden, 1)
            elif kind == "transformer":
                self.input = nn.Linear(feature_count, hidden)
                self.body = nn.TransformerEncoder(nn.TransformerEncoderLayer(hidden, 2, hidden*2, dropout=0, batch_first=True), 1)
                self.head = nn.Linear(hidden, 1)
            else:
                raise ValueError(kind)

        def forward(self, x):
            if self.kind == "mlp":
                return self.body(x[:, -1]).squeeze(-1)
            if self.kind in ("lstm", "gru"):
                x, _ = self.body(x)
            elif self.kind == "tcn":
                x = self.body(nn.functional.pad(x.transpose(1, 2), (2, 0))).relu().transpose(1, 2)
            else:
                z = self.input(x)
                # Deterministic positional encoding; no hindsight context or future mask holes.
                positions = torch.arange(z.shape[1], device=z.device, dtype=z.dtype)[None, :, None]
                frequencies = torch.arange(z.shape[2], device=z.device, dtype=z.dtype)[None, None, :]+1
                z = z+torch.sin(positions/frequencies)
                mask = torch.triu(torch.ones(z.shape[1], z.shape[1], device=z.device, dtype=torch.bool), diagonal=1)
                x = self.body(z, mask=mask)
            return self.head(x[:, -1]).squeeze(-1)
    return Network()


def train_network(kind, x_train, y_train, x_validation, y_validation, *, epochs=5, seed=20261106, device="cpu"):
    """Only pre-separated training and inner validation arrays; no final-test input."""
    import torch
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    train = np.asarray(x_train, dtype=np.float32)
    valid = np.asarray(x_validation, dtype=np.float32)
    if train.ndim != 3 or valid.ndim != 3 or not np.isfinite(train).all() or not np.isfinite(valid).all():
        raise ValueError("Finite [samples,time,features] arrays required; fit scaling on training only")
    net = build_network(kind, train.shape[-1]).to(device)
    optimizer = torch.optim.Adam(net.parameters(), lr=.001)
    criterion = torch.nn.BCEWithLogitsLoss()
    x = torch.tensor(train, device=device)
    y = torch.tensor(np.asarray(y_train), dtype=torch.float32, device=device)
    log = []
    best, best_loss = None, np.inf
    for epoch in range(epochs):
        net.train()
        optimizer.zero_grad()
        loss = criterion(net(x), y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1)
        optimizer.step()
        net.eval()
        with torch.no_grad():
            vloss = criterion(net(torch.tensor(valid, device=device)), torch.tensor(np.asarray(y_validation), dtype=torch.float32, device=device)).item()
        log.append(dict(epoch=epoch, train_loss=loss.item(), validation_loss=vloss))
        if vloss < best_loss:
            best_loss = vloss
            best = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best)
    return net, log


def make_environment(bars, features, config, *, drawdown_penalty=.01, turnover_penalty=.1):
    import gymnasium as gym
    from gymnasium import spaces
    from .backtest import Simulator

    class TradingEnvironment(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            if len(bars) < 3:
                raise ValueError("At least three bars required")
            self.action_space = spaces.Discrete(4)
            self.x = np.nan_to_num(features.to_numpy(dtype=np.float32), nan=0, posinf=0, neginf=0)
            self.observation_space = spaces.Box(-1e9, 1e9, shape=(self.x.shape[1]+5,), dtype=np.float32)
            self.rows = list(bars.itertuples(index=False))

        def _observe(self):
            state = self.sim.curve[-1]
            values = np.r_[self.x[self.i], state["quantity"], state["equity"]-state["cash"],
                state["cash"]-config.initial_balance, self.sim.risk.limits.max_drawdown-(self.sim.risk.peak-state["equity"]),
                max(0, config.execution.session_flat_minute_et-(self.rows[self.i].timestamp_utc.tz_convert("America/New_York").hour*60+self.rows[self.i].timestamp_utc.tz_convert("America/New_York").minute))]
            return np.clip(values, -1e9, 1e9).astype(np.float32)

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)
            self.i = 0
            self.sim = Simulator(config)
            self.sim.step(self.rows[0], 0)
            self.peak = config.initial_balance
            return self._observe(), dict(mode="experimental_paper_environment")

        def step(self, action):
            if not self.action_space.contains(action):
                raise ValueError("Invalid action")
            desired = {0: 0, 1: 1, 2: -1, 3: 0}[int(action)]
            previous_equity = self.sim.curve[-1]["equity"]
            previous_quantity = self.sim.curve[-1]["quantity"]
            # Decision uses the already-observed completed bar; execute on a future bar.
            if self.sim.pending is None and not self.sim.risk.killed and not self.sim.risk.day_locked:
                self.sim.pending = (self.sim.index+config.execution.delay_bars, desired,
                    self.rows[self.i].timestamp_utc+pd.Timedelta(minutes=config.timeframe_minutes), self.rows[self.i].contract)
            self.i += 1
            state = self.sim.step(self.rows[self.i], None)
            self.peak = max(self.peak, state["equity"])
            drawdown = self.peak-state["equity"]
            turnover = abs(state["quantity"]-previous_quantity)
            reward = state["equity"]-previous_equity-drawdown_penalty*drawdown-turnover_penalty*turnover
            terminated = self.i == len(self.rows)-1 or self.sim.risk.killed
            if terminated:
                before = state["equity"]
                result = self.sim.finish()
                reward += result["curve"].equity.iloc[-1]-before
            return self._observe(), float(reward), bool(terminated), False, dict(equity=self.sim.curve[-1]["equity"], mode="experimental")
    return TradingEnvironment()


def train_rl(algorithm, environment, total_timesteps=2000, seed=20261106):
    from stable_baselines3 import PPO, DQN
    import torch
    torch.set_num_threads(1)
    choices = {"ppo": PPO, "dqn": DQN}
    if algorithm not in choices:
        raise ValueError("PPO/DQN supported; SAC requires a separate continuous-action design")
    options = dict(n_steps=64, batch_size=32, n_epochs=2) if algorithm == "ppo" else dict(learning_starts=32, buffer_size=2048, batch_size=32, train_freq=4)
    model = choices[algorithm]("MlpPolicy", environment, seed=seed, device="cpu", verbose=0, **options)
    model.learn(total_timesteps=total_timesteps)
    return model
