


import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY")) 

# फॉलबॅक फंक्शन (स्थानिक FAQ)
def fallback_response(prompt: str) -> str:
    query = prompt.lower()
    if "भात" in query or "तांदूळ" in query:
        return "🌾 भात लागवड खरीप हंगामात (जून-ऑक्टोबर) करावी. चिकणमाती जमीन योग्य."
    elif "कांदा" in query:
        return "🧅 कांदा रब्बी हंगामात (ऑक्टोबर-मार्च) लावावा. साठवणूक कोरड्या जागी करावी."
    elif "सेंद्रिय खत" in query or "जैविक खत" in query:
        return "🌱 गांडूळ खत, शेणखत, कंपोस्ट ही उत्तम सेंद्रिय खते आहेत."
    elif "कीटक" in query:
        return "🐛 निंबोळी अर्क, लसूण-मिरची फवारणी, जैविक कीटकनाशके वापरा."
    elif "पाणी" in query or "सिंचन" in query:
        return "💧 ठिबक सिंचनाने पाणी वाचते. पिकानुसार पाणी व्यवस्थापन करा."
    elif "माती" in query:
        return "🟫 माती परीक्षण करून खतांचा वापर करा. सेंद्रिय पदार्थ वाढवा."
    elif "हवामान" in query:
        return "⛅ 'Krushi Mitra' मध्ये '🌤️ हवामान सल्ला' पेजवर तुम्ही शहराचे नाव टाकून लाईव्ह हवामान पाहू शकता."
    else:
        return "🤖 मी फक्त शेतीविषयक प्रश्नांची उत्तरे देतो. कृपया भात, कांदा, सेंद्रिय खत, कीटक, पाणी, माती, किंवा हवामान याबद्दल विचारा."

def get_ai_response(prompt: str) -> str:
    """Gemini API वापरून उत्तर मिळवा; अपयश आल्यास फॉलबॅक."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')  # किंवा 'gemini-2.5-flash'
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI error: {e}")
        return fallback_response(prompt)
    

