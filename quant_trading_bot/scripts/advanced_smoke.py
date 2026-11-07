"""Record small seeded synthetic neural/RL training attempts; never claim market performance."""
from pathlib import Path
import importlib.util
import numpy as np
import tempfile
from quant_futures.cli import synthetic_fixture
from quant_futures.advanced import train_network, train_rl, make_environment
from quant_futures.config import ResearchConfig
from quant_futures.research import json_write, code_identity, load_dataset

ROOT = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(20261106)
x = rng.normal(size=(80, 8, 4)).astype(np.float32)
y = rng.integers(0, 2, 80)
attempts = []
for kind in ("mlp", "tcn", "lstm", "gru", "transformer"):
    try:
        _, log = train_network(kind, x[:60], y[:60], x[60:], y[60:], epochs=2)
        attempts.append(dict(model=kind, status="functional_training_completed", history=log))
    except (ImportError, RuntimeError, ValueError) as error:
        attempts.append(dict(model=kind, status="failed", error=str(error)))
temporary = tempfile.TemporaryDirectory(prefix=".test-tmp-advanced-", dir=ROOT)
fixture = synthetic_fixture(Path(temporary.name)/"fixture.parquet", sessions=2, bars_per_session=80)
bars, _, _ = load_dataset(fixture)
for algorithm in ("ppo", "dqn"):
    try:
        env = make_environment(bars.iloc[:80], bars[["close", "volume"]].iloc[:80], ResearchConfig())
        model = train_rl(algorithm, env, total_timesteps=128)
        observation, _ = env.reset(seed=20261106)
        done, rewards = False, []
        while not done:
            action, _ = model.predict(observation, deterministic=True)
            observation, reward, done, _, _ = env.step(int(action))
            rewards.append(reward)
        attempts.append(dict(model=algorithm, status="functional_training_completed", timesteps=128,
            synthetic_reward_sum=float(sum(rewards)), note="Training-domain replay; no out-of-sample market inference"))
    except (ImportError, RuntimeError, ValueError) as error:
        attempts.append(dict(model=algorithm, status="failed", error=str(error)))
json_write(ROOT/"reports/advanced_functional_tests.json", dict(synthetic=True, seed=20261106,
    **code_identity(), attempts=attempts, deployment_eligible=False))
print([(a["model"], a["status"]) for a in attempts])
temporary.cleanup()
