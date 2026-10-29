import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

def validate_signal_with_gemini(setup: dict) -> dict:
    if not GEMINI_API_KEY:
        return {'approved': False, 'confidence_score': 0.0, 'reason': 'Gemini non configurato'}
    try:
        prompt = ('Valuta questo setup tecnico di XAU/USD, senza promettere rendimenti. '
                  'Rispondi solo con JSON: approved boolean, confidence_score tra 0 e 1, reason string. '
                  + json.dumps(setup, ensure_ascii=False))
        response = genai.Client(api_key=GEMINI_API_KEY).models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json'))
        result = json.loads(response.text)
        confidence = float(result['confidence_score'])
        if not 0 <= confidence <= 1 or not isinstance(result['approved'], bool):
            raise ValueError('Risposta Gemini non valida')
        return {'approved': result['approved'], 'confidence_score': confidence,
                'reason': str(result.get('reason', ''))[:500]}
    except Exception as exc:
        return {'approved': False, 'confidence_score': 0.0,
                'reason': f'Gemini non disponibile: {type(exc).__name__}'}
