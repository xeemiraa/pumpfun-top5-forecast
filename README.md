# Predict top 5 new Solana coins by market cap 24 hours out

Entry for make.fun bounty: Predict the top 5 new Solana coins by market cap, 24 hours out.

## What it does

Reads 11 hours of 10-minute market-cap snapshots of every coin launched on pump.fun,
analyzes growth patterns, momentum, and volatility, then forecasts which 5 coins will
be the largest 24 hours after the opening.

## Output

Writes `/output/forecast.json` with:
- Top 5 slots with coin IDs, probabilities, and predicted market caps
- Market cap distribution across bins

## Run

```bash
python3 main.py
```

## Requirements

- Python 3.13+
- Standard library only (no external dependencies)
- No network access
- Deterministic output (same input → same output)

## License

MIT
