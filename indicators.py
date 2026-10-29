import pandas as pd
import numpy as np
import ta
from config import RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT

def analyze_scalp_setup(data: pd.DataFrame) -> dict:
    """Receives only closed M5 candles, oldest first. Keeps original strategy."""
    df = data.copy()
    if len(df) < 30:
        raise ValueError('Servono almeno 30 candele chiuse')
    df['rsi'] = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_upper'] = bb.bollinger_hband()
    # Centered pivots need 5 future candles: only confirmed pivots are used.
    window = 5
    df['pivot_high'] = df['high'].rolling(11, center=True).apply(
        lambda x: x.iloc[5] if x.iloc[5] == x.max() else np.nan, raw=False)
    df['pivot_low'] = df['low'].rolling(11, center=True).apply(
        lambda x: x.iloc[5] if x.iloc[5] == x.min() else np.nan, raw=False)
    latest, prev = df.iloc[-1], df.iloc[-2]
    supports = df['pivot_low'].dropna().tail(5).tolist()
    resistances = df['pivot_high'].dropna().tail(5).tolist()
    support = min(supports, key=lambda x: abs(x - latest['close'])) if supports else None
    resistance = min(resistances, key=lambda x: abs(x - latest['close'])) if resistances else None
    signal, level, score = None, None, 0.0
    has_volume = 'volume' in df.columns and df['volume'].notna().any()
    volume_avg = df['volume'].rolling(20).mean().iloc[-1] if has_volume else None
    if support is not None and abs(latest['low'] - support) <= 1.0:
        if prev['rsi'] <= RSI_OVERSOLD and latest['rsi'] > prev['rsi']:
            signal, level, score = 'BUY', support, 0.4
            if latest['close'] <= latest['bb_lower']: score += 0.3
            if has_volume and pd.notna(volume_avg) and latest['volume'] > volume_avg: score += 0.3
    elif resistance is not None and abs(latest['high'] - resistance) <= 1.0:
        if prev['rsi'] >= RSI_OVERBOUGHT and latest['rsi'] < prev['rsi']:
            signal, level, score = 'SELL', resistance, 0.4
            if latest['close'] >= latest['bb_upper']: score += 0.3
            if has_volume and pd.notna(volume_avg) and latest['volume'] > volume_avg: score += 0.3
    return dict(signal=signal, price=float(latest['close']),
                level_price=float(level) if level is not None else None,
                rsi=round(float(latest['rsi']), 2), local_score=round(score, 2),
                support=float(support) if support is not None else None,
                resistance=float(resistance) if resistance is not None else None)
