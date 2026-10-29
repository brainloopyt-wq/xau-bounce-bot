import os
SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '').strip()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
TWELVEDATA_API_KEY = os.getenv('TWELVEDATA_API_KEY', '').strip()
SYMBOL = 'XAU/USD'
SCAN_INTERVAL = max(300, int(os.getenv('SCAN_INTERVAL', '300')))
MIN_SCORE = float(os.getenv('V2_MIN_SCORE', '0.70'))
CAPITAL_EUR = 3000.0
RISK_EUR = 15.0
ATR_STOP_MULT = 1.5
TP1_R = 1.5
TP2_R = 2.5

# Soglie di QUALITA TECNICA, non probabilita di successo.
SCORE_A = float(os.getenv('V2_SCORE_A', '0.85'))
SCORE_B = float(os.getenv('V2_SCORE_B', '0.65'))
GEMINI_DAILY_LIMIT = max(0, int(os.getenv('V2_GEMINI_DAILY_LIMIT', '10')))
