# Paper trading ETH v1.11 (and BNB crypto_v0_1) through TradingView alerts

TradingView cannot auto-execute a strategy, not even on its Paper Trading account, and Breakout has no API. So the paper account lives here: the v1.11 Pine strategy fires an alert on each simulated order fill, TradingView POSTs it to your PC, and `backtesting/paper_webhook.py` appends it to an immutable ledger scored against the Breakout $50k 1-Step limits (static $47,000 floor, 3% daily loss from the 00:30 UTC balance). Nothing is routed to Breakout; mirror fills by hand in the Breakout Terminal if you want them live.

## One-time setup (about 20 minutes)

1. **TradingView Essential** (or higher) with **2FA enabled**; webhooks are refused otherwise.
2. **ngrok**: create a free account at ngrok.com, claim your free static domain (Dashboard -> Domains), then on your PC:
   `winget install ngrok.ngrok` and `ngrok config add-authtoken <token from the dashboard>`.
3. Start the receiver from the repo root: `$env:NGROK_DOMAIN='your-name.ngrok-free.app'; .\backtesting\start_paper_webhook.ps1`. It prints the secret and opens the tunnel. Check `https://your-name.ngrok-free.app/health` in a browser.
4. In TradingView open **BINANCE:ETHUSDT.P, 5-minute, standard candles**, add `backtesting/reference/ETH_Strategy_v1_11.pine` via Pine Editor -> Add to chart. In the strategy inputs set **Planned risk per trade = 150** (Breakout 50k sizing); leave everything else at its defaults.
5. Create an alert: Condition = the strategy (**ETH v1.11 | Channel research**), it fires on order fills. Expiration: Essential caps alerts at 2 months (open-ended needs Premium), so take the maximum date and restart the alert from the Alerts panel (right sidebar clock icon → Restart) before it expires; TradingView emails a warning first. Notifications: tick **Webhook URL** and enter `https://your-name.ngrok-free.app/tradingview`. Message (replace YOUR_SECRET with the printed secret, keep everything else exactly):

```
{"secret":"YOUR_SECRET","ticker":"{{ticker}}","action":"{{strategy.order.action}}","contracts":"{{strategy.order.contracts}}","price":"{{strategy.order.price}}","position":"{{strategy.position_size}}","id":"{{strategy.order.id}}","comment":"{{strategy.order.comment}}","time":"{{timenow}}"}
```

6. Optional phone notifications: set `$env:PAPER_NOTIFY_URL` to a Discord or Slack incoming-webhook URL before starting; each fill is posted there with the running balance and floor buffer.

## Hosted deployment (current setup)

The receiver runs 24/7 on a DigitalOcean droplet (`eth-paper`, Ubuntu 24.04, $6/mo) instead of Nick's PC, so the ngrok steps above are not needed:

- Code: `/opt/eth-paper/paper_webhook.py` (a copy of `backtesting/paper_webhook.py` with `ROOT=/opt/eth-paper`), run by the `eth-paper` systemd service (auto-restart, starts on boot) on 127.0.0.1:8787.
- HTTPS: Caddy with an automatic Let's Encrypt certificate for `https://143-198-126-83.sslip.io` (also plain `http://143.198.126.83`), firewall open on 22/80/443 only.
- Webhook URL for the TradingView alert: `https://143-198-126-83.sslip.io/tradingview`; status page `https://143-198-126-83.sslip.io/status`; secret in `/opt/eth-paper/artifacts/paper_trading/secret.txt` on the server (never in this repo).
- Ledger: `/opt/eth-paper/artifacts/paper_trading/fills.jsonl` and `state.json`. Reset = stop the service, delete those two files (keep `secret.txt`), start it again.
- Updating the code: copy the new `paper_webhook.py` over, replace the `from .paths import ROOT` line with `from pathlib import Path` / `ROOT = Path('/opt/eth-paper')`, `systemctl restart eth-paper`.

## Second account: BNB crypto_v0_1 (side experiment)

The receiver keeps one paper account per strategy and routes each alert by its ticker: `ETHUSDT.P` -> ETH v1.11, `BNBUSDT.P` -> BNB crypto_v0_1 (ledger in `artifacts/paper_trading/bnb/`); any other ticker is rejected. Both alerts use the same webhook URL, secret and message JSON.

- Chart **BINANCE:BNBUSDT.P, 5-minute, standard candles**; add `backtesting/reference/BNB_Strategy_crypto_v0_1.pine` (unpromoted candidate; defaults already encode the frozen rule and the **$200** joint-replay sizing from `reports/eth_bnb_joint_replay.md`).
- Alert condition **BNB crypto_v0_1 | 4h momentum research**, same webhook URL and message as the ETH alert, 2-month expiry like ETH.
- `/status` reports both accounts. Reset BNB alone = stop the service, delete the `bnb/` folder, start it again.
- Expect ~2 trades a month; the 4h signal fires on the last 5-minute bar of a completed UTC-aligned 4h candle and fills on the next 5-minute open, as in the Python lab.

## Daily use

- `https://your-name.ngrok-free.app/status` (or `.ethvenv\Scripts\python.exe -m backtesting.paper_webhook --status`) shows balance, open position, closed trades, win rate, and any Breakout rule breach.
- Ledger files: `backtesting/artifacts/paper_trading/fills.jsonl` (append-only) and `state.json`.
- To restart a fresh paper account, stop the receiver and move the `paper_trading` folder aside; never edit `fills.jsonl`.

## Limits to keep in mind

- TradingView runs the strategy on its own servers with its own data; Pine/Python trade matching for v1.11 is **not verified**, so fills will differ somewhat from the Python backtest (fixed 2-tick slippage, no financing, no stop-first rule).
- The ledger marks closed fills only; open P&L is not included in the floor check. Breakout applies its limits to equity including open positions.
- The alert expires every 2 months on Essential; a lapsed alert silently stops the ledger until restarted.
- Alerts fire only while the receiver and tunnel are up; an outage loses those fills (TradingView retries nothing). Check `/health` after reboots.
- A changed strategy input requires deleting and recreating the alert; TradingView freezes a copy at alert creation.
- Paper results on a sealed forward period are the first honest evidence of v1.11; do not change the strategy because of them mid-period.
