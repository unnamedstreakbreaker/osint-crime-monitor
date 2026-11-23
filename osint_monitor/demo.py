"""Synthetic sample data so the pipeline can be demonstrated offline.

All headlines are invented. They are shaped like real regional news so the
classifier, clustering and trend logic have something realistic to chew on.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .fetcher import NewsItem

# (hours_ago, title, summary, source)
_SAMPLES = [
    # --- last 24h -----------------------------------------------------------
    (3, "Retired official loses Rs 1.2 crore in 'digital arrest' scam in Visakhapatnam",
     "Fraudsters posing as CBI officers kept the victim on a video call for two days and made him transfer savings to mule accounts.", "Sample Daily"),
    (5, "Vizag pensioner duped of Rs 1.2 crore by fake CBI officers in digital arrest fraud",
     "Cyber crime police in Visakhapatnam have registered a case and are tracing the mule accounts.", "Sample Times"),
    (6, "Cyberabad police bust inter-state gang running fake trading app, 9 arrested",
     "The gang lured victims through WhatsApp groups promising high returns on a fake investment app; losses estimated at Rs 18 crore.", "Sample Express"),
    (8, "250 kg ganja seized near Paderu, two vehicles impounded",
     "Police intercepted the consignment bound for Maharashtra under the NDPS Act in Alluri Sitharama Raju district.", "Sample Daily"),
    (10, "Exchange of fire between Greyhounds and Maoists in Mulugu forest",
     "No casualties reported among security forces; combing operations continue in the area.", "Sample Chronicle"),
    (12, "Section 163 imposed in parts of Palnadu after clash between two groups",
     "Prohibitory orders were imposed after stone pelting during a local festival; additional forces deployed.", "Sample Times"),
    (14, "Hyderabad police warn public about new courier scam using AI voice clone",
     "Advisory says fraudsters use AI voice clone of relatives claiming a parcel with drugs was seized.", "Sample Express"),
    (16, "Red sanders logs worth Rs 2 crore seized in Tirupati district",
     "Task force personnel caught smugglers transporting red sanders logs from Seshachalam forest.", "Sample Daily"),
    (18, "Chain snatching gang arrested in Rachakonda, 40 tolas gold recovered",
     "The gang targeted elderly women walking in the early morning in LB Nagar and Uppal.", "Sample Chronicle"),
    (20, "Nellore techie loses Rs 14 lakh in part-time job task scam",
     "Victim was asked to like videos and later invest in tasks via a fake app; cyber crime case registered.", "Sample Times"),
    (22, "Warangal: youth stabbed to death over land dispute",
     "Police registered a murder case and formed special teams to nab the accused.", "Sample Express"),
    (23, "Karimnagar police seize 1,200 bags of PDS rice being smuggled to Maharashtra", "", "Sample Daily"),
    # --- last 7 days (outside 24h) -----------------------------------------
    (30, "Two held for operating mule accounts for cyber criminals in Guntur",
     "Accused opened bank accounts and sold them to a cyber fraud network.", "Sample Times"),
    (40, "Kakinada woman loses Rs 32 lakh to fake stock trading scam", "Cyber crime police registered a case.", "Sample Daily"),
    (52, "MDMA worth Rs 40 lakh seized in Madhapur, drug peddler arrested",
     "Cyberabad narcotics wing seized the drugs at a party; NDPS case booked.", "Sample Express"),
    (60, "Sextortion racket targeting students busted in Vijayawada", "Fake profiles were used to lure victims on social media.", "Sample Chronicle"),
    (75, "Digital arrest scam: Hyderabad doctor loses Rs 2.5 crore",
     "Fraudsters posed as ED officials and claimed his Aadhaar was linked to money laundering.", "Sample Daily"),
    (90, "Ganja cultivation in 5 acres destroyed in Bhadradri Kothagudem", "Excise and police conducted a joint raid.", "Sample Times"),
    (100, "APK file fraud: Anantapur farmer loses Rs 6 lakh after clicking fake PM Kisan link",
     "Fraudsters sent a malicious APK through WhatsApp and gained access to his phone.", "Sample Express"),
    (115, "Maoist militia member surrenders before Khammam police", "", "Sample Chronicle"),
    (130, "Fake currency notes worth Rs 5 lakh seized in Kurnool, gang busted", "", "Sample Daily"),
    (140, "Cyber fraud: Siddipet man loses Rs 9 lakh in loan app harassment case",
     "Loan app agents morphed photos and threatened the victim.", "Sample Times"),
    (150, "Dowry harassment: woman ends life in Nalgonda, husband arrested", "", "Sample Express"),
    (160, "Hyderabad: robbery at jewellery shop in Old City, gang flees with gold", "", "Sample Chronicle"),
    # --- previous week (8-14 days ago) -------------------------------------
    (180, "Online fraud: Tirupati trader loses Rs 4 lakh via OTP scam", "Cyber crime case registered.", "Sample Daily"),
    (200, "Ganja smuggling: 120 kg seized near Vizianagaram", "NDPS case registered.", "Sample Times"),
    (220, "Exchange of fire with Maoists in Bhadradri Kothagudem; IED recovered", "", "Sample Express"),
    (240, "Murder in Kadapa over financial dispute; accused surrenders", "", "Sample Chronicle"),
    (260, "Protest turns violent in Adilabad, lathi charge by police", "", "Sample Daily"),
    (280, "Drugs seized at Shamshabad airport, passenger arrested under NDPS Act", "Heroin concealed in baggage.", "Sample Times"),
    (300, "Red sanders smuggling bid foiled in Annamayya district", "", "Sample Express"),
    (320, "Kidnap case solved in Eluru within 12 hours", "", "Sample Chronicle"),
]


def sample_items(now: datetime, seed: int = 7) -> list[NewsItem]:
    rnd = random.Random(seed)
    items = []
    for i, (hours_ago, title, summary, source) in enumerate(_SAMPLES):
        items.append(NewsItem(
            title=title, summary=summary, source=source, feed="demo",
            link=f"https://example.org/demo/{i}",
            published=now - timedelta(hours=hours_ago, minutes=rnd.randint(0, 50)),
        ))
    return items
