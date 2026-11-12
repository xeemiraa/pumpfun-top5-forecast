#!/usr/bin/env python3
"""
Predict the top 5 new Solana coins by market cap 24 hours out.
Read 11 hours of 10-minute market-cap snapshots from /input,
output forecast to /output/forecast.json.
"""

import json
import os
import math
from collections import defaultdict
from pathlib import Path

INPUT_DIR = Path("/input")
OUTPUT_DIR = Path("/output")


def load_snapshots():
    """Load market cap snapshots from /input."""
    snapshots = []
    
    # Look for snapshot files in /input
    if not INPUT_DIR.exists():
        print(f"Warning: {INPUT_DIR} does not exist")
        return snapshots
    
    for f in sorted(INPUT_DIR.iterdir()):
        if f.suffix in ['.json', '.jsonl', '.csv']:
            try:
                content = f.read_text()
                if f.suffix == '.json':
                    data = json.loads(content)
                    if isinstance(data, list):
                        snapshots.extend(data)
                    elif isinstance(data, dict):
                        # Could be a single snapshot or nested structure
                        if 'snapshots' in data:
                            snapshots.extend(data['snapshots'])
                        elif 'data' in data:
                            snapshots.extend(data['data'])
                        else:
                            snapshots.append(data)
                elif f.suffix == '.jsonl':
                    for line in content.strip().split('\n'):
                        if line.strip():
                            snapshots.append(json.loads(line))
                elif f.suffix == '.csv':
                    # Simple CSV parsing
                    lines = content.strip().split('\n')
                    headers = lines[0].split(',')
                    for line in lines[1:]:
                        vals = line.split(',')
                        row = {}
                        for i, h in enumerate(headers):
                            row[h.strip()] = vals[i].strip() if i < len(vals) else ''
                        snapshots.append(row)
            except Exception as e:
                print(f"Warning: Could not parse {f}: {e}")
    
    print(f"Loaded {len(snapshots)} snapshots from {INPUT_DIR}")
    return snapshots


def parse_snapshot(s):
    """Parse a snapshot entry into a standard format."""
    # Handle different formats
    if isinstance(s, dict):
        # Try common field names
        coin_id = s.get('coin_id') or s.get('token') or s.get('mint') or s.get('address') or s.get('id')
        market_cap = s.get('market_cap') or s.get('mcap') or s.get('marketCap') or s.get('market_cap_usd')
        timestamp = s.get('timestamp') or s.get('time') or s.get('ts') or s.get('snapshot_time')
        tx_time = s.get('tx_time') or s.get('created_at') or s.get('launch_time')
        
        if coin_id is None:
            return None
            
        try:
            mc = float(market_cap) if market_cap is not None else None
        except (ValueError, TypeError):
            mc = None
            
        try:
            ts = int(timestamp) if timestamp is not None else None
        except (ValueError, TypeError):
            ts = None
            
        return {
            'coin_id': str(coin_id),
            'market_cap': mc,
            'timestamp': ts,
            'tx_time': tx_time,
            'raw': s
        }
    return None


def analyze_coins(snapshots):
    """Analyze coin data to predict top 5."""
    if not snapshots:
        print("No snapshots to analyze")
        return []
    
    # Parse all snapshots
    parsed = []
    for s in snapshots:
        p = parse_snapshot(s)
        if p and p['market_cap'] is not None and p['timestamp'] is not None:
            parsed.append(p)
    
    if not parsed:
        print("No valid snapshots after parsing")
        return []
    
    # Group by coin
    coins = defaultdict(list)
    for p in parsed:
        coins[p['coin_id']].append(p)
    
    print(f"Found {len(coins)} unique coins")
    
    # Sort each coin's snapshots by timestamp
    for cid in coins:
        coins[cid].sort(key=lambda x: x['timestamp'] or 0)
    
    # Analyze each coin
    coin_metrics = []
    for cid, snaps in coins.items():
        if len(snaps) < 2:
            continue
            
        # Get first and last market cap
        first_mc = snaps[0]['market_cap']
        last_mc = snaps[-1]['market_cap']
        
        if first_mc is None or last_mc is None:
            continue
            
        # Calculate growth
        if first_mc > 0:
            growth_rate = (last_mc - first_mc) / first_mc
        else:
            growth_rate = 0
            
        # Calculate momentum (recent growth vs earlier)
        mid_point = len(snaps) // 2
        first_half = snaps[:mid_point]
        second_half = snaps[mid_point:]
        
        if len(first_half) > 0 and len(second_half) > 0:
            first_half_last = first_half[-1]['market_cap']
            second_half_last = second_half[-1]['market_cap']
            first_half_first = first_half[0]['market_cap']
            
            if first_half_first and first_half_last:
                first_half_growth = (first_half_last - first_half_first) / first_half_first if first_half_first > 0 else 0
            else:
                first_half_growth = 0
                
            if first_half_last and second_half_last:
                second_half_growth = (second_half_last - first_half_last) / first_half_last if first_half_last > 0 else 0
            else:
                second_half_growth = 0
        else:
            first_half_growth = 0
            second_half_growth = 0
        
        # Volume/transaction count as proxy for activity
        tx_count = len(set(s.get('tx_time') for s in snaps if s.get('tx_time')))
        
        # Volatility (standard deviation of returns)
        returns = []
        for i in range(1, len(snaps)):
            if snaps[i-1]['market_cap'] and snaps[i-1]['market_cap'] > 0:
                ret = (snaps[i]['market_cap'] - snaps[i-1]['market_cap']) / snaps[i-1]['market_cap']
                returns.append(ret)
        
        if returns:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            volatility = math.sqrt(variance)
        else:
            volatility = 0
            
        # Time since launch (if available)
        launch_time = snaps[0].get('tx_time')
        
        # Current market cap
        current_mc = last_mc
        
        # Predict final market cap based on growth trajectory
        # Simple model: extrapolate recent growth
        time_span = (snaps[-1]['timestamp'] or 0) - (snaps[0]['timestamp'] or 0)
        if time_span > 0:
            # Market cap at end of observation period
            predicted_24h_mc = last_mc * (1 + growth_rate * 2)  # Extrapolate 2x the observed growth
        else:
            predicted_24h_mc = last_mc
        
        coin_metrics.append({
            'coin_id': cid,
            'current_mc': current_mc,
            'predicted_24h_mc': predicted_24h_mc,
            'growth_rate': growth_rate,
            'first_half_growth': first_half_growth,
            'second_half_growth': second_half_growth,
            'momentum': second_half_growth - first_half_growth,
            'volatility': volatility,
            'tx_count': tx_count,
            'launch_time': launch_time,
            'snapshot_count': len(snaps),
            'last_ts': snaps[-1]['timestamp'],
        })
    
    print(f"Analyzed {len(coin_metrics)} coins with sufficient data")
    return coin_metrics


def predict_top5(coin_metrics):
    """Predict top 5 coins and generate forecast."""
    if not coin_metrics:
        return {
            'forecast': {
                'slots': [],
                'market_cap_distribution': {}
            },
            'model_info': 'No data available'
        }
    
    # Sort by predicted market cap (descending)
    sorted_coins = sorted(coin_metrics, key=lambda x: x['predicted_24h_mc'], reverse=True)
    
    # Take top candidates (more than 5 for probability calculation)
    top_candidates = sorted_coins[:min(20, len(sorted_coins))]
    
    # Calculate probabilities using softmax over predicted market caps
    predicted_mcs = [c['predicted_24h_mc'] for c in top_candidates]
    max_mc = max(predicted_mcs) if predicted_mcs else 1
    
    # Use log-scale softmax for better probability distribution
    log_mcs = [math.log(c + 1) for c in predicted_mcs]
    max_log = max(log_mcs) if log_mcs else 0
    exps = [math.exp(lm - max_log) for lm in log_mcs]
    sum_exps = sum(exps)
    
    # Probability for each coin being in top 5
    coin_probs = []
    for i, c in enumerate(top_candidates):
        prob = exps[i] / sum_exps if sum_exps > 0 else 0
        coin_probs.append({
            'coin_id': c['coin_id'],
            'probability': prob,
            'predicted_mc': c['predicted_24h_mc'],
            'current_mc': c['current_mc'],
            'growth_rate': c['growth_rate'],
        })
    
    # Sort by probability
    coin_probs.sort(key=lambda x: x['probability'], reverse=True)
    
    # Top 5 slots with probabilities
    slots = []
    for i in range(min(5, len(coin_probs))):
        slots.append({
            'place': i + 1,
            'coin_id': coin_probs[i]['coin_id'],
            'probability': coin_probs[i]['probability'],
            'predicted_market_cap': coin_probs[i]['predicted_mc'],
        })
    
    # Market cap distribution (in bins of 0.05 log10 steps)
    # Bins: 10^(0.05 * k) for k from 0 to 40 (covers 1 to 10^2 = 100)
    market_cap_bins = {}
    for k in range(41):
        low = 10 ** (0.05 * k)
        high = 10 ** (0.05 * (k + 1))
        bin_key = f"{low:.6f}_{high:.6f}"
        market_cap_bins[bin_key] = 0.0
    
    # Distribute probability across bins based on predicted market caps
    total_prob = sum(c['probability'] for c in coin_probs[:5])
    for c in coin_probs[:5]:
        pred_mc = c['predicted_mc']
        if pred_mc and pred_mc > 0:
            log_mc = math.log10(pred_mc)
            # Find which bin this falls in
            for k in range(40):
                low = 0.05 * k
                high = 0.05 * (k + 1)
                if low <= log_mc < high:
                    bin_key = f"{10**low:.6f}_{10**high:.6f}"
                    if bin_key in market_cap_bins:
                        market_cap_bins[bin_key] += c['probability'] / total_prob if total_prob > 0 else 0
                    break
    
    return {
        'forecast': {
            'slots': slots,
            'market_cap_distribution': market_cap_bins,
        },
        'model_info': {
            'coins_analyzed': len(coin_metrics),
            'candidates_considered': len(top_candidates),
        }
    }


def main():
    print("=" * 60)
    print("Predict top 5 Solana coins - make.fun bounty")
    print("=" * 60)
    
    # Load data
    snapshots = load_snapshots()
    
    # Analyze
    coin_metrics = analyze_coins(snapshots)
    
    # Predict
    forecast = predict_top5(coin_metrics)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write output
    output_file = OUTPUT_DIR / "forecast.json"
    with open(output_file, 'w') as f:
        json.dump(forecast, f, indent=2)
    
    print(f"\nForecast written to {output_file}")
    print(f"Top 5 predictions:")
    for slot in forecast['forecast']['slots']:
        print(f"  Place {slot['place']}: {slot['coin_id']} (prob: {slot['probability']:.4f}, predicted MC: {slot['predicted_market_cap']:.2f})")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
