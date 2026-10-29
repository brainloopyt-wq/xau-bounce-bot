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
    """Salva lo stato corrente su Supabase per la dashboard web."""
    try:
        payload = {
            "id": 1,
            "symbol": SYMBOL,
            "last_price": status_data.get("price", 0),
            "rsi": status_data.get("rsi", 0),
            "local_score": status_data.get("local_score", 0),
            "status_message": status_data.get("message", "In esecuzione..."),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        db_client.table("bot_status").upsert(payload).execute()
    except Exception as e:
        print(f"[SUPABASE ERROR] {e}")

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

# --- CONNETTORE NATIVO XTB WEBSOCKET ---
def fetch_xtb_market_data() -> pd.DataFrame:
    """Apre una connessione WebSocket verso XTB Demo, effettua il login e recupera i dati M5 per GOLD."""
    try:
        ws = websocket.create_connection(XTB_WS_URL, timeout=10)
        
        # 1. Login
        login_cmd = {
            "command": "login",
            "arguments": {
                "userId": XTB_USER_ID,
                "password": XTB_PASSWORD
            }
        }
        ws.send(json.dumps(login_cmd))
        login_res = json.loads(ws.recv())
        
        if not login_res.get("status"):
            print(f"[XTB ERROR] Login fallito: {login_res.get('errorDescr', 'Sconosciuto')}")
            ws.close()
            return pd.DataFrame()

        # 2. Richiesta Chart (Candele M5 per GOLD / XAUUSD)
        start_time = int((time.time() - (12 * 3600)) * 1000)
        chart_cmd = {
            "command": "getChartLastRequest",
            "arguments": {
                "info": {
                    "period": 5,
                    "start": start_time,
                    "symbol": "GOLD"
                }
            }
        }
        ws.send(json.dumps(chart_cmd))
        chart_res = json.loads(ws.recv())

        # 3. Logout
        logout_cmd = {"command": "logout"}
        ws.send(json.dumps(logout_cmd))
        ws.close()

        if not chart_res.get("status"):
            print(f"[XTB ERROR] Errore recupero grafico GOLD: {chart_res}")
            return pd.DataFrame()

        rate_infos = chart_res.get("returnData", {}).get("rateInfos", [])
        if not rate_infos:
            print("[XTB] Nessuna candela ricevuta per GOLD.")
            return pd.DataFrame()

        # 4. Parsing Dati OHLCV
        parsed_data = []
        for r in rate_infos:
            open_p = r["open"] / 100.0 if "open" in r else 0
            close_p = (r["open"] + r["close"]) / 100.0 if "close" in r else open_p
            high_p = (r["open"] + r["high"]) / 100.0 if "high" in r else open_p
            low_p = (r["open"] + r["low"]) / 100.0 if "low" in r else open_p
            
            parsed_data.append({
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
                'volume': r.get("vol", 0)
            })

        df = pd.DataFrame(parsed_data).dropna()
        return df

    except Exception as e:
        print(f"[XTB EXCEPTION]: {e}")
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
