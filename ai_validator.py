import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

def validate_signal_with_gemini(setup: dict) -> dict:
    """
    Valida il segnale con Gemini AI (chiamato solo se lo score locale rientra nella zona grigia).
    """
    if not GEMINI_API_KEY:
        print("[AI] API Key mancante. Uso fallback matematico.")
        return mathematical_fallback(setup)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        Sei un esperto trader di scalping su XAU/USD (Oro).
        Valuta se questo setup di Mean-Reversion ha un'alta probabilità di successo:
        
        - Direzione: {setup['signal']}
        - Prezzo Corrente: ${setup['price']}
        - Livello Chiave S/R Testato: ${setup['level_price']}
        - RSI (14): {setup['rsi']}
        - Punteggio Tecnico Locale: {setup['local_score']}
        
        Rispondi ESCLUSIVAMENTE con un JSON valido nel seguente formato:
        {{
            "approved": true/false,
            "confidence_score": 0.85,
            "reason": "Spiegazione sintetica"
        }}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        return result

    except Exception as e:
        print(f"[AI ERROR] Errore Gemini API: {e}. Attivazione Fallback.")
        return mathematical_fallback(setup)


def mathematical_fallback(setup: dict) -> dict:
    rsi = setup['rsi']
    direction = setup['signal']
    
    if direction == "BUY" and rsi <= 35:
        return {"approved": True, "confidence_score": 0.75, "reason": "Fallback: RSI confermato in zona di ipervenduto."}
    elif direction == "SELL" and rsi >= 65:
        return {"approved": True, "confidence_score": 0.75, "reason": "Fallback: RSI confermato in zona di ipercomprato."}
    
    return {"approved": False, "confidence_score": 0.40, "reason": "Fallback: Condizioni di spinta insufficienti."}