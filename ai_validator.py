import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY


def validate_signal_with_gemini(setup):
    if not GEMINI_API_KEY:
        return {'approved': False, 'available': False, 'reason': 'GEMINI_API_KEY assente'}
    try:
        prompt = ('Valuta criticamente questo setup tecnico di XAU/USD, senza considerare '
                  'confidence_score una probabilita statistica. Rispondi solo in JSON '
                  'con approved boolean, reason string. Dati: ' + json.dumps(setup, ensure_ascii=False))
        response = genai.Client(api_key=GEMINI_API_KEY).models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json'))
        value = json.loads(response.text)
        if type(value.get('approved')) is not bool:
            raise ValueError('approved non booleano')
        return {'approved': value['approved'], 'available': True, 'reason': str(value.get('reason', ''))[:250]}
    except Exception as exc:
        return {'approved': False, 'available': False, 'reason': f'Gemini non disponibile: {type(exc).__name__}'}
