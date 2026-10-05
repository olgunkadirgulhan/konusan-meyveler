"""Meyve kadrosu (orijinal karakterler). Renkler 0-1 RGB.

shape      fruit.py'deki gövde biçimi
w, h       gövde boyu (birim; 1 birim = FORMATS[...]['s'] piksel)
face_y     yüz merkezinin gövde merkezine göre dikey kayması (birim, + aşağı)
voice      Microsoft sinir ağı sesi (Azure ve edge-tts'de aynı isim)
pitch      Hz kayması: anime tarzı için hepsi yukarı çekili (Çilek referans: Emel +55Hz), rate = konuşma hızı
piper      yedek ses (Piper, Türkçe) + perde çarpanı
"""

CAST = {
    'limon': {
        'name': 'Limon', 'shape': 'lemon', 'w': 46, 'h': 54, 'face_y': 2, 'scale': 0.95,
        'color': (1.0, 0.86, 0.12), 'limb': (0.86, 0.66, 0.05), 'iris': (0.25, 0.55, 0.15), 'accent': (1.0, 0.9, 0.2),
        'voice': 'tr-TR-EmelNeural', 'pitch': '+45Hz', 'rate': '+8%', 'piper': ('tr_TR-dfki-medium', 1.25),
        'bible': 'Limon (sarı, ekşi suratlı): herkese laf sokar, sivri dilli, ama içten içe çok duygusal; '
                 '"ekşi" denince alınır, "aslında C vitamini kraliçesiyim" der.',
    },
    'domates': {
        'name': 'Domates', 'shape': 'tomato', 'w': 54, 'h': 46, 'face_y': 3, 'scale': 1.0,
        'color': (0.92, 0.16, 0.12), 'limb': (0.2, 0.55, 0.18), 'iris': (0.45, 0.25, 0.1), 'accent': (1.0, 0.35, 0.3),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+38Hz', 'rate': '+8%', 'piper': ('tr_TR-fahrettin-medium', 1.08),
        'bible': 'Domates (kırmızı, tepesinde yeşil yaprak): kimlik krizinde; botanik olarak meyve olduğu halde '
                 'herkes ona sebze diyor, buna çıldırıyor. Dramatik, kendini her yemeğin yıldızı sanır.',
    },
    'muz': {
        'name': 'Muz', 'shape': 'banana', 'w': 34, 'h': 66, 'face_y': 0, 'scale': 1.0,
        'color': (1.0, 0.88, 0.25), 'limb': (0.55, 0.42, 0.15), 'iris': (0.4, 0.25, 0.1), 'accent': (1.0, 0.92, 0.3),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+22Hz', 'rate': '-2%', 'piper': ('tr_TR-fettah-medium', 0.97),
        'bible': 'Muz (sarı, kavisli): tembel, rahat, her şeyi potasyuma bağlar; üstünde kahverengi lekeler çıkınca '
                 '"yaşlanıyorum" diye panikler.',
    },
    'karpuz': {
        'name': 'Karpuz', 'shape': 'watermelon', 'w': 62, 'h': 56, 'face_y': 2, 'scale': 1.02,
        'color': (0.42, 0.7, 0.28), 'limb': (0.16, 0.42, 0.14), 'iris': (0.35, 0.2, 0.1), 'accent': (1.0, 0.35, 0.42),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+8Hz', 'rate': '-4%', 'piper': ('tr_TR-fahrettin-medium', 0.86),
        'bible': 'Karpuz (iri, çizgili yeşil): kendini yazın kralı ilan eder, şişman ama alıngan; "içim kıpkırmızı, '
                 'kalbim büyük" der, aslında çok korkak.',
    },
    'cilek': {
        'name': 'Çilek', 'shape': 'strawberry', 'w': 44, 'h': 50, 'face_y': 3, 'scale': 0.88,
        'color': (0.93, 0.12, 0.2), 'limb': (0.22, 0.6, 0.2), 'iris': (0.15, 0.4, 0.6), 'accent': (1.0, 0.4, 0.6),
        'voice': 'tr-TR-EmelNeural', 'pitch': '+55Hz', 'rate': '+10%', 'piper': ('tr_TR-dfki-medium', 1.35),
        'bible': 'Çilek (kırmızı, benekli, yeşil taçlı): fenomen; sürekli selfie çeker, takipçi sayısıyla övünür, '
                 'pastaların üstünde olmayı "kariyer" sayar.',
    },
    'sogan': {
        'name': 'Soğan', 'shape': 'onion', 'w': 50, 'h': 54, 'face_y': 6, 'scale': 0.98,
        'color': (0.86, 0.52, 0.28), 'limb': (0.62, 0.36, 0.2), 'iris': (0.35, 0.2, 0.1), 'accent': (1.0, 0.65, 0.35),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+16Hz', 'rate': '+2%', 'piper': ('tr_TR-fettah-medium', 0.92),
        'bible': 'Soğan (kat kat kabuklu): huysuz, herkesi ağlattığı için dışlanıyor; aslında katman katman '
                 'duyguları var, en çok kendisi ağlar.',
    },
    'ananas': {
        'name': 'Ananas', 'shape': 'pineapple', 'w': 44, 'h': 56, 'face_y': 2, 'scale': 1.02,
        'color': (0.95, 0.7, 0.18), 'limb': (0.62, 0.42, 0.12), 'iris': (0.2, 0.45, 0.2), 'accent': (1.0, 0.8, 0.25),
        'voice': 'fr-FR-RemyMultilingualNeural', 'pitch': '+35Hz', 'rate': '+4%', 'piper': ('tr_TR-fahrettin-medium', 1.0),
        'bible': 'Ananas (dikenli taçlı, yabancı aksanlı): tropik adalardan gelmiş havalı turist; her şeyi '
                 '"bizim adada" diye kıyaslar, pizzaya konulmayı onur meselesi yapar.',
    },
    'avokado': {
        'name': 'Avokado', 'shape': 'avocado', 'w': 44, 'h': 58, 'face_y': 6, 'scale': 0.98,
        'color': (0.28, 0.4, 0.14), 'limb': (0.2, 0.28, 0.1), 'iris': (0.35, 0.22, 0.1), 'accent': (0.7, 0.9, 0.35),
        'voice': 'fr-FR-VivienneMultilingualNeural', 'pitch': '+38Hz', 'rate': '+4%', 'piper': ('tr_TR-dfki-medium', 1.2),
        'bible': 'Avokado (koyu yeşil, armut biçimli, yabancı aksanlı): pahalı ve kibirli; fiyatıyla övünür, '
                 '"brunch" der, ama ya hep sert ya hep fazla olgun, tam kıvamı hiç tutturamaz.',
    },
    'portakal': {
        'name': 'Portakal', 'shape': 'orange', 'w': 52, 'h': 50, 'face_y': 2, 'scale': 1.0,
        'color': (1.0, 0.55, 0.08), 'limb': (0.85, 0.38, 0.02), 'iris': (0.3, 0.5, 0.2), 'accent': (1.0, 0.6, 0.1),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+48Hz', 'rate': '+12%', 'piper': ('tr_TR-fahrettin-medium', 1.04),
        'bible': 'Portakal (turuncu, yapraklı): aşırı enerjik spor hocası; her şeye C vitamini önerir, '
                 'bağırarak motive eder, kendi kabuğunu soyamaz.',
    },
    'biber': {
        'name': 'Acı Biber', 'shape': 'pepper', 'w': 32, 'h': 66, 'face_y': -3, 'scale': 1.0,
        'color': (0.9, 0.08, 0.06), 'limb': (0.18, 0.5, 0.15), 'iris': (0.4, 0.2, 0.1), 'accent': (1.0, 0.25, 0.1),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+42Hz', 'rate': '+15%', 'piper': ('tr_TR-fettah-medium', 1.1),
        'bible': 'Acı Biber (kırmızı, uzun): çabuk parlayan, ateşli, sinirli; "bana dokunan yanar" der, '
                 'ama bir bardak süt görünce korkar.',
    },
    'salatalik': {
        'name': 'Salatalık', 'shape': 'cucumber', 'w': 30, 'h': 70, 'face_y': -6, 'scale': 1.0,
        'color': (0.25, 0.55, 0.2), 'limb': (0.16, 0.38, 0.12), 'iris': (0.25, 0.4, 0.2), 'accent': (0.5, 0.95, 0.45),
        'voice': 'tr-TR-AhmetNeural', 'pitch': '+28Hz', 'rate': '-6%', 'piper': ('tr_TR-fettah-medium', 0.98),
        'bible': 'Salatalık (uzun, yeşil, sivilceli): aşırı sakin ve "cool"; yüzde 95 su olduğuyla övünür, '
                 'herkese "sakin ol" der, gözüne konulmaktan nefret eder.',
    },
}

EMOTIONS = ['neutral', 'happy', 'angry', 'shock', 'cry', 'nervous', 'sad', 'smug', 'confused', 'excited', 'suspicious']
POSES = ['standing', 'hips', 'arms_crossed', 'pointing', 'shrug', 'celebrate', 'facepalm', 'thinking', 'phone', 'fist',
         'crying', 'wave']
# aksiyon: replikten sonra olur ("target" = etkilenen karakter)
ACTIONS = ['slap', 'faint', 'run_away', 'jump', 'spin', 'dramatic_zoom', 'rimshot', 'shiver', 'roll_away', 'grabbed',
           'squish']
SFX = ['slap', 'whoosh', 'boing', 'pop', 'thud', 'ding', 'crash', 'rimshot', 'sting', 'buzz', 'gasp_hit', 'squish',
       'blender']


def bible():
    return '\n'.join('- id "%s": %s' % (k, v['bible']) for k, v in CAST.items())
