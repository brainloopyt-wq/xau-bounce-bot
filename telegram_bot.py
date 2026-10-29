import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_demo_alert(setup, validation):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError('Credenziali Telegram mancanti')
    msg = (f"🧪 BOUNCE BOT V2 — SEGNALE DEMO / NON ESEGUIRE AUTOMATICAMENTE\n"
           f"{setup['signal']} {setup['strategy']} XAU/USD | M15 {setup['m15_trend']}\n"
           f"Candela M5: {setup['candle']}\nEntrata indicativa: {setup['price']:.2f}\n"
           f"SL: {setup['sl']:.2f} | TP1: {setup['tp1']:.2f} | TP2: {setup['tp2']:.2f}\n"
           f"ATR: {setup['atr']:.2f} | Score tecnico: {setup['local_score']:.2f}\n"
           f"AI: {validation['label']}\n"
           f"Dettaglio AI: {validation['reason']}\n"
           'Trailing stop: solo regola proposta, NON monitorato automaticamente.\n'
           'Prezzi Twelve Data diversi da XTB; rischio 15 EUR non verificato (lotto/spread).')
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                      json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg}, timeout=12)
    r.raise_for_status()
    if not r.json().get('ok'):
        raise RuntimeError('Telegram non ha accettato il messaggio')


def send_test_message():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError('Credenziali Telegram mancanti')
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                      json={'chat_id': TELEGRAM_CHAT_ID,
                            'text': '🧪 BOUNCE BOT V2 — TEST\n✅ Telegram collegato. Nessun segnale di trading.'}, timeout=12)
    r.raise_for_status()
    if not r.json().get('ok'):
        raise RuntimeError('Telegram non ha accettato il test')
