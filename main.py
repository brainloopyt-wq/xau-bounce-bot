import os
import time
import requests
import pandas as pd
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import dai moduli del Bounce Bot
from indicators import analyze_scalp_setup
from ai_validator import validate_signal_with_gemini
from db import save_bounce_signal
from telegram_bot import send_bounce_telegram_alert
from config import DEFAULT_SL_DOLLARS, DEFAULT_TP_DOLLARS, SYMBOL

# --- MINI SERVER WEB PER MANTENERE IL BOT GRATUITO SU RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Flow-IA XAUUSD Bounce Bot is active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args):
        # Disabilita i log HTTP continui in console per mantenere l'output pulito
        return

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"[WEB SERVER] In ascolto sulla porta {port}...")
    server.serve_forever()

def fetch_market_data() -> pd.DataFrame:
    """
    Scarica i dati spot di XAU/USD da OANDA API pubblica (intervallo 5m),
    garantendo stabilità e coerenza con i grafici di TradingView.
    """
    try:
        # Endpoint pubblico OANDA v3 per le candele (Instrument: XAU_USD, Granularity: M5)
        url = "https://api-fxtrade.oanda.com/v3/instruments/XAU_USD/candles?count=100&granularity=M5"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"[MERCATO] Errore HTTP OANDA: {response.status_code}")
            return pd.DataFrame()
            
        data = response.json()
        candles = data.get('candles', [])
        
        if not candles:
            print("[DATI] Nessuna candela ricevuta da OANDA.")
            return pd.DataFrame()
            
        parsed_data = []
        for c in candles:
            if c.get('complete', True): # Prende le candele completate
                mid = c.get('mid', {})
                parsed_data.append({
                    'open': float(mid.get('o', 0)),
                    'high': float(mid.get('h', 0)),
                    'low': float(mid.get('l', 0)),
                    'close': float(mid.get('c', 0)),
                    'volume': int(c.get('volume', 0))
                })
                
        df = pd.DataFrame(parsed_data).dropna()
        return df
        
    except Exception as e:
        print(f"[ERRORE FETCH OANDA]: {e}")
        return pd.DataFrame()


def run_bounce_bot():
    print(f"🚀 Bounce Bot (XAU/USD Mean-Reversion) Avviato con successo...")
    
    while True:
        try:
            # 1. Recupero Dati di Mercato ( Yahoo Finance )
            df = fetch_market_data()
            
            if df.empty or len(df) < 20:
                print("[DATI] Dati insufficienti o mercato chiuso, attesa...")
                time.sleep(30)
                continue

            # 2. Analisi Tecnica e calcolo Local Score
            setup = analyze_scalp_setup(df)
            
            if setup["signal"]:
                score = setup["local_score"]
                print(f"[SETUP TROVATO] {setup['signal']} a ${setup['price']} (Score Locale: {score})")
                
                # RISPARMIO API - LIVELLO 1: Se il punteggio locale è basso (< 0.5), scarta subito (0 crediti spesi)
                if score < 0.5:
                    print("[GATE] Setup scartato localmente per score insufficiente.")
                    time.sleep(30)
                    continue
                
                # RISPARMIO API - LIVELLO 2: Se il setup è perfetto (score >= 0.9), bypassa l'IA
                if score >= 0.9:
                    ai_result = {
                        "approved": True, 
                        "confidence_score": score, 
                        "reason": "Approvazione diretta: Setup ad altissima confluenza (S/R + RSI + Bollinger + Volumi)."
                    }
                else:
                    # Chiamata API effettuata SOLO per la "zona grigia" (es. score tra 0.5 e 0.89)
                    print(f"[AI GATE] Setup in zona grigia. Chiamata a Gemini in corso...")
                    ai_result = validate_signal_with_gemini(setup)
                
                if ai_result.get("approved"):
                    print(f"[SETUP APPROVATO] Invio notifiche e salvataggio...")
                    
                    # Calcolo SL e TP dinamici per scalping su XAU/USD
                    entry_price = setup["price"]
                    if setup["signal"] == "BUY":
                        setup["sl"] = entry_price - DEFAULT_SL_DOLLARS
                        setup["tp"] = entry_price + DEFAULT_TP_DOLLARS
                    else:
                        setup["sl"] = entry_price + DEFAULT_SL_DOLLARS
                        setup["tp"] = entry_price - DEFAULT_TP_DOLLARS

                    # 3. Salvataggio Database Supabase (Tabella dedicata: bounce_signals)
                    db_payload = {
                        "symbol": SYMBOL,
                        "signal_type": setup["signal"],
                        "entry_price": setup["price"],
                        "sl_price": setup["sl"],
                        "tp_price": setup["tp"],
                        "rsi": setup["rsi"],
                        "ai_score": ai_result.get("confidence_score"),
                        "ai_reason": ai_result.get("reason"),
                        "status": "APPROVED"
                    }
                    save_bounce_signal(db_payload)
                    
                    # 4. Invio Notifica Telegram sul bot ufficiale
                    send_bounce_telegram_alert(setup, ai_result)
            
            # Frequenza di controllo (ogni 30 secondi)
            time.sleep(30)
            
        except Exception as e:
            print(f"[LOOP ERROR] Errore imprevisto nel main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Avvia il mini server web in background per il piano Free di Render
    server_thread = Thread(target=run_web_server, daemon=True)
    server_thread.start()
    
    # Avvia il motore di trading Bounce Bot
    run_bounce_bot()
