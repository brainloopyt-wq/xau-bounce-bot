import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_bounce_telegram_alert(setup, ai):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError('Configura TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID')
    text = (f"XAU/USD - {setup['signal']} (segnale indicativo)\n"
            f"Entrata: {setup['price']:.2f}\nLivello: {setup['level_price']:.2f}\n"
            f"RSI: {setup['rsi']} | Score: {setup['local_score']}\n"
            f"SL: {setup['sl']:.2f} | TP: {setup['tp']:.2f}\n"
            f"Validazione: {ai['reason']}\nFonte: Twelve Data, non quotazione XTB")
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                      json={'chat_id': TELEGRAM_CHAT_ID, 'text': text}, timeout=12)
    r.raise_for_status()
    if not r.json().get('ok'):
        raise RuntimeError(f'Telegram ha rifiutato il messaggio: {r.text[:250]}')
