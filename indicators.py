"""Experimental M5/M15 setups. Uses only closed candles; no volume required."""
import pandas as pd
import ta
from config import ATR_STOP_MULT, TP1_R, TP2_R


def analyze_setup(m5: pd.DataFrame, m15: pd.DataFrame) -> dict:
    if len(m5) < 60 or len(m15) < 60:
        raise ValueError('Servono almeno 60 candele chiuse per timeframe')
    a, b = m5.copy(), m15.copy()
    for df in (a, b):
        df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
        df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    bb = ta.volatility.BollingerBands(a['close'], window=20, window_dev=2)
    a['bb_low'], a['bb_high'] = bb.bollinger_lband(), bb.bollinger_hband()
    last, prev, higher = a.iloc[-1], a.iloc[-2], b.iloc[-1]
    price, atr = float(last['close']), float(last['atr'])
    trend = ('UP' if higher['ema20'] > higher['ema50'] and higher['close'] > higher['ema20']
             else 'DOWN' if higher['ema20'] < higher['ema50'] and higher['close'] < higher['ema20']
             else 'SIDEWAYS')
    # Volatility-normalized recent levels: exclude signal candle to avoid lookahead.
    support = float(a['low'].iloc[-21:-1].min())
    resistance = float(a['high'].iloc[-21:-1].max())
    direction, strategy, score = None, None, 0.0
    if atr > 0 and atr / price <= 0.006:  # experimental excessive-volatility guard
        near_support = abs(float(last['low']) - support) <= 0.5 * atr
        near_resistance = abs(float(last['high']) - resistance) <= 0.5 * atr
        bullish = last['close'] > last['open'] and last['close'] > prev['close']
        bearish = last['close'] < last['open'] and last['close'] < prev['close']
        if trend != 'DOWN' and near_support and bullish and prev['rsi'] < 40 and last['rsi'] > prev['rsi']:
            direction, strategy, score = 'BUY', 'BOUNCE', 0.70
            if last['low'] <= last['bb_low']: score += 0.10
            if trend == 'UP': score += 0.10
        elif trend != 'UP' and near_resistance and bearish and prev['rsi'] > 60 and last['rsi'] < prev['rsi']:
            direction, strategy, score = 'SELL', 'BOUNCE', 0.70
            if last['high'] >= last['bb_high']: score += 0.10
            if trend == 'DOWN': score += 0.10
        elif (trend == 'UP' and last['ema20'] > last['ema50'] and
              prev['low'] <= prev['ema20'] + 0.3 * atr and bullish and 45 <= last['rsi'] <= 70):
            direction, strategy, score = 'BUY', 'TREND_PULLBACK', 0.75
            if (last['ema20'] - last['ema50']) >= 0.35 * atr: score += 0.12
        elif (trend == 'DOWN' and last['ema20'] < last['ema50'] and
              prev['high'] >= prev['ema20'] - 0.3 * atr and bearish and 30 <= last['rsi'] <= 55):
            direction, strategy, score = 'SELL', 'TREND_PULLBACK', 0.75
            if (last['ema50'] - last['ema20']) >= 0.35 * atr: score += 0.12
    result = dict(signal=direction, strategy=strategy, price=price, atr=round(atr, 3),
                  rsi=round(float(last['rsi']), 2), m15_trend=trend,
                  support=round(support, 2), resistance=round(resistance, 2),
                  local_score=round(score, 2), candle=a['datetime'].iloc[-1].isoformat())
    if direction:
        # Stop respects recent structure with ATR buffer; avoid tiny stops.
        if direction == 'BUY':
            sl = min(price - ATR_STOP_MULT * atr, support - 0.2 * atr)
            risk = price - sl
            tp1, tp2 = price + TP1_R * risk, price + TP2_R * risk
        else:
            sl = max(price + ATR_STOP_MULT * atr, resistance + 0.2 * atr)
            risk = sl - price
            tp1, tp2 = price - TP1_R * risk, price - TP2_R * risk
        result.update(sl=round(sl, 2), tp1=round(tp1, 2), tp2=round(tp2, 2),
                      risk_distance_usd=round(risk, 2), trailing_atr_multiple=1.0)
    return result
