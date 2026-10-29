import os
import time
import json
import websocket
import pandas as pd
from datetime import datetime, timezone
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import dai moduli del Bounce Bot
from indicators import analyze_scalp_setup
from ai_validator import validate_signal_with_gemini
from db import save_bounce_signal
from telegram_bot import send_bounce_telegram_alert
from config import DEFAULT_SL_DOLLARS, DEFAULT_TP_DOLLARS, SYMBOL

# Credenziali XTB & Supabase dalle Environment Variables
XTB_USER_ID = os.environ.get("XTB_USER_ID", "21803137")
XTB_PASSWORD = os.environ.get("XTB_PASSWORD", "Joussefcarlo2706!")
XTB_WS_URL = "wss://ws.xtb.com/demo"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wgliaidollibufxesvqi.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndnbGlhaWRvbGxpYnVmeGVzdnFpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI4NDU5OTMsImV4cCI6MjEwODQyMTk5M30.Rld18wsMSHlWu35mDXqfWxAYj505aRZhhWMbJf4EYMQ")

from supabase import create_client
db_client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_bot_status(status_data):
    """Salva o inserisce lo stato corrente su Supabase con gestione degli errori."""
    try:
        payload = {
            "id": 1,
            "symbol": SYMBOL,
            "last_price": float(status_data.get("price", 0)),
            "rsi": float(status_data.get("rsi", 0)),
            "local_score": float(status_data.get("local_score", 0)),
            "status_message": str(status_data.get("message", "In esecuzione...")),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        # Esegue l'upsert forzato sulla riga con id=1
        response = db_client.table("bot_status").upsert(payload).execute()
        print(f"[SUPABASE SUCCESS] Stato aggiornato: {payload['last_price']} | RSI: {payload['rsi']}")
    except Exception as e:
        print(f"[SUPABASE ERROR CRITICAL] Errore upsert bot_status: {e}")

# --- MINI SERVER WEB PER RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Flow-IA XAUUSD XTB Bot is active 24/7!")

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
        return

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"[WEB SERVER] In ascolto sulla porta {port}...")
    server.serve_forever()

def fetch_xtb_market_data() -> pd.DataFrame:
    """Scarica candele M5 per XAU/USD con debug e fallback pulito."""
    try:
        url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles?count=50&granularity=M5"
        response = requests.get(url, timeout=10)
        
        print(f"[DEBUG DATI] Status HTTP: {response.status_code}")
        
        if response.status_code != 200:
            return pd.DataFrame()
            
        data = response.json()
        candles = data.get('candles', [])
        print(f"[DEBUG DATI] Candele ricevute: {len(candles)}")
        
        if not candles:
            return pd.DataFrame()
            
        parsed_data = []
        for c in candles:
            mid = c.get('mid', {})
            if mid:
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
        print(f"[DEBUG ERRORE EXCEPTION]: {e}")
        return pd.DataFrame()



def run_bounce_bot():
    print(f"🚀 Bounce Bot XTB (XAU/USD) Avviato con successo...")
    
    while True:
        try:
            # 1. Recupero Dati di Mercato direttamente da XTB
            df = fetch_xtb_market_data()
            
            if df.empty or len(df) < 20:
                print("[DATI] Dati XTB insufficienti o mercato chiuso, attesa...")
                save_bot_status({
                    "price": 0,
                    "rsi": 0,
                    "local_score": 0,
                    "message": "In attesa di dati di mercato validi da XTB..."
                })
                time.sleep(30)
                continue

            # 2. Analisi Tecnica e calcolo Local Score
            setup = analyze_scalp_setup(df)
            current_price = float(df['close'].iloc[-1])
            current_rsi = float(setup.get("rsi", 0)) if setup else 0
            score = setup.get("local_score", 0) if setup else 0
            
            status_msg = f"Scan XTB OK | RSI: {current_rsi:.1f} | Score: {score:.2f}"
            save_bot_status({
                "price": current_price,
                "rsi": current_rsi,
                "local_score": score,
                "message": status_msg
            })

            if setup and setup.get("signal"):
                print(f"[SETUP TROVATO] {setup['signal']} a ${setup['price']} (Score: {score})")
                
                if score < 0.5:
                    print("[GATE] Setup scartato localmente per score insufficiente.")
                    time.sleep(30)
                    continue
                
                if score >= 0.9:
                    ai_result = {
                        "approved": True, 
                        "confidence_score": score, 
                        "reason": "Approvazione diretta: Confluenza ad alto punteggio."
                    }
                else:
                    print(f"[AI GATE] Setup in zona grigia. Chiamata a Gemini in corso...")
                    ai_result = validate_signal_with_gemini(setup)
                
                if ai_result.get("approved"):
                    print(f"[SETUP APPROVATO] Invio notifiche e salvataggio...")
                    
                    entry_price = setup["price"]
                    if setup["signal"] == "BUY":
                        setup["sl"] = entry_price - DEFAULT_SL_DOLLARS
                        setup["tp"] = entry_price + DEFAULT_TP_DOLLARS
                    else:
                        setup["sl"] = entry_price + DEFAULT_SL_DOLLARS
                        setup["tp"] = entry_price - DEFAULT_TP_DOLLARS

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
                    send_bounce_telegram_alert(setup, ai_result)
            
            time.sleep(30)
            
        except Exception as e:
            print(f"[LOOP ERROR] Errore imprevisto nel main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    server_thread = Thread(target=run_web_server, daemon=True)
    server_thread.start()
    run_bounce_bot()
