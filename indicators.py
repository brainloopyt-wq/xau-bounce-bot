import pandas as pd
import numpy as np
import ta
from config import RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT

def calculate_pivot_levels(df: pd.DataFrame, window: int = 5):
    """
    Finestra stretta per generare più livelli intermedi per lo scalping.
    """
    df['pivot_high'] = df['high'].rolling(window=window*2+1, center=True).apply(
        lambda x: x[window] if max(x) == x[window] else np.nan
    )
    df['pivot_low'] = df['low'].rolling(window=window*2+1, center=True).apply(
        lambda x: x[window] if min(x) == x[window] else np.nan
    )
    return df

def analyze_scalp_setup(df: pd.DataFrame):
    df['rsi'] = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
    
    # Bande di Bollinger per confermare la deviazione dalla media
    bollinger = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_lower'] = bollinger.bollinger_lband()
    df['bb_upper'] = bollinger.bollinger_hband()
    
    df = calculate_pivot_levels(df)
    
    latest = df.iloc[-2]
    prev = df.iloc[-3]
    
    latest_close = latest['close']
    latest_rsi = latest['rsi']
    prev_rsi = prev['rsi']
    
    recent_supports = df['pivot_low'].dropna().tail(5).tolist()
    recent_resistances = df['pivot_high'].dropna().tail(5).tolist()
    
    nearest_support = min(recent_supports, key=lambda x: abs(x - latest_close)) if recent_supports else None
    nearest_resistance = min(recent_resistances, key=lambda x: abs(x - latest_close)) if recent_resistances else None
    
    signal = None
    level_price = None
    local_score = 0.0
    TOLERANCE = 1.0  
    
    # Condizione BUY (Rimbalzo su Supporto)
    if nearest_support and abs(latest['low'] - nearest_support) <= TOLERANCE:
        if prev_rsi <= RSI_OVERSOLD and latest_rsi > prev_rsi:
            signal = "BUY"
            level_price = nearest_support
            local_score += 0.4
            if latest_close <= latest['bb_lower']:
                local_score += 0.3
            if latest['volume'] > df['volume'].rolling(20).mean().iloc[-2]:
                local_score += 0.3
            
    # Condizione SELL (Rimbalzo su Resistenza)
    elif nearest_resistance and abs(latest['high'] - nearest_resistance) <= TOLERANCE:
        if prev_rsi >= RSI_OVERBOUGHT and latest_rsi < prev_rsi:
            signal = "SELL"
            level_price = nearest_resistance
            local_score += 0.4
            if latest_close >= latest['bb_upper']:
                local_score += 0.3
            if latest['volume'] > df['volume'].rolling(20).mean().iloc[-2]:
                local_score += 0.3

    return {
        "signal": signal,
        "price": latest_close,
        "level_price": level_price,
        "rsi": round(latest_rsi, 2),
        "local_score": round(local_score, 2),
        "support": nearest_support,
        "resistance": nearest_resistance
    }