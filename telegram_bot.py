import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_bounce_telegram_alert(signal_data: dict, ai_analysis: dict):
    emoji = "🟢 BUY (RIMBALZO)" if signal_data['signal'] == "BUY" else "🔴 SELL (RIMBALZO)"
    
    message = (
        f"⚡ *[BOUNCE BOT] SEGNALE MEAN-REVERSION* ⚡\n\n"
        f"*Strumento:* XAU/USD (Oro)\n"
        f"*Operazione:* {emoji}\n"
        f"*Prezzo Entrata:* `${signal_data['price']:.2f}`\n"
        f"*Livello Testato:* `${signal_data['level_price']:.2f}`\n"
        f"*RSI (14):* {signal_data['rsi']}\n"
        f"*Score Tecnico:* {signal_data['local_score']}\n\n"
        f"🎯 *TP Suggerito:* `${signal_data['tp']:.2f}`\n"
        f"🛑 *SL Suggerito:* `${signal_data['sl']:.2f}`\n\n"
        f"🤖 *Validazione:* {'✅ APPROVATO' if ai_analysis['approved'] else '❌ RIFIUTATO'}\n"
        f"📊 *Confidenza:* {ai_analysis['confidence_score'] * 100:.0f}%\n"
        f"📝 *Nota:* {ai_analysis['reason']}"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[TELEGRAM ERROR] Errore nell'invio del messaggio: {e}")