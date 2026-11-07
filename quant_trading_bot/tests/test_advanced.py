import importlib.util
import numpy as np
import pytest
from quant_futures.config import ResearchConfig
from quant_futures.advanced import train_network, make_environment
from quant_futures.statistics import reality_check, deflated_sharpe_diagnostic


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="Optional PyTorch unavailable")
@pytest.mark.parametrize("kind", ["mlp", "tcn", "lstm", "gru", "transformer"])
def test_small_networks_train(kind):
    rng = np.random.default_rng(2)
    x = rng.normal(size=(12, 5, 3)).astype(np.float32)
    y = np.tile([0, 1], 6)
    net, log = train_network(kind, x[:8], y[:8], x[8:], y[8:], epochs=1)
    assert len(log) == 1 and np.isfinite(log[0]["validation_loss"])


@pytest.mark.skipif(importlib.util.find_spec("gymnasium") is None, reason="Optional Gymnasium unavailable")
def test_gym_environment(bars):
    from gymnasium.utils.env_checker import check_env
    features = bars[["close", "volume"]].iloc[:20]
    env = make_environment(bars.iloc[:20], features, ResearchConfig())
    check_env(env, skip_render_check=True)
    env.reset(seed=3)
    for _ in range(19):
        obs, reward, done, truncated, info = env.step(1)
        assert np.isfinite(reward)
    assert done


def test_multiple_testing_diagnostics():
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1, size=(100, 3))
    assert 0 < reality_check(x, draws=20)["pvalue"] <= 1
    assert deflated_sharpe_diagnostic(x[:, 0], [.1, .2, -.1])["probability"] is not None


@pytest.mark.skipif(importlib.util.find_spec("stable_baselines3") is None, reason="Optional stable-baselines3 unavailable")
@pytest.mark.parametrize("algorithm", ["ppo", "dqn"])
def test_rl_training_smoke(algorithm, bars):
    from quant_futures.advanced import train_rl
    b = bars.iloc[:40]
    env = make_environment(b, b[["close", "volume"]], ResearchConfig())
    model = train_rl(algorithm, env, total_timesteps=64)
    observation, _ = env.reset(seed=1)
    action, _ = model.predict(observation, deterministic=True)
    assert int(action) in (0, 1, 2, 3)
