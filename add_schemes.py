from database import SessionLocal
from models import GovScheme

db = SessionLocal()

schemes = [
    GovScheme(
        name="पीक विमा योजना",
        description="नैसर्गिक आपत्तीमुळे पिकांचे नुकसान झाल्यास विमा संरक्षण.",
        eligibility="सर्व शेतकरी",
        benefits="नुकसानीच्या 80% पर्यंत भरपाई",
        apply_link="https://pmfby.gov.in",
        category="पीक विमा",
        crop_type="सर्व",
        min_land_area=0.5
    ),
    GovScheme(
        name="ठिबक सिंचन अनुदान योजना",
        description="ठिबक सिंचन पद्धतीसाठी 50% अनुदान.",
        eligibility="लहान व सीमांत शेतकरी",
        benefits="50% अनुदान (जास्तीत जास्त ₹50,000)",
        apply_link="https://pmksy.gov.in",
        category="सिंचन",
        crop_type="भाजीपाला",
        min_land_area=1.0
    ),
    GovScheme(
        name="शेतकरी क्रेडिट कार्ड (KCC)",
        description="कमी व्याजदरात अल्पकालीन कर्ज.",
        eligibility="सर्व शेतकरी",
        benefits="3% व्याजदर, सुलभ परतफेड",
        apply_link="https://kcc.bank",
        category="कर्ज",
        crop_type=None,
        min_land_area=None
    ),
]

for scheme in schemes:
    db.add(scheme)
db.commit()
print("✅ योजना यशस्वीपणे जोडल्या गेल्या.")
db.close()