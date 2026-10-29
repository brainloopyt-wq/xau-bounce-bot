import logging
import time
import os
from datetime import datetime, timezone
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import pandas as pd
from config import (TWELVEDATA_API_KEY, SYMBOL, SCAN_INTERVAL,
                    DEFAULT_SL_DOLLARS, DEFAULT_TP_DOLLARS)
from indicators import analyze_scalp_setup
from ai_validator import validate_signal_with_gemini
from db import save_bot_status, save_bounce_signal
from telegram_bot import send_bounce_telegram_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('bounce')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bounce bot process online (not market-feed health)')
    def log_message(self, *_): pass

def serve():
    HTTPServer(('0.0.0.0', int(os.getenv('PORT', '10000'))), Handler).serve_forever()

def fetch_closed_candles():
    if not TWELVEDATA_API_KEY:
        raise RuntimeError('TWELVEDATA_API_KEY mancante')
    r = requests.get('https://api.twelvedata.com/time_series', params={
        'symbol': SYMBOL, 'interval': '5min', 'outputsize': 100,
        'apikey': TWELVEDATA_API_KEY, 'timezone': 'UTC', 'format': 'JSON'}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get('status') == 'error' or not data.get('values'):
        raise RuntimeError(f"Feed Twelve Data: {str(data.get('message', data))[:250]}")
    df = pd.DataFrame(data['values'])
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # Forex/metal feeds may not provide real traded volume.
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    df = df.dropna(subset=['datetime', 'open', 'high', 'low', 'close'])
    now = pd.Timestamp.now(tz='UTC')
    df = df[df['datetime'] + pd.Timedelta(minutes=5) <= now]
    df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
    if len(df) < 30:
        raise RuntimeError(f'Solo {len(df)} candele chiuse disponibili')
    return df

def run():
    last_alert_candle = None
    # Un solo polling ogni 5 minuti: evita 2.880 richieste al giorno.
    poll_seconds = max(300, SCAN_INTERVAL)
    log.info("Polling Twelve Data ogni %s secondi", poll_seconds)
    while True:
        try:
            df = fetch_closed_candles()
            candle = df['datetime'].iloc[-1].isoformat()
            setup = analyze_scalp_setup(df)
            log.info('Candle=%s price=%.2f RSI=%.2f score=%.2f signal=%s',
                     candle, setup['price'], setup['rsi'], setup['local_score'], setup['signal'])
            save_bot_status(price=setup['price'], rsi=setup['rsi'],
                            local_score=setup['local_score'],
                            message=f"Feed Twelve Data OK | candela M5 chiusa {candle}")
            if setup['signal'] and setup['local_score'] >= 0.5 and candle != last_alert_candle:
                score = setup['local_score']
                ai = ({'approved': True, 'confidence_score': score,
                       'reason': 'Regola locale score >= 0.9; Gemini non consultato'}
                      if score >= 0.9 else validate_signal_with_gemini(setup))
                if ai.get('approved'):
                    setup['sl'] = setup['price'] + (-DEFAULT_SL_DOLLARS if setup['signal'] == 'BUY' else DEFAULT_SL_DOLLARS)
                    setup['tp'] = setup['price'] + (DEFAULT_TP_DOLLARS if setup['signal'] == 'BUY' else -DEFAULT_TP_DOLLARS)
                    payload = dict(symbol=SYMBOL, signal_type=setup['signal'], entry_price=setup['price'],
                                   sl_price=setup['sl'], tp_price=setup['tp'], rsi=setup['rsi'],
                                   ai_score=ai['confidence_score'], ai_reason=ai['reason'], status='APPROVED')
                    save_bounce_signal(payload)
                    last_alert_candle = candle  # avoid repeated alert on same closed candle within this process
                    send_bounce_telegram_alert(setup, ai)
        except Exception as exc:
            log.exception('Scan fallito: %s', exc)
            try:
                save_bot_status(message=f'Dati non aggiornati: {type(exc).__name__}: {str(exc)[:100]}')
            except Exception:
                log.exception('Impossibile salvare lo stato di errore')
        time.sleep(poll_seconds)

if __name__ == '__main__':
    Thread(target=serve, daemon=True).start()
    run()
