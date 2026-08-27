# OrderFlowSage

Strict, dependency-free limit-order-book snapshot replay with sequence integrity checks and transparent microstructure features. It calculates spread, microprice, top/depth imbalance, top-of-book order-flow imbalance (OFI), signed trade flow, checksums, and fixed event windows. It never predicts price or submits orders.

```console
$ ./install.sh
...
OrderFlowSage deterministic replay report
events=12 sequence=1000..1011 windows=3
spread_bps min=... mean=... max=...
...
mode=offline_replay_only not_a_prediction_or_signal
```

The command runs the full test suite and synthetic replay offline with Python 3.10+ and no runtime dependencies.

## Concrete distinction

The relationship between top-of-book order-flow imbalance and short-horizon price changes has been studied by [Cont, Kukanov, and Stoikov](https://arxiv.org/abs/1011.6402). OrderFlowSage does not reproduce their empirical model and does not turn OFI into a prediction. It provides the missing reproducibility layer before modeling: strict snapshot ordering, exact sequence continuity, canonical timestamps, sorted positive-depth levels, uncrossed books, explicit formulas, per-book hashes, deterministic window boundaries, and complete recomputation.

It handles searches and errors such as **"order book sequence gap"**, **"bids not sorted descending"**, **"locked or crossed book"**, **"calculate microprice Python without pandas"**, and **"top of book OFI replay"**.

## Input

Configuration:

```json
{"schema_version":1,"depth_levels":3,"window_events":100,"expected_start_sequence":5000}
```

One full snapshot per JSONL line:

```json
{"sequence":5000,"timestamp":"2026-01-01T00:00:00Z","bids":[[99.9,10],[99.8,15],[99.7,20]],"asks":[[100.1,11],[100.2,16],[100.3,21]],"trades":[{"side":"buy","size":2}]}
```

Bids must have unique descending prices; asks must have unique ascending prices. Prices and sizes are positive. Best bid must remain below best ask. Sequence numbers and timestamps must be gap-free and strictly increasing respectively.

```bash
./run.sh run config.json snapshots.jsonl report.json
./run.sh verify config.json snapshots.jsonl report.json
./run.sh summary report.json
./run.sh prompt report.json local-commentary-prompt.json
```

`verify` replays the complete dataset. `prompt` exports aggregate measurements without raw books, timestamps, or prices and tells an optional local LLM that imbalance and OFI are measurements—not trading signals.

## Feature definitions

- `mid = (best_bid + best_ask) / 2`
- `microprice = (ask * bid_size + bid * ask_size) / (bid_size + ask_size)`
- top/depth imbalance is `(bid_size - ask_size) / total_size`
- signed trade flow counts buyer-initiated size positive and seller-initiated size negative as declared by the input
- OFI uses changes in best prices and displayed queues on both sides between adjacent snapshots

## Limitations and safety

- Offline replay only; no API credentials, sockets, live feeds, exchange access, wallets, signing, orders, custody, or trading.
- No price, return, fill, alpha, manipulation, participant, or profit claim.
- Input trade side is trusted; aggressor inference is not performed.
- Full snapshots cannot represent event ordering hidden between observations.
- Displayed depth excludes hidden liquidity and venue-specific queue rules.
- Floating-point inputs are deterministic for the same canonical JSON but are not tick-decimal accounting.
- Window statistics are descriptive and do not include sampling uncertainty.

## Support

[Donations fund additional development time](SUPPORT.md). Confirmed donors may request a direction using a public transaction hash; donations cannot purchase ownership, returns, deadlines, priority, acceptance, or prohibited work.

Apache-2.0 licensed. See [LICENSE](LICENSE).


## Standard launcher

`./run.sh` is the normal entry point. It runs `./install.sh` automatically when setup is missing, then opens the PySide6 control panel with live output and actions for the demo, tests, repair, and stop. Use `./cli.sh` for CLI-only operation.
