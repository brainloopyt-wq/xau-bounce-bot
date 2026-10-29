"""Bounce Bot V2: informational signals, Supabase, Telegram, Gemini. NO ORDERS."""
import logging
import os
import time
from datetime import datetime, timezone
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pandas as pd
import requests
from config import TWELVEDATA_API_KEY, SYMBOL, SCAN_INTERVAL, SCORE_A, SCORE_B, GEMINI_DAILY_LIMIT
from indicators import analyze_setup
from ai_validator import validate_signal_with_gemini
from db import save_bot_status, save_bounce_signal
from telegram_bot import send_demo_alert, send_test_message

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('bounce_v2')

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bounce Bot V2 online (not market feed health)')
    def log_message(self, *_):
        pass

def serve():
    ThreadingHTTPServer(('0.0.0.0', int(os.getenv('PORT', '10000'))), Handler).serve_forever()

def fetch_m5():
    if not TWELVEDATA_API_KEY:
        raise RuntimeError('TWELVEDATA_API_KEY mancante')
    # One request per scan. Derive M15 from complete, consecutive M5 candles.
    r = requests.get('https://api.twelvedata.com/time_series', params={
        'symbol': SYMBOL, 'interval': '5min', 'outputsize': 300,
        'apikey': TWELVEDATA_API_KEY, 'timezone': 'UTC', 'format': 'JSON'}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get('status') == 'error' or not data.get('values'):
        raise RuntimeError(f'Twelve Data: {str(data.get("message", data))[:200]}')
    df = pd.DataFrame(data['values'])
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['datetime', 'open', 'high', 'low', 'close'])
    df = df[df['datetime'] + pd.Timedelta(minutes=5) <= pd.Timestamp.now(tz='UTC')]
    df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
    if len(df) < 180:
        raise RuntimeError(f'Solo {len(df)} candele M5 chiuse: ne servono almeno 180')
    return df

def derive_m15(m5):
    # Align UTC quarter hours, exclude incomplete groups or missing 5m bars.
    df = m5.copy().set_index('datetime')
    grouped = df.resample('15min', label='left', closed='left')
    result = grouped.agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
    counts = grouped['close'].count()
    result = result[counts == 3].dropna().reset_index()
    if len(result) < 60:
        raise RuntimeError(f'Solo {len(result)} candele M15 complete')
    return result

def run():
    last_processed = None
    gemini_day = None
    gemini_calls_today = 0
    if os.getenv('V2_TEST_TELEGRAM_ON_START', 'false').lower() == 'true':
        try:
            send_test_message()
            log.info('Messaggio TEST Telegram inviato')
        except Exception:
            log.exception('Test Telegram fallito')
    log.info('V2 avviato: feed M5/M15, Gemini selettivo, Telegram e Supabase attivi')
    while True:
        try:
            m5 = fetch_m5()
            candle = m5['datetime'].iloc[-1].isoformat()
            if candle != last_processed:
                m15 = derive_m15(m5)
                setup = analyze_setup(m5, m15)
                log.info('M5=%s price=%.2f RSI=%.2f M15=%s strategy=%s signal=%s score=%.2f',
                         candle, setup['price'], setup['rsi'], setup['m15_trend'],
                         setup['strategy'], setup['signal'], setup['local_score'])
                save_bot_status(price=setup['price'], rsi=setup['rsi'],
                                local_score=setup['local_score'],
                                message=f'V2 feed OK | M5 {candle} | M15 {setup["m15_trend"]}')
                if setup['signal'] and setup['local_score'] >= SCORE_B:
                    score = setup['local_score']
                    if score >= SCORE_A:
                        validation = {'approved': True, 'available': True,
                                      'label': 'NON CONSULTATA — segnale tecnico A',
                                      'reason': 'Score tecnico A; nessuna richiesta Gemini'}
                    else:
                        today = datetime.now(timezone.utc).date()
                        if today != gemini_day:
                            gemini_day, gemini_calls_today = today, 0
                        if gemini_calls_today >= GEMINI_DAILY_LIMIT:
                            validation = {'approved': False, 'available': False,
                                          'reason': 'Limite giornaliero Gemini raggiunto'}
                        else:
                            # Conta anche i tentativi falliti per contenere i consumi.
                            gemini_calls_today += 1
                            validation = validate_signal_with_gemini(setup)
                        if not validation['available']:
                            validation['label'] = 'NON DISPONIBILE — segnale tecnico NON validato'
                        elif validation['approved']:
                            validation['label'] = 'VALIDATO DA GEMINI'
                        else:
                            validation['label'] = 'RESPINTO DA GEMINI'
                    if validation['approved'] or not validation['available']:
                        # Lo stato APPROVED indica soltanto che il segnale tecnico e stato
                        # selezionato per la notifica, NON che Gemini lo abbia approvato.
                        # La reale condizione AI viene registrata in ai_reason.
                        payload = dict(symbol=SYMBOL, signal_type=setup['signal'],
                                       entry_price=setup['price'], sl_price=setup['sl'],
                                       tp_price=setup['tp2'], rsi=setup['rsi'],
                                       ai_score=setup['local_score'],
                                       ai_reason=f"V2 {setup['strategy']} | {validation['label']} | {validation['reason']}"[:500],
                                       status='APPROVED')
                        # Un problema DB non deve impedire la notifica Telegram.
                        try:
                            save_bounce_signal(payload)
                        except Exception:
                            log.exception('Salvataggio segnale Supabase fallito')
                        send_demo_alert(setup, validation)
                        log.info('Segnale V2 notificato: %s %s AI=%s',
                                 setup['signal'], candle, validation['label'])
                    else:
                        log.info('Gemini ha respinto il segnale: %s', validation['reason'])
                last_processed = candle
        except Exception as exc:
            log.exception('Scansione V2 fallita: %s', exc)
            try:
                save_bot_status(message=f'V2 dati non aggiornati: {type(exc).__name__}: {str(exc)[:100]}')
            except Exception:
                log.exception('Impossibile salvare lo stato di errore')
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    Thread(target=serve, daemon=True).start()
    run()
