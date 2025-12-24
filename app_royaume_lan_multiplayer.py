import streamlit as st
import random
import time
import os
import pandas as pd
import json
from PIL import Image, ImageDraw
from datetime import datetime
import threading
import socket
import qrcode
from io import BytesIO
import base64

# --- CONFIGURATION ---
st.set_page_config(page_title="Royaume des Kaplas", layout="wide", page_icon="🏰")

# ==========================================
# CSS & DESIGN
# ==========================================
def local_css():
    st.markdown("""
    <style>
    /* IMPORT POLICE */
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

    /* 1. APP & COULEURS */
    .stApp {
        background-color: #fff4dc;
        color: #4a3b2a;
    }

    /* 2. POLICE MÉDIÉVALE PAR DÉFAUT */
    h1, h2, h3, h4, h5, h6, .stMarkdown, p, span, div {
        font-family: 'MedievalSharp', cursive !important;
    }

    /* 3. EXCEPTIONS : POLICE STANDARD (Pour éviter les bugs d'affichage) */
    /* Menus déroulants, inputs textuels, infobulles, alertes */
    div[data-baseweb="select"], div[data-baseweb="popover"], div[role="listbox"], option,
    input[type="text"], div[data-baseweb="toast"], div[class*="stAlert"] {
        font-family: sans-serif !important;
    }

    /* FIX CRITIQUE : Empêcher la police médiévale de casser les icônes (flèches expander, croix...) */
    .st-emotion-cache-1h9usn1 svg, .st-emotion-cache-1h9usn1 span, [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded', sans-serif !important;
        font-weight: normal !important;
    }

    /* On force aussi la police standard sur le résumé des expanders pour éviter les conflits */
    .streamlit-expanderHeader {
        font-family: sans-serif !important;
    }

    /* Titres des expanders (qui buggent souvent) */
    .streamlit-expanderHeader p {
        font-family: 'MedievalSharp', cursive !important; /* On force le médiéval ici car c'est joli */
        font-size: 1.1em;
    }

    /* 4. UI CLEANING */
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
        display: none !important;
    }
    .main .block-container { padding-top: 1rem; }

    /* 5. SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #f7e8c6;
        border-right: 2px solid #d4c5a3;
    }

    /* 6. BOUTONS */
    .stButton > button {
        background-color: #8b4513 !important;
        color: #fff4dc !important;
        border: 2px solid #5e2f0d !important;
        border-radius: 8px;
        font-family: 'MedievalSharp', cursive !important;
        font-size: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# SYSTÈME AUDIO
# ==========================================
def autoplay_audio(file_path, volume=1.0):
    """Joue un son en autoplay via HTML5 avec gestion du volume"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                # ID unique pour éviter les conflits
                uid = random.randint(1000, 99999)
                md = f"""
                    <audio id="audio_{uid}" autoplay style="display:none;">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                    <script>
                        var audio = document.getElementById("audio_{uid}");
                        audio.volume = {volume};
                    </script>
                    """
                st.markdown(md, unsafe_allow_html=True)
    except Exception as e:
        # On ne veut pas faire planter le jeu si un son manque
        print(f"Erreur audio: {e}")

def gestion_audio(data):
    # --- A. PRIORITÉ ABSOLUE : GUERRE ---
    # Si on passe en Phase 3 (Marché) et qu'il y a eu des combats en Phase 2
    if data["phase"] == 3 and data.get("trigger_sound_guerre"):
        autoplay_audio("sounds/event_guerre.mp3") # Ou un son spécifique "rapport_bataille.mp3"
        data["trigger_sound_guerre"] = False
        st.session_state.last_phase_audio = 3 # On considère la phase comme "annoncée"
        return # On s'arrête là pour ne pas jouer le son "Marché ouvert" par dessus

    # --- B. PRIORITÉ : ÉVÉNEMENTS SPÉCIAUX ---
    evt = data.get("evenement_actif")
    evt_nom = evt["nom"] if evt else None

    if "last_event_audio" not in st.session_state:
        st.session_state.last_event_audio = None

    if st.session_state.last_event_audio != evt_nom and evt_nom is not None:
        sounds_evt = {
            "Saison de la Chasse": "event_chasse.mp3",
            "Guerre": "event_guerre.mp3",
            "Attaque Surprise": "event_guerre.mp3",
            "Vol d'Ecu": "event_vol.mp3",
            "Vol de Ressource": "event_vol.mp3",
            "Passage du Roi": "event_roi.mp3",
            "Le Banquet": "event_banquet.mp3",
            "Le Monument": "event_monument.mp3",
            "L'Espion": "event_vol.mp3" # Son par défaut pour l'espion
        }
        if evt_nom in sounds_evt:
            autoplay_audio(f"sounds/{sounds_evt[evt_nom]}")

        st.session_state.last_event_audio = evt_nom
        return # Priorité à l'événement

    if evt_nom is None:
        st.session_state.last_event_audio = None

    # --- C. VARIATIONS MARCHÉ (Matin - Phase 1) ---
    if data["phase"] == 1 and st.session_state.get("last_phase_audio") != 1:
        # On vérifie si le cours du Kapla a beaucoup bougé
        old_k = data.get("cours_kapla_hier", 10)
        new_k = data["cours_kapla"]
        diff = new_k - old_k

        # Si grosse variation, on joue le son spécial AU LIEU du "Cocorico"
        if diff >= 3:
            autoplay_audio("sounds/money_up.mp3") # Inflation
            st.session_state.last_phase_audio = 1
            return
        elif diff <= -3:
            autoplay_audio("sounds/money_down.mp3") # Soldes
            st.session_state.last_phase_audio = 1
            return

    # --- D. SONS DE PHASE CLASSIQUES (Si rien d'autre) ---
    if "last_phase_audio" not in st.session_state:
        st.session_state.last_phase_audio = -1

    current_phase = data["phase"]
    if st.session_state.last_phase_audio != current_phase:
        sounds_phase = {
            1: "phase_1.mp3",
            2: "phase_2.mp3",
            3: "phase_3.mp3",
            4: "phase_4.mp3"
        }
        if current_phase in sounds_phase:
            autoplay_audio(f"sounds/{sounds_phase[current_phase]}")
        elif current_phase == 0:
             autoplay_audio("sounds/intro.mp3")

        st.session_state.last_phase_audio = current_phase

# Fichier de sauvegarde partagé
DATA_FILE = "game_data_shared.json"
LOCK = threading.Lock()

# ==========================================
# 1. CONSTANTES & ÉQUILIBRAGE
# ==========================================

# Temps
DUREE_ANNEE = 40
DUREE_SAISON = 10

# Survie
PV_BASE_MAX = 100
PV_ABSOLUTE_MAX = 250
FAIM_BASE_MAX = 100
FAIM_ABSOLUTE_MAX = 250
PENALITE_FAMINE = 40

# Marché
PRIX_REPAS_SIMPLE = 5; GAIN_FAIM_SIMPLE = 25
PRIX_PAIN_MAX = 20; GAIN_FAIM_MAX_BONUS = 5
PRIX_POTION = 15; GAIN_VIE_POTION = 10

# COURS ET PRIX
PRIX_CHAMPIGNON = 10
PRIX_GIBIER_BASE = {"Petit": 30, "Moyen": 50, "Gros": 100}

# Coûts Armée
PRIX_SOLDAT = 15
PRIX_ARCHER = 25
PRIX_CHEVALIER = 50

# Social
PRIX_MARIAGE = 50
PRIX_OUVRIER = 30
SALAIRE_OUVRIER = 5
BONUS_PROD_CONJOINT = 0.1
BONUS_PROD_ENFANT = 1.0

# Événements
PROBA_EVENEMENT = 1.0  # Probabilité qu'un événement se produise chaque jour (0.3 = 30%)

STATS_COMBAT = {
    "Soldat": {"cout": 15, "base": 10, "desc": "Fantassin", "icon": "🗡️"},
    "Archer": {"cout": 25, "base": 15, "desc": "Défenseur", "icon": "🏹"},
    "Chevalier": {"cout": 50, "base": 40, "desc": "Élite", "icon": "🐎"}
}

VALEUR_PHYSIQUE = {"enceinte": 50, "porte": 20, "tour": 15}

STATS_METIERS = {
    "Fermier": {
        "desc": "Le Manager. Recrutez pour gagner.",
        "cout_terrain": 15, "bonus_terrain": 0.2, "bonus_ouvrier": 1.5,
        "cout_fatigue": 15, "base_min": 3, "base_max": 6, "icon": "🌾"
    },
    "Bûcheron": {
        "desc": "L'Industriel. Fort tout seul.",
        "cout_terrain": 30, "bonus_terrain": 0.8, "bonus_ouvrier": 0.5,
        "cout_fatigue": 20, "base_min": 2, "base_max": 5, "icon": "🪓"
    },
    "Vigneron": {
        "desc": "L'Investisseur. Patience = Richesse.",
        "cout_terrain": 25, "bonus_terrain": 1.0, "bonus_ouvrier": 1.0,
        "cout_fatigue": 10, "base_min": 1, "base_max": 1, "icon": "🍇"
    }
}

CATALOGUE_OBJETS = {
    # --- OUTILS ---
    "Jumelles": {"prix": 40, "type": "Outil", "icon": "🔭", "desc": "Chasse : Voir 10s avant", "help": "Permet de mieux repérer le gibier."},
    "Sextant": {"prix": 70, "type": "Outil", "icon": "🧭", "desc": "Chasse : Chercher 5s avant", "help": "Navigation rapide."},
    "Petit Couteau": {"prix": 25, "type": "Outil", "icon": "🔪", "desc": "+30% gain Gibier", "help": "Augmente le rendement de la chasse."},
    "Couteau Champignon": {"prix": 10, "type": "Outil", "icon": "🍄", "desc": "Récolte bonus", "help": "Permet de ramasser des champignons."},
    "Clous et Marteau": {"prix": 15, "type": "Outil", "icon": "🔨", "desc": "1 unité de Pâte à Fixe (IRL)", "help": "Autorise l'utilisation de pâte à fixe pour vos constructions.", "stackable": True},

    # --- PROTECTION / PROD ---
    "Coffre-fort": {"prix": 80, "type": "Protection", "icon": "🔒", "desc": "Protège du vol", "help": "Empêche le vol d'écus la nuit."},
    "Charrette": {"prix": 35, "type": "Production", "icon": "🛒", "desc": "+2 Prod brute", "help": "Bonus de production."},
    "Cheval": {"prix": 60, "type": "Prestige", "icon": "🐎", "desc": "Prestige", "help": "Un signe de richesse."},

    # --- ARMURES (Bonus Défense) ---
    "Armure Commune": {"prix": 20, "type": "Armure", "icon": "⭐️", "desc": "+5 Défense", "help": "Protection basique.", "bonus_def": 5, "stackable": True},
    "Armure Mythique": {"prix": 50, "type": "Armure", "icon": "⚜️", "desc": "+15 Défense", "help": "Protection avancée.", "bonus_def": 15, "stackable": True},
    "Armure Légendaire": {"prix": 100, "type": "Armure", "icon": "🔱", "desc": "+35 Défense", "help": "Protection ultime.", "bonus_def": 35, "stackable": True},

    # --- BOUCLIERS (Bonus Défense) ---
    "Bouclier Commun": {"prix": 15, "type": "Bouclier", "icon": "⭐️", "desc": "+5 Défense", "help": "Petit bouclier en bois.", "bonus_def": 5, "stackable": True},
    "Bouclier Mythique": {"prix": 40, "type": "Bouclier", "icon": "⚜️", "desc": "+12 Défense", "help": "Bouclier en acier trempé.", "bonus_def": 12, "stackable": True},
    "Bouclier Légendaire": {"prix": 80, "type": "Bouclier", "icon": "🔱", "desc": "+25 Défense", "help": "Égide divine impénétrable.", "bonus_def": 25, "stackable": True},

    # --- ARMES (Bonus Attaque) ---
    "Arme Commune": {"prix": 20, "type": "Arme", "icon": "⭐️", "desc": "+5 Attaque", "help": "Arme standard.", "bonus_att": 5, "stackable": True},
    "Arme Mythique": {"prix": 50, "type": "Arme", "icon": "⚜️", "desc": "+15 Attaque", "help": "Arme enchantée.", "bonus_att": 15, "stackable": True},
    "Arme Légendaire": {"prix": 100, "type": "Arme", "icon": "🔱", "desc": "+35 Attaque", "help": "Arme des dieux.", "bonus_att": 35, "stackable": True},
}

ICON_GIBIER = {"Petit": "🐇", "Moyen": "🐗", "Gros": "🐻"}

# ==========================================
# 2. GESTION DES DONNÉES
# ==========================================

def init_shared_data():
    if not os.path.exists(DATA_FILE):
        default = {
            "joueurs": [],
            "phase": 0,
            "jour": 1,
            "meteo": "Beau temps",
            "cours_kapla": 10, "cours_ble": 5,
            "cours_gibier": {"Petit": 30, "Moyen": 50, "Gros": 100},
            "cours_kapla_hier": 10, "cours_ble_hier": 5,
            "logs_guerre": [],
            "evenement_actif": None,
            "jour_evenement": None,  # Jour où l'événement a été déclenché (pour garantir 1 seul par jour)
            "fin_partie": False,
            "joueurs_prets": [],
            "last_update": str(datetime.now())
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=4)

def load_data():
    with LOCK:
        if not os.path.exists(DATA_FILE): init_shared_data()
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return None

def save_data(data):
    with LOCK:
        data["last_update"] = str(datetime.now())
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# ==========================================
# 3. HELPER CLASSES & FONCTIONS
# ==========================================

def charger_carte_background():
    """Charge la carte depuis Carte.jpg ou crée un fond par défaut"""
    if os.path.exists("Carte.jpg"):
        try:
            img = Image.open("Carte.jpg")
            return img.resize((600, 400))
        except:
            pass
    # Fallback
    img = Image.new("RGB", (600, 400), (240, 230, 200))
    return img

def generer_carte(joueurs):
    fond = charger_carte_background().copy()
    draw = ImageDraw.Draw(fond)
    w, h = fond.size
    
    
    # Dessiner les joueurs et leurs constructions
    for j in joueurs:
        if j.get("vie", 0) <= 0: continue
        x, y = j.get("x", 50), j.get("y", 50)
        px, py = int((x/100)*w), int((y/100)*h)
        
        # Taille du carré selon le nombre de terrains
        nb_terrains = j.get("nb_terrains", 0)
        taille_base = 12
        taille = taille_base + (nb_terrains * 2)
        taille = min(taille, 30)  # Limite max
        
        # Couleur selon la rive
        col_fill = "#8b4513" if x < 50 else "#a0522d"  # Marron clair/foncé
        col_outline = "#daa520"  # Doré
        
        # Dessiner le carré du joueur
        draw.rectangle(
            [(px-taille//2, py-taille//2), (px+taille//2, py+taille//2)],
            fill=col_fill,
            outline=col_outline,
            width=2
        )
        
        # Nom du joueur
        draw.text((px-15, py-taille//2-15), j["nom"][:4], fill="white")
        
        # Dessiner les tours (petits cercles gris)
        nb_tours = j.get("nb_tours", 0)
        for i in range(nb_tours):
            offset_x = -8 + (i * 6)
            draw.ellipse(
                [(px+offset_x-4, py+taille//2+5), (px+offset_x+4, py+taille//2+13)],
                fill="#808080",
                outline="#555555",
                width=1
            )
    
    return fond

def get_local_ip():
    """Détecte automatiquement l'adresse IP locale de la machine (Wi-Fi ou Ethernet)"""
    try:
        # Créer une socket pour obtenir l'IP locale
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # On se connecte à une adresse externe (mais on n'envoie rien)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"

def generate_qr_code(url):
    """Génère un QR Code pour l'URL donnée"""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def draw_bar(val, max_v, color):
    pct = max(0, min(100, int((val / (max_v if max_v > 0 else 100)) * 100)))
    st.markdown(f"""<div style="background:#ddd;border-radius:4px;height:10px;width:100%;margin-bottom:5px;">
        <div style="background:{color};width:{pct}%;height:100%;border-radius:4px;"></div></div>""", unsafe_allow_html=True)

def get_saison_info(jour):
    j_annee = (jour - 1) % DUREE_ANNEE + 1
    annee = ((jour - 1) // DUREE_ANNEE) + 1
    if 1 <= j_annee <= 10: return "Printemps", "🌿", "Pluie", "#4CAF50", j_annee, annee
    elif 11 <= j_annee <= 20: return "Été", "☀️", "Soleil", "#FFC107", j_annee-10, annee
    elif 21 <= j_annee <= 30: return "Automne", "🍂", "Vent", "#FF5722", j_annee-20, annee
    else: return "Hiver", "❄️", "Neige", "#2196F3", j_annee-30, annee

def generer_conjoint(joueurs_existants):
    """Génère un conjoint unique avec un nom rigolo"""

    prenoms_h = [
        "Godefroy", "Jacquouille", "Enguerrand", "Clotaire", "Barnabé",
        "Hubert", "Raoul", "Lothaire", "Pepin", "Gontran", "Fulbert",
        "Tancrède", "Hildebert", "Gondemar", "Theodebert"
    ]
    titres_h = [
        "le Pantois", "le Mangeur de Soupe", "le Court-sur-pattes", "du Gratin",
        "le Mal-Peigné", "le Ronfleur", "des Pâquerettes", "le Borgne",
        "le Sans-Dents", "le Joyeux Drille", "de la Compta", "le Pot-de-Colle",
        "le Brave (mais pas trop)", "aux Pieds Plats", "le Fromager"
    ]

    prenoms_f = [
        "Cunégonde", "Ursule", "Pétronille", "Gertrude", "Berthe",
        "Isolde", "Gisèle", "Hildegarde", "Yolande", "Hermine",
        "Eulalie", "Gudule", "Clotilde", "Brunhilde", "Fredegonde"
    ]
    titres_f = [
        "la Bruyante", "de la Tourbière", "la Dent-Cassée", "aux Gros Sabots",
        "la Magnifique", "la Terrible", "des Champignons", "la Têtue",
        "la Grande Gueule", "de la Basse-Cour", "la Douce (faut voir)",
        "la Chipie", "au Regard Noir", "la Tisanière", "du Chaudron"
    ]

    # On essaie de trouver un nom unique (max 50 tentatives)
    for _ in range(50):
        sexe = random.choice(["H", "F"])

        if sexe == "H":
            nom_complet = f"{random.choice(prenoms_h)} {random.choice(titres_h)}"
        else:
            nom_complet = f"{random.choice(prenoms_f)} {random.choice(titres_f)}"

        # Vérification d'unicité
        est_pris = False
        if joueurs_existants:
            for j in joueurs_existants:
                c = j.get("conjoint")
                if c and c.get("nom") == nom_complet:
                    est_pris = True
                    break

        if not est_pris:
            return {"nom": nom_complet, "sexe": sexe, "jours_mariage": 0}

    # Fallback (si vraiment pas de bol)
    return {"nom": "Jean-Michel Apeuprès", "sexe": "H", "jours_mariage": 0}

class JoueurHelper:
    def __init__(self, data): self.d = data

    def get_prod_coeff(self, jour_actuel=1):
        m = self.d["metier"]
        t = self.d.get("nb_terrains", 0)
        o = self.d.get("nb_ouvriers", 0)

        stats = STATS_METIERS.get(m, STATS_METIERS["Fermier"])
        b_t = t * stats["bonus_terrain"]
        b_o = o * stats["bonus_ouvrier"]

        b_c = 0
        if self.d.get("conjoint"): b_c = 0.1 * jour_actuel
        b_e = self.d.get("enfants", 0) * BONUS_PROD_ENFANT

        base = 1.0 + b_t + b_o + b_c + b_e
        if self.d.get("bonus_banquet", 0) > 0: base *= 2
        return base

    def get_defense(self):
        # 1. Défense Armée
        armee = self.d.get("armee", {})
        da = armee.get("Soldat",0)*STATS_COMBAT["Soldat"]["base"] + \
             armee.get("Archer",0)*STATS_COMBAT["Archer"]["base"] + \
             armee.get("Chevalier",0)*STATS_COMBAT["Chevalier"]["base"]

        # 2. Défense Physique (Bâtiments)
        phy = self.d.get("def_physique", {})
        dp = (50 if phy.get("enceinte") else 0) + (20 if phy.get("porte") else 0) + (self.d.get("nb_tours",0)*VALEUR_PHYSIQUE["tour"])

        # 3. Défense Objets (Armures, Boucliers, Constructions spéciales)
        dm = 0
        for obj in self.d.get("objets_reels", []):
            nom = obj.get("nom")
            # Si l'objet est dans le catalogue et a un bonus de défense
            if nom in CATALOGUE_OBJETS and "bonus_def" in CATALOGUE_OBJETS[nom]:
                dm += CATALOGUE_OBJETS[nom]["bonus_def"]
            # Ancienne compatibilité pour les éléments de construction libres
            elif obj.get("type") == "Élément de construction":
                dm += obj.get("valeur", 0)

        # 4. Défense Kaplas (IRL)
        dk = (self.d.get("nb_toits",0)*3) + (self.d.get("kaplas",0)*2)

        return int(da + dp + dm + dk)

    def get_puissance(self):
        a = self.d.get("armee", {})
        return a.get("Soldat",0)*STATS_COMBAT["Soldat"]["base"] + \
               a.get("Archer",0)*STATS_COMBAT["Archer"]["base"] + \
               a.get("Chevalier",0)*STATS_COMBAT["Chevalier"]["base"]

    def a_objet(self, nom_objet):
        for obj in self.d.get("objets_reels", []):
            if obj.get("nom") == nom_objet or obj.get("type") == nom_objet: return True
        return False

    def a_un_pont(self):
        return self.d.get("pont_construit", False)

    def get_bonus_fixe_production(self):
        return 2 if self.a_objet("Charrette") else 0

    def get_taille_foyer(self):
        return 1 + (1 if self.d.get("conjoint") else 0) + self.d.get("enfants", 0)

    def get_besoin_toits_famille(self):
        return self.get_taille_foyer() * 2

    def get_toits_disponibles_pour_embauche(self):
        reste = self.d.get("nb_toits", 0) - self.get_besoin_toits_famille()
        return max(0, reste - (self.d.get("nb_ouvriers", 0) * 2))

    def get_rive(self):
        return "Gauche" if self.d.get("x", 50) < 50 else "Droite"

# ==========================================
# 4. LOGIQUE DE JEU (EVENTS & ACTIONS)
# ==========================================

def simuler_combat(att_dict, def_dict, malus_riviere=False):
    logs = []

    # Récupération armée
    armee_att = att_dict.get("armee", {"Soldat":0, "Archer":0, "Chevalier":0})
    s, a, c = armee_att.get("Soldat",0), armee_att.get("Archer",0), armee_att.get("Chevalier",0)

    # Calcul bonus armes attaquant
    bonus_armes = 0
    for obj in att_dict.get("objets_reels", []):
        nom = obj.get("nom")
        if nom in CATALOGUE_OBJETS and "bonus_att" in CATALOGUE_OBJETS[nom]:
            bonus_armes += CATALOGUE_OBJETS[nom]["bonus_att"]

    if bonus_armes > 0: logs.append(f"⚔️ Bonus Armes: +{bonus_armes}")

    # 1. Jet de Dé (Influence de +/- 30%)
    de = random.randint(1, 20)
    bonus_de = 0
    msg = ""
    if de == 1: bonus_de, msg = -0.5, "💀 ÉCHEC CRITIQUE (Dé 1)"
    elif de == 20: bonus_de, msg = 0.5, "🌟 COUP DE GÉNIE (Dé 20)"
    elif de >= 15: bonus_de, msg = 0.2, "🔥 Moral élevé (+20%)"
    elif de <= 5: bonus_de, msg = -0.2, "🌧️ Terrain boueux (-20%)"

    logs.append(f"🎲 Dé: {de}/20 {msg}")

    # 2. Calcul Force de Frappe (Rééquilibré)
    # Plus de multiplicateur x10 aléatoire. On a une base solide + une petite variation.
    force_base = (s * 10) + (a * 15) + (c * 40)

    # Bonus aléatoire léger (0.9 à 1.3)
    var_aleatoire = random.uniform(0.9, 1.3)

    # La force brute inclut maintenant le bonus des armes
    dmg = (force_base + bonus_armes) * var_aleatoire

    logs.append(f"⚔️ Troupes: {s} Soldats, {a} Archers, {c} Chevaliers")
    logs.append(f"💪 Force totale: {int(dmg)} (Base: {force_base} + Armes: {bonus_armes})")

    # Application du Dé
    total_att = int(dmg * (1 + bonus_de))

    # Malus Rivière
    if malus_riviere:
        total_att = int(total_att / 2)
        logs.append("🌊 RIVIÈRE: Malus traversée (/2)")

    # Calcul Défense
    helper_def = JoueurHelper(def_dict)
    total_def = helper_def.get_defense()

    diff = total_att - total_def

    if total_att > total_def:
        if diff > 50: logs.append("💥 VICTOIRE ÉCRASANTE !")
        else: logs.append("⚔️ VICTOIRE DIFFICILE")
    else:
        if abs(diff) < 20: logs.append("🛡️ DÉFENSE HÉROÏQUE (Tenu de justesse)")
        else: logs.append("🏰 FORTERESSE IMPRENABLE")

    return total_att, total_def, logs

def next_phase(data):
    if data["phase"] == 4:
        trigger_event(data, "Soir")
        if data["evenement_actif"]:
            save_data(data); return

        executer_nuit(data)

        data["phase"] = 1
        data["jour"] += 1
        # Réinitialiser le flag d'événement pour le nouveau jour
        data["jour_evenement"] = None
        nom_s, _, climat_pref, _, _, _ = get_saison_info(data["jour"])
        data["meteo"] = random.choice([climat_pref, "Beau temps"]) if random.random() > 0.5 else random.choice(["Pluie", "Orage", "Vent"])

        # Variation Cours
        data["cours_kapla_hier"] = data["cours_kapla"]
        data["cours_ble_hier"] = data["cours_ble"]
        ck, cb = data["cours_kapla"], data["cours_ble"]
        data["cours_kapla"] = max(5, ck + random.randint(-2, 3))
        data["cours_ble"] = max(2, cb + random.randint(-1, 2))

        # Variation Gibier
        base = {"Petit": 30, "Moyen": 50, "Gros": 100}
        for k, v in base.items():
            data["cours_gibier"][k] = max(10, v + random.randint(-10, 15))

        # --- SYSTÈME DE PIOCHE DU MATIN ---
        # Tirage au sort du type de stock de pièces
        stock_du_jour = random.choice(["Petite Bourse 💰", "Sac Moyen 💰💰", "Grand Coffre 💎"])

        # Tri des joueurs par richesse croissante (le plus pauvre commence)
        joueurs_vivants = [j for j in data["joueurs"] if j.get("vie", 0) > 0]
        ordre_joueurs = sorted(joueurs_vivants, key=lambda x: x.get("ecus", 0))
        noms_ordres = [j["nom"] for j in ordre_joueurs]

        data["info_pioche"] = {
            "type": stock_du_jour,
            "ordre": noms_ordres
        }

        # Reset Actions
        data["logs_guerre"] = []
        data["joueurs_prets"] = []
        for j in data["joueurs"]:
            j["action_du_jour"] = None

        trigger_event(data, "Matin")

    elif data["phase"] == 1:
        data["phase"] = 2
        data["joueurs_prets"] = []
        trigger_event(data, "Journée")
    elif data["phase"] == 2:
        # Transition vers le MARCHÉ (Phase 3) - Récap Guerre
        data["phase"] = 3
        data["joueurs_prets"] = []

        # Si guerre il y a eu, on prépare un signal sonore pour le Master
        if data.get("logs_guerre"):
            # On stocke une info temporaire pour que le gestion_audio la lise une fois
            data["trigger_sound_guerre"] = True
    else:
        data["phase"] += 1
        data["joueurs_prets"] = []

    save_data(data)

def executer_nuit(data):
    nom_s, _, _, _, _, _ = get_saison_info(data["jour"])

    for j in data["joueurs"]:
        if j.get("vie", 0) <= 0: continue
        j["rapport_nuit"] = []

        if j.get("bonus_banquet", 0) > 0:
            j["bonus_banquet"] -= 1
            msg = "🍽️ Fin du bonus Banquet." if j["bonus_banquet"] == 0 else f"🍽️ Bonus Banquet actif ({j['bonus_banquet']} j restants)"
            j["rapport_nuit"].append(msg)

        if j.get("nb_ouvriers", 0) > 0:
            cout = j["nb_ouvriers"] * SALAIRE_OUVRIER
            j["ecus"] -= cout
            j["rapport_nuit"].append(f"💸 Paie : -{cout}$")

        if j.get("conjoint"):
            j["conjoint"]["jours_mariage"] += 1
            j["faim"] -= 10
            j["rapport_nuit"].append("💍 Conjoint : -10 Faim")
            if j["conjoint"]["jours_mariage"] % DUREE_ANNEE == 0:
                j["enfants"] = j.get("enfants", 0) + 1
                j["rapport_nuit"].append("👶 **NAISSANCE !**")

        if j.get("stock_vin"):
            j["stock_vin"] = [a+1 for a in j["stock_vin"]]
            j["rapport_nuit"].append("🍇 Vin vieilli (+1 jour)")

        j["faim"] = max(0, j["faim"] - 15)
        if j["faim"] <= 0:
            j["faim"] = 0; j["vie"] -= PENALITE_FAMINE
            j["rapport_nuit"].append(f"💀 **FAMINE** : -{PENALITE_FAMINE} PV")

        if j.get("ecus", 0) < 0: j["rapport_nuit"].append("📉 **DETTES**")

        helper = JoueurHelper(j)
        besoin = helper.get_besoin_toits_famille() + (j.get("nb_ouvriers", 0) * 2)
        if nom_s == "Hiver":
            if j.get("nb_toits", 0) < besoin:
                j["vie"] -= 20; j["rapport_nuit"].append("❄️ FROID -20 PV")
        elif "Pluie" in data["meteo"] and j.get("nb_toits", 0) < (besoin/2):
            j["vie"] -= 10; j["rapport_nuit"].append("☔ PLUIE -10 PV")

        if j["vie"] <= 0:
            j["vie"] = 0; j["rapport_nuit"].append("🪦 MORT")

def trigger_event(data, moment):
    # Vérifier s'il y a déjà un événement actif ou si un événement a déjà été déclenché aujourd'hui
    if data.get("evenement_actif") is not None:
        return  # Un événement est déjà en cours
    
    # Vérifier si un événement a déjà été déclenché ce jour
    if data.get("jour_evenement") == data["jour"]:
        return  # Un événement a déjà été déclenché aujourd'hui
    
    # 1 événement maximum par jour (probabilité configurable)
    if random.random() > PROBA_EVENEMENT: 
        return

    events_map = {
        "Soir": ["Vol d'Ecu", "Vol de Ressource", "Saison de la Chasse", "Passage du Roi", "Le Monument", "Le Banquet", "L'Espion", "Attaque Surprise"]
    }

    if moment not in events_map or not data["joueurs"]: 
        return

    choix = random.choice(events_map[moment])
    cible = random.choice(data["joueurs"])

    evt = {"nom": choix, "data": {"cible": cible["nom"], "resolu": False}}

    if choix == "Vol d'Ecu":
        evt["data"]["perte"] = random.randint(2, 4) * data["jour"]

    elif choix == "Vol de Ressource":
        evt["data"]["perte"] = random.randint(1, 2) * data["jour"]

    elif choix == "Saison de la Chasse":
        evt["data"]["maitre"] = cible["nom"]
        evt["data"]["instruction"] = "Le joueur doit cacher des animaux dans une pièce. Les autres doivent les trouver."
        evt["data"]["chasseurs_valides"] = []  # Liste pour suivre qui a validé son butin

    elif choix == "Passage du Roi":
        total_ecus = sum(p["ecus"] for p in data["joueurs"])
        evt["data"]["gain"] = int((total_ecus / 2) * random.uniform(0.1, 0.5))
        evt["data"]["condition"] = "2 toits supplémentaires + de quoi s'asseoir"

    elif choix == "Le Monument":
        evt["data"]["cible"] = "Tous" # Marqueur pour dire que tout le monde participe
        evt["data"]["instruction"] = "Le premier joueur qui construit une tour de 5 Kaplas verticaux gagne ressources x2"

    elif choix == "Le Banquet":
        evt["data"]["instruction"] = "Le joueur doit avoir une grande table avec 4 chaises/bancs"
        evt["data"]["recompense"] = "Production x2 pendant 3 jours"

    elif choix == "L'Espion":
        evt["data"]["instruction"] = "Le joueur a 1 minute pour cacher sa figurine Chef chez un autre joueur"
        evt["data"]["penalite"] = "Perte d'un membre du foyer ou -15 PV"

    elif choix == "Attaque Surprise":
        evt["data"]["nb_figurines"] = random.randint(3, 6)
        evt["data"]["nb_essais"] = random.randint(10, 15)
        evt["data"]["instruction"] = f"Positionner {evt['data']['nb_figurines']} figurines. Le joueur a {evt['data']['nb_essais']} essais pour les faire tomber."
        evt["data"]["penalite"] = "20 écus par figurine restante"

    data["evenement_actif"] = evt
    data["jour_evenement"] = data["jour"]  # Marquer que l'événement a été déclenché ce jour

# ==========================================
# 5. INTERFACE UTILISATEUR
# ==========================================

# 1. Gestion Session / Login
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# Chargement données
data = load_data()
if not data: st.stop()

# Injection CSS - Aggressive Parchment
local_css()

# --- ÉCRAN DE CONNEXION ---
if st.session_state.user_role is None:
    st.title("🏰 Royaume des Kaplas")
    st.write("Bienvenue dans le réseau local du Royaume.")

    # --- AFFICHAGE DES INFORMATIONS DE CONNEXION + QR CODE ---
    st.divider()
    st.subheader("📱 Connexion Rapide")

    # Obtenir l'IP locale
    local_ip = get_local_ip()
    game_url = f"http://{local_ip}:8501"

    col_info, col_qr = st.columns([2, 1])

    with col_info:
        st.info("**Pour rejoindre depuis un téléphone ou une tablette :**")
        st.markdown(f"### 🔗 {game_url}")
        st.caption("✅ Scannez le QR Code ci-contre avec votre appareil mobile")
        st.caption("✅ Ou tapez l'adresse manuellement dans votre navigateur")
        st.caption("⚠️ Assurez-vous que tous les appareils sont connectés au **même réseau Wi-Fi/routeur**")

    with col_qr:
        st.write("**QR Code :**")
        # Générer le QR Code
        qr_img = generate_qr_code(game_url)

        # Convertir l'image PIL en bytes pour Streamlit
        img_byte_arr = BytesIO()
        qr_img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()

        st.image(img_byte_arr, caption=f"Scannez pour rejoindre : {game_url}", width=200)

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛠️ Administration")
        if st.button("Je suis le Maître du Jeu", type="primary"):
            st.session_state.user_role = "MASTER"
            st.rerun()

    with c2:
        st.subheader("👤 Joueurs")
        noms_existants = [j["nom"] for j in data["joueurs"]]

        if not noms_existants:
            st.warning("Aucun joueur inscrit. Attendez le Maître du Jeu.")
        else:
            choix_nom = st.selectbox("Votre Nom", ["Choisir..."] + noms_existants)
            if st.button("Rejoindre la partie"):
                if choix_nom != "Choisir...":
                    st.session_state.user_role = "PLAYER"
                    st.session_state.user_name = choix_nom
                    st.rerun()
    st.stop()

# --- GESTION AUDIO GLOBALE (MAITRE UNIQUEMENT) ---
# On le place ICI, avant tout blocage (st.stop), pour être sûr que le son se lance
if st.session_state.user_role == "MASTER":
    gestion_audio(data)

# --- GESTION ÉVÉNEMENT BLOQUANT (POUR LE MASTER UNIQUEMENT) ---
if data.get("evenement_actif") and st.session_state.user_role == "MASTER":
    evt = data["evenement_actif"]
    nom_evt = evt["nom"]
    info = evt["data"]

    st.warning(f"📢 ÉVÉNEMENT EN COURS : {nom_evt}")

    # VUE MAITRE - RÉSOLUTION
    st.info("👁️ En tant que Maître du Jeu, vous supervisez l'événement.")

    st.write(f"**Joueur concerné** : {info.get('cible')}")
    if info.get("maitre"):
        st.write(f"**Maître de l'événement** : {info.get('maitre')}")

    if info.get("instruction"):
        st.markdown(f"📋 **Instructions** : *{info.get('instruction')}*")

    st.divider()
    
    # Indicateur visuel d'attente
    st.write("⏳ **En attente de la résolution par les joueurs...**")
    st.progress(random.random()) # Barre qui bouge pour montrer que c'est vivant
    st.caption("L'écran s'actualise automatiquement.")

    # Bouton de secours (toujours utile si un joueur perd sa connexion)
    if st.button("⚠️ SUCCÈS D'URGENCE (Débloquer la partie)"):
        data["evenement_actif"] = None
        save_data(data)
        st.rerun()

    # --- AUTO REFRESH POUR LE MAITRE ---
    time.sleep(2)
    st.rerun()
    
    st.stop()


# ==========================================
# VUE MAÎTRE DU JEU (DASHBOARD)
# ==========================================
if st.session_state.user_role == "MASTER":
    st.sidebar.title("🎮 Panneau Maître")

    # --- LOGIQUE AUTOMATIQUE DE PASSAGE DE PHASE ---
    # On vérifie D'ABORD si tout le monde est prêt avant d'afficher quoi que ce soit
    if data["phase"] > 0:
        joueurs_prets = data.get("joueurs_prets", [])
        total_joueurs = len(data["joueurs"])

        # Si tout le monde est prêt ET qu'il y a des joueurs
        if total_joueurs > 0 and len(joueurs_prets) >= total_joueurs:
            st.success("✅ Tous les joueurs sont prêts ! Passage à la phase suivante...")
            time.sleep(1)  # Petit délai visuel
            next_phase(data)
            st.rerun()

    # Phase 0 : Inscription
    if data["phase"] == 0:
        st.header("📝 Inscription des Joueurs")
        c1, c2, c3 = st.columns(3)
        new_nom = c1.text_input("Nom")
        new_metier = c2.selectbox("Métier", list(STATS_METIERS.keys()))
        if c3.button("Inscrire"):
            if new_nom and not any(j["nom"] == new_nom for j in data["joueurs"]):
                new_j = {
                    "nom": new_nom, "metier": new_metier, "ecus": 80, "kaplas": 5,
                    "vie": 100, "vie_max": 100, "faim": 100, "faim_max": 100,
                    "nb_terrains": 0, "nb_ouvriers": 0, "nb_toits": 0, "nb_tours": 0,
                    "stock_ble": 0, "stock_vin": [],
                    "stock_gibier": {"Petit":0, "Moyen":0, "Gros":0}, "stock_champignons": 0,
                    "armee": {"Soldat":0, "Archer":0, "Chevalier":0},
                    "def_physique": {"enceinte": False, "porte": False},
                    "objets_reels": [], "conjoint": None, "enfants": 0, "bonus_banquet": 0,
                    "action_du_jour": None, "rapport_nuit": [], "rapport_combat": [],
                    "x": random.randint(10,90), "y": random.randint(10,90), "pont_construit": False
                }
                data["joueurs"].append(new_j)
                save_data(data)
                st.success(f"{new_nom} ajouté !")
                st.rerun()
            else:
                st.error("Nom vide ou déjà pris.")

        st.write("---")
        st.write("**Joueurs prêts** :", [j["nom"] for j in data["joueurs"]])

        if st.button("🚀 LANCER LA PARTIE", type="primary"):
            data["phase"] = 1
            save_data(data)
            st.rerun()

    # Jeu en cours
    else:
        # BARRE DE SAISON AVEC ANNÉE
        nom_s, icon_s, _, color_s, j_saison, annee = get_saison_info(data["jour"])
        st.markdown(f"""
        <div style="background:{color_s};padding:15px;border-radius:10px;text-align:center;margin-bottom:20px;">
            <h2 style="color:white;margin:0;">{icon_s} {nom_s} - Jour {j_saison}/10 | Année {annee}</h2>
            <p style="color:white;margin:5px 0 0 0;font-size:18px;">Jour {data['jour']} | Phase {data['phase']}/4 | {data['meteo']}</p>
        </div>
        """, unsafe_allow_html=True)

        # Barre de progression de l'année
        progression_annee = (data['jour'] - 1) % DUREE_ANNEE / DUREE_ANNEE
        st.progress(progression_annee, text=f"Progression de l'année : {int(progression_annee*100)}%")

        # COURS AVEC ÉVOLUTION
        st.subheader("📊 Cours du marché")
        col1, col2, col3, col4 = st.columns(4)

        evol_k = data['cours_kapla'] - data.get('cours_kapla_hier', data['cours_kapla'])
        evol_b = data['cours_ble'] - data.get('cours_ble_hier', data['cours_ble'])
        icon_k = "📈" if evol_k > 0 else "📉" if evol_k < 0 else "➡️"
        icon_b = "📈" if evol_b > 0 else "📉" if evol_b < 0 else "➡️"
        color_k = "green" if evol_k > 0 else "red" if evol_k < 0 else "gray"
        color_b = "green" if evol_b > 0 else "red" if evol_b < 0 else "gray"

        with col1:
            # Affichage du cours avec flèche et couleur
            pct_k = abs(evol_k/data.get('cours_kapla_hier',10)*100) if data.get('cours_kapla_hier',10) != 0 else 0
            delta_text = f"{evol_k:+d}$ ({pct_k:.1f}%)"
            st.markdown(f"**🧱 Kapla : {data['cours_kapla']}$**")
            st.markdown(f"<p style='color:{color_k};font-size:14px;margin:0;'>{icon_k} {delta_text}</p>", unsafe_allow_html=True)

        with col2:
            # Affichage du cours avec flèche et couleur
            pct_b = abs(evol_b/data.get('cours_ble_hier',5)*100) if data.get('cours_ble_hier',5) != 0 else 0
            delta_text = f"{evol_b:+d}$ ({pct_b:.1f}%)"
            st.markdown(f"**🌾 Blé : {data['cours_ble']}$**")
            st.markdown(f"<p style='color:{color_b};font-size:14px;margin:0;'>{icon_b} {delta_text}</p>", unsafe_allow_html=True)

        with col3:
            cg = data["cours_gibier"]
            st.write("**🍖 Gibier**")
            # Affichage uniformisé et plus gros
            st.markdown(f"<h5>🐇 {cg['Petit']}$ | 🐗 {cg['Moyen']}$ | 🐻 {cg['Gros']}$</h5>", unsafe_allow_html=True)

        with col4:
            st.metric("👥 Joueurs", len(data["joueurs"]))
            nb_prets = len(data.get("joueurs_prets", []))
            st.caption(f"Prêts: {nb_prets}/{len(data['joueurs'])}")

        st.divider()

        # CARTE COMPACTE
        col_carte, col_controle = st.columns([1, 2])

        with col_carte:
            st.write("**🗺️ Carte du Royaume**")
            if data["joueurs"]:
                st.image(generer_carte(data["joueurs"]), width=350)

        with col_controle:
            st.write("**🎮 Contrôles**")

            if st.button("➡️ PHASE SUIVANTE", type="primary", use_container_width=True):
                next_phase(data)
                st.rerun()

            if st.button("🔄 Rafraîchir", use_container_width=True):
                st.rerun()

            st.divider()

            # Tableau récap
            if data["joueurs"]:
                df_data = []
                for j in data["joueurs"]:
                    df_data.append({
                        "Nom": j["nom"],
                        "Métier": j["metier"],
                        "💰": j["ecus"],
                        "❤️": j["vie"],
                        "🍗": j["faim"],
                        "Action": j.get("action_du_jour", "-")
                    })
                st.dataframe(pd.DataFrame(df_data), use_container_width=True)

        # --- GESTION AUDIO AVANCÉE ---
        # 1. Check Récap Guerre (Transition 2->3)
        if data.get("trigger_sound_guerre"):
            autoplay_audio("sounds/attaque_reussie.mp3")  # Son de bataille
            data["trigger_sound_guerre"] = False  # On le joue une seule fois
            save_data(data)

        # 2. Blagues Aléatoires (Seulement si pas d'event actif)
        if not data.get("evenement_actif"):
            # 5% de chance à chaque refresh (toutes les 5s)
            if random.random() < 0.05:
                blagues = ["joke_1.mp3", "joke_2.mp3", "joke_3.mp3", "joke_4.mp3", "joke_5.mp3"]
                son_blague = random.choice(blagues)
                autoplay_audio(f"sounds/{son_blague}")

        # --- AUTO-REFRESH LOOP ---
        # Une fois l'interface affichée, on attend 5s puis on reload
        # Cela permet au Master de voir l'écran pendant 5s, puis de vérifier si les joueurs sont prêts
        time.sleep(5)
        st.rerun()

    if st.sidebar.button("🔴 RESET TOTAL"):
        if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
        st.session_state.user_role = None
        st.rerun()

# ==========================================
# VUE JOUEUR (CLIENT)
# ==========================================
elif st.session_state.user_role == "PLAYER":
    # ============================================================
    # 1. RÉCUPÉRATION JOUEUR
    # ============================================================
    me = next((j for j in data["joueurs"] if j["nom"] == st.session_state.user_name), None)

    if not me:
        st.error("Erreur de compte. Retournez à l'accueil.")
        if st.button("Déconnexion"):
            st.session_state.user_role = None
            st.rerun()
        st.stop()

    # --- ALERTE ATTAQUE SUBIE ---
    if me.get("rapport_combat"):
        st.error("⚔️ VOUS AVEZ ÉTÉ ATTAQUÉ CETTE NUIT !")
        for msg in me["rapport_combat"]:
            st.write(msg)

        if st.button("❌ J'ai vu (Fermer l'alerte)", key="close_alert"):
            me["rapport_combat"] = []
            save_data(data)
            st.rerun()
        st.divider()

    # --- GESTION DE LA MORT ---
    if me["vie"] <= 0:
        st.error("💀 VOUS ÊTES MORT")
        st.markdown(f"""
        <div style="text-align:center; padding: 50px;">
            <h1>✝️ R.I.P</h1>
            <p>Votre aventure s'arrête ici.</p>
            <p>Vous avez succombé à vos blessures ou à la famine.</p>
        </div>
        """, unsafe_allow_html=True)

        # Mode spectateur pour le mort (optionnel : il voit juste le log)
        st.info("Attendez que le Maître du jeu relance une partie.")

        if st.button("Quitter la partie"):
            st.session_state.user_role = None
            st.rerun()

        time.sleep(5)  # Refresh lent pour voir si le MJ reset la partie
        st.rerun()

    # --- DETECTION CHANGEMENT DE PHASE / EVENT ---
    if "last_phase_seen" not in st.session_state:
        st.session_state.last_phase_seen = data["phase"]

    # Si la phase change, on reset l'auto-refresh pour éviter les boucles
    if st.session_state.last_phase_seen != data["phase"]:
        st.session_state.last_phase_seen = data["phase"]
        st.session_state.auto_refresh = False
        st.rerun()

    # Si un event arrive, on refresh pour l'afficher
    current_event = data.get("evenement_actif")
    if "last_event_seen" not in st.session_state:
        st.session_state.last_event_seen = current_event

    if st.session_state.last_event_seen != current_event:
        st.session_state.last_event_seen = current_event
        st.rerun()

    helper = JoueurHelper(me)

    # ============================================================
    # 2. AFFICHAGE DU HEADER & HUD
    # ============================================================
    # --- HEADER JOUEUR ---
    nom_saison, icon_saison, _, color_saison, j_saison, annee = get_saison_info(data["jour"])
    st.markdown(f"""
    <div style="background:{color_saison};padding:10px;border-radius:8px;text-align:center;margin-bottom:15px;">
        <h3 style="color:white;margin:0;">{icon_saison} {nom_saison} - Jour {j_saison}/10 | Année {annee}</h3>
    </div>
    """, unsafe_allow_html=True)

    # Barre de progression de l'année
    progression_annee = (data['jour'] - 1) % DUREE_ANNEE / DUREE_ANNEE
    st.progress(progression_annee, text=f"Progression de l'année : {int(progression_annee*100)}%")

    st.sidebar.title(f"👤 {me['nom']}")
    st.sidebar.write(f"Métier : **{me['metier']}** {STATS_METIERS[me['metier']]['icon']}")

    # --- HUD STICKY : Métriques fixes en haut ---
    st.markdown("""
    <div class="hud-sticky">
        <div style="display: flex; justify-content: space-around; align-items: center; flex-wrap: wrap; gap: 20px;">
    """, unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Vie ❤️", f"{me['vie']}/{me['vie_max']}")
        draw_bar(me['vie'], me['vie_max'], "#f44336")
    with c2:
        st.metric("Faim 🍗", f"{me['faim']}/{me['faim_max']}")
        draw_bar(me['faim'], me['faim_max'], "#FF9800")
    with c3:
        st.metric("Or 💰", me['ecus'])
    with c4:
        st.metric("Kaplas 🧱", me['kaplas'])
    
    st.markdown("</div></div>", unsafe_allow_html=True)

    # Inventaire
    inv = []
    if me['stock_ble'] > 0: inv.append(f"🌾{me['stock_ble']}")
    if me['stock_vin']: inv.append(f"🍷{len(me['stock_vin'])}")
    gibier = me.get("stock_gibier", {})
    if gibier.get("Petit"): inv.append(f"🐇{gibier['Petit']}")
    if gibier.get("Moyen"): inv.append(f"🐗{gibier['Moyen']}")
    if gibier.get("Gros"): inv.append(f"🐻{gibier['Gros']}")
    if me.get("stock_champignons"): inv.append(f"🍄{me['stock_champignons']}")

    for k,v in me.get("armee", {}).items():
        if v > 0: inv.append(f"{STATS_COMBAT[k]['icon']}{v}")

    for o in me.get("objets_reels", []):
        nom_o = o.get("nom", "")
        if nom_o in CATALOGUE_OBJETS:
            inv.append(CATALOGUE_OBJETS[nom_o].get("icon", "🔧"))

    st.info("🎒 **Inventaire**: " + " | ".join(inv) if inv else "🎒 **Inventaire**: Vide")

    # ============================================================
    # 3. AIGUILLAGE PRINCIPAL : ÉVÉNEMENT vs JEU NORMAL
    # ============================================================
    if data.get("evenement_actif"):
        # === MODE ÉVÉNEMENT ===
        evt = data["evenement_actif"]
        nom_evt = evt["nom"]
        info = evt["data"]

        # Si la cible est "Tous" ou si c'est la Chasse, tout le monde est acteur
        if nom_evt in ["Le Monument", "Saison de la Chasse"]:
            est_acteur = True
        else:
            est_acteur = (st.session_state.user_name == info.get("cible")) or (st.session_state.user_name == info.get("maitre"))

        st.divider()

        if est_acteur:
            # ========================================================
            # MODE ACTEUR : Le joueur doit agir
            # ========================================================
            st.subheader(f"📢 ACTION REQUISE : {nom_evt}")

            # Logique des boutons selon l'événement
            if nom_evt == "Vol d'Ecu":
                st.error(f"🚨 Des voleurs vous ciblent ! Perte potentielle : **{info['perte']}$**")
                if helper.a_objet("Coffre-fort"):
                    st.success("🔒 Vous avez un coffre-fort ! Le vol est annulé.")
                    if st.button("✅ ÉVÉNEMENT TERMINÉ"):
                        data["evenement_actif"] = None
                        save_data(data)
                        st.rerun()
                else:
                    st.error(f"💸 Vous n'avez pas de coffre-fort. Vous perdez **{info['perte']}$**")
                    if st.button("✅ CONFIRMER LA PERTE"):
                        me["ecus"] = max(0, me["ecus"] - info["perte"])
                        data["evenement_actif"] = None
                        save_data(data)
                        st.rerun()

            elif nom_evt == "Vol de Ressource":
                st.error(f"🚨 Des pillards tentent de voler vos ressources ! Menace : **-{info['perte']}** unités")
                st.caption(f"Vos stocks : Blé={me.get('stock_ble',0)} | Kaplas={me.get('kaplas',0)}")

                # Vérification : Le joueur a-t-il protégé ses cultures physiquement ?
                culture_protegee = me.get("def_physique", {}).get("protection_cultures", False)

                col1, col2 = st.columns(2)

                with col1:
                    # Option 1 : Payer (Pas de protection)
                    if st.button("💸 ILS PILLENT MES CHAMPS"):
                        perte = info["perte"]
                        # Priorité sur le blé
                        if me.get("stock_ble", 0) >= perte:
                            me["stock_ble"] -= perte
                            st.error(f"Ils ont piétiné vos champs : -{perte} Blé.")
                        elif me.get("kaplas", 0) >= perte:
                            me["kaplas"] -= perte
                            st.error(f"Ils ont volé votre bois : -{perte} Kaplas.")
                        else:
                            st.info("Les pillards n'ont rien trouvé d'intéressant.")

                        data["evenement_actif"] = None
                        save_data(data)
                        st.rerun()

                with col2:
                    # Option 2 : Se défendre (Si condition physique remplie)
                    if culture_protegee:
                        st.success("🛡️ CHAMPS SÉCURISÉS (Mur de 1 Kapla)")
                        if st.button("🛡️ REPOUSSER LES PILLARDS", type="primary"):
                            st.balloons()
                            st.success("Votre mur d'enceinte a stoppé les voleurs ! Ils fuient !")
                            time.sleep(2)
                            data["evenement_actif"] = None
                            save_data(data)
                            st.rerun()
                    else:
                        st.warning("⚠️ Vos cultures sont à découvert !")
                        st.caption("Pour vous défendre : Construisez un mur d'au moins 1 Kapla de haut tout autour de vos champs (Phase 4).")

            elif nom_evt == "Saison de la Chasse":
                # --- VUE MAÎTRE DE CHASSE (Celui qui a organisé) ---
                if st.session_state.user_name == info.get("maitre"):
                    st.success("👑 VOUS ÊTES LE MAÎTRE DE CHASSE !")
                    st.write(f"**Instructions** : {info.get('instruction')}")
                    st.info("🎯 Cachez les animaux. Les joueurs valident leur butin sur leur écran.")
                    
                    # Afficher qui a déjà ramené du gibier
                    chasseurs = info.get("chasseurs_valides", [])
                    if chasseurs:
                        st.write("📊 **Chasseurs revenus :** " + ", ".join(chasseurs))
                    else:
                        st.caption("Aucun chasseur n'est encore revenu...")

                    st.divider()
                    st.write("Une fois que tout le monde a fini :")
                    if st.button("🏁 TERMINER L'ÉVÉNEMENT (Fin de la Chasse)"):
                        me["ecus"] += 100 # Prime pour l'organisateur
                        data["evenement_actif"] = None
                        save_data(data)
                        st.rerun()

                # --- VUE CHASSEURS (Tous les autres joueurs) ---
                else:
                    # Vérifier si le joueur a déjà validé son butin
                    if st.session_state.user_name in info.get("chasseurs_valides", []):
                        st.success("✅ BUTIN VALIDÉ !")
                        st.info("🎒 Vos prises ont été ajoutées à votre inventaire.")
                        st.caption("En attente de la fin de la chasse par le Maître...")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.subheader("🏹 C'est la Chasse ! Rapportez votre butin.")
                        st.write(f"Cherchez les animaux cachés par **{info.get('maitre')}** !")

                        c1, c2, c3 = st.columns(3)
                        nb_petit = c1.number_input("🐇 Petit", 0, 10, 0)
                        nb_moyen = c2.number_input("🐗 Moyen", 0, 5, 0)
                        nb_gros = c3.number_input("🐻 Gros", 0, 2, 0)

                        # Gestion du Couteau à Champignons
                        nb_champi = 0
                        if helper.a_objet("Couteau Champignon"):
                            st.success("🍄 Couteau actif !")
                            nb_champi = st.number_input("🍄 Champignons", 0, 20, 0)

                        st.divider()
                        
                        if st.button("✅ VALIDER MON BUTIN", type="primary"):
                            # Mise à jour inventaire
                            if "stock_gibier" not in me: me["stock_gibier"] = {"Petit":0, "Moyen":0, "Gros":0}
                            me["stock_gibier"]["Petit"] += nb_petit
                            me["stock_gibier"]["Moyen"] += nb_moyen
                            me["stock_gibier"]["Gros"] += nb_gros
                            if nb_champi > 0:
                                me["stock_champignons"] = me.get("stock_champignons", 0) + nb_champi

                            # Enregistrement
                            if "chasseurs_valides" not in info: info["chasseurs_valides"] = []
                            info["chasseurs_valides"].append(st.session_state.user_name)
                            
                            save_data(data)
                            st.balloons()
                            st.rerun()

            elif nom_evt == "Passage du Roi":
                st.success(f"👑 LE ROI VOUS REND VISITE !")
                st.write(f"**Condition** : {info.get('condition')}")
                st.write(f"**Récompense potentielle** : {info.get('gain')}$")

                col1, col2 = st.columns(2)
                if col1.button("✅ J'AI LES CONDITIONS"):
                    me["ecus"] += info.get("gain", 0)
                    st.success(f"🎉 Vous recevez {info.get('gain')}$ du Roi !")
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()
                if col2.button("❌ JE N'AI PAS LES CONDITIONS"):
                    st.info("Le Roi repart sans vous donner d'or.")
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()

            elif nom_evt == "Le Monument":
                st.info("🏛️ DÉFI COLLECTIF : LES DIEUX RÉCLAMENT UNE OFFRANDE !")
                st.warning(f"🏆 {info.get('instruction')}")
                st.write("Le **PREMIER** joueur à valider remporte la bénédiction !")

                # Bouton de course : Le premier qui clique gagne
                if st.button("🏁 J'AI TERMINÉ LA TOUR EN PREMIER !", type="primary", use_container_width=True):
                    # On vérifie si l'event est toujours actif (anti-conflit)
                    if data.get("evenement_actif"):
                        me["stock_ble"] = me.get("stock_ble", 0) * 2
                        me["kaplas"] = me.get("kaplas", 0) * 2
                        gibier = me.get("stock_gibier", {})
                        for k in gibier:
                            gibier[k] *= 2
                        
                        st.balloons()
                        st.success("🎉 BÉNÉDICTION ACCORDÉE ! Vos ressources ont doublé !")
                        
                        # On ferme l'événement pour tout le monde
                        data["evenement_actif"] = None
                        # On peut ajouter un log pour dire qui a gagné si tu veux
                        save_data(data)
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Trop tard ! Quelqu'un d'autre a déjà gagné.")
                        time.sleep(2)
                        st.rerun()

            elif nom_evt == "Le Banquet":
                st.success("🍽️ VOUS ORGANISEZ UN GRAND BANQUET !")
                st.write(f"**Instructions** : {info.get('instruction')}")
                st.write(f"**Récompense** : {info.get('recompense')}")

                col1, col2 = st.columns(2)
                if col1.button("✅ J'AI LA TABLE ET LES CHAISES"):
                    me["bonus_banquet"] = 3
                    st.success("🎉 Le Roi est impressionné ! Production x2 pendant 3 jours !")
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()
                if col2.button("❌ JE N'AI PAS TOUT"):
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()

            elif nom_evt == "L'Espion":
                st.error("🗡️ UN ASSASSIN RÔDE !")
                st.write(f"**Instructions** : {info.get('instruction')}")
                st.write("Vous avez 1 minute pour cacher votre figurine Chef chez un autre joueur")
                st.caption(f"**Pénalité** : {info.get('penalite')}")

                col1, col2 = st.columns(2)
                if col1.button("✅ J'AI RÉUSSI À ME CACHER"):
                    st.success("🎉 Vous avez échappé à l'assassin !")
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()
                if col2.button("❌ ILS M'ONT TROUVÉ"):
                    if me.get("enfants", 0) > 0:
                        me["enfants"] -= 1
                        st.error("💔 Vous perdez un enfant...")
                    elif me.get("conjoint"):
                        me["conjoint"] = None
                        st.error("💔 Vous perdez votre conjoint...")
                    elif me.get("nb_ouvriers", 0) > 0:
                        me["nb_ouvriers"] -= 1
                        st.error("💔 Vous perdez un ouvrier...")
                    else:
                        me["vie"] = max(0, me["vie"] - 15)
                        st.error("💔 Vous perdez 15 PV...")
                    data["evenement_actif"] = None
                    save_data(data)
                    st.rerun()

            elif nom_evt == "Attaque Surprise":
                st.error("⚔️ ATTAQUE SURPRISE !")
                st.write(f"**Instructions** : {info.get('instruction')}")
                nb_fig = info.get("nb_figurines", 3)
                nb_essais = info.get("nb_essais", 10)
                st.write(f"**Nombre de figurines** : {nb_fig}")
                st.write(f"**Nombre d'essais** : {nb_essais}")
                st.caption(f"**Pénalité** : {info.get('penalite')}")

                st.divider()
                st.subheader("📊 Résultat de votre défense")
                
                # Menu pour saisir le nombre de figurines restantes
                restantes = st.number_input(
                    "Combien de figurines sont encore debout ?", 
                    min_value=0, 
                    max_value=nb_fig, 
                    value=0,
                    help=f"Indiquez le nombre de figurines restantes (0 à {nb_fig})"
                )

                # Calcul du résultat
                if restantes == 0:
                    # Victoire : gain = nombre total de figurines * 10
                    gain = nb_fig * 10
                    st.success(f"🎉 VICTOIRE TOTALE ! Toutes les figurines sont tombées !")
                    st.info(f"💰 Vous gagnez {gain}$ de prime !")
                else:
                    # Défaite : perte = nombre restantes * 20
                    perte = restantes * 20
                    st.warning(f"⚠️ Il reste {restantes} figurine(s) debout.")
                    st.info(f"💸 Pénalité : -{perte}$ ({restantes} × 20$)")

                st.divider()

                # Bouton pour valider le résultat
                if st.button("✅ VALIDER LE RÉSULTAT", type="primary", use_container_width=True):
                    if restantes == 0:
                        # Victoire : gain
                        gain = nb_fig * 10
                        me["ecus"] += gain
                        st.balloons()
                        st.success(f"🎉 Victoire ! Vous gagnez {gain}$ de prime !")
                    else:
                        # Défaite : perte
                        perte = restantes * 20
                        me["ecus"] = max(0, me["ecus"] - perte)
                        st.error(f"Vous perdez {perte}$ ({restantes} figurine(s) restante(s))")
                    
                    data["evenement_actif"] = None
                    save_data(data)
                    time.sleep(2)
                    st.rerun()

        else:
            # ========================================================
            # MODE SPECTATEUR : Les autres joueurs observent
            # ========================================================
            st.warning(f"⚠️ ÉVÉNEMENT EN COURS : {nom_evt}")

            st.write(f"👤 **Joueur ciblé** : {info.get('cible')}")
            if info.get("maitre"):
                st.write(f"👑 **Maître du jeu** : {info.get('maitre')}")

            st.info("⏳ Le jeu est en pause pour les autres joueurs...")

            # Barre de chargement pour montrer que ça tourne
            st.progress(random.random())
            st.caption("Actualisation automatique en attente de la fin de l'événement...")

            # AUTO REFRESH SPECTATEUR
            time.sleep(2)
            st.rerun()

    # ============================================================
    # 4. MODE JEU NORMAL (Pas d'événement actif)
    # ============================================================
    else:
        # C'est ici que l'on met tout le reste : Phase 0, 1, 2, 3, 4
        # Le code des onglets, des actions, des achats, etc.

        phase = data["phase"]

        if phase == 0:
            st.warning("⏳ En attente du lancement de la partie par le Maître du Jeu...")

        elif phase == 1:
            st.header("🌅 Phase 1 : Réveil")

            # --- AFFICHAGE PIOCHE DU MATIN ---
            if "info_pioche" in data:
                info = data["info_pioche"]
                st.markdown(f"""
                <div style="background:#ffd700;padding:15px;border-radius:10px;border:3px solid #8b6914;margin-bottom:20px;">
                    <h3 style="color:#4a3b2a;text-align:center;margin:0;">👐 Distribution du Matin : {info['type']}</h3>
                </div>
                """, unsafe_allow_html=True)

                st.write("**📋 Ordre de passage (du plus pauvre au plus riche) :**")

                # Affichage de l'ordre avec mise en évidence
                for idx, nom in enumerate(info['ordre']):
                    if idx == 0:
                        st.markdown(f"### 🥇 **{nom}** (Premier à se servir !)")
                    elif idx == 1:
                        st.markdown(f"🥈 **{nom}**")
                    elif idx == 2:
                        st.markdown(f"🥉 **{nom}**")
                    else:
                        st.write(f"{idx+1}. {nom}")

                st.divider()

            if me.get("rapport_nuit"):
                with st.expander("📜 Bilan de la nuit", expanded=True):
                    for ligne in me["rapport_nuit"]:
                        st.write(f"- {ligne}")

            # Rapport de combats subis (messages laissés par les autres joueurs)
            if "rapport_combat" not in me:
                me["rapport_combat"] = []
            if me.get("rapport_combat"):
                with st.expander("⚔️ Rapports de combat reçus", expanded=True):
                    for ligne in me["rapport_combat"]:
                        st.warning(ligne)
                # Une fois lus, on vide la boîte de réception
                me["rapport_combat"] = []
                save_data(data)

        elif phase == 2:
            st.header("🔨 Phase 2 : Actions")

            act = me.get("action_du_jour")

            # Vérifier si prêt
            est_pret = st.session_state.user_name in data.get("joueurs_prets", [])

            if est_pret:
                # --- ÉCRAN D'ATTENTE DYNAMIQUE ---
                nb_prets = len(data.get("joueurs_prets", []))
                total_joueurs = len(data["joueurs"])

                st.success("✅ Vous êtes PRÊT !")
                st.info(f"⏳ En attente des autres joueurs...")
                st.metric("Joueurs prêts", f"{nb_prets} / {total_joueurs}")

                # Auto-refresh toutes les 2 secondes pour détecter le changement de phase
                time.sleep(2)
                st.rerun()

            else:
                # --- LOGIQUE RESTRICTIVE PAR CATÉGORIE ---

                # CAS A : Pas encore d'action, afficher tous les onglets
                if act is None:
                    tab1, tab2, tab3, tab4 = st.tabs(["💼 Gestion", "⚒️ Travailler", "⚖️ Vendre", "⚔️ Guerre"])

                    # --- GESTION (Action coup de poing) ---
                    with tab1:
                        stats = STATS_METIERS.get(me["metier"], STATS_METIERS["Fermier"])
                        st.subheader("Gestion des ressources")
                        st.warning("⚠️ Acheter un terrain ou recruter un ouvrier termine votre tour !")

                        c_a, c_b = st.columns(2)
                        with c_a:
                            st.write("**Terrains**")
                            prix_t = stats['cout_terrain']
                            st.metric("Terrains possédés", me.get('nb_terrains', 0))
                            st.caption(f"Bonus: +{int(stats['bonus_terrain']*100)}% prod par terrain")
                            if st.button(f"Acheter Terrain (-{prix_t}$)", key="bt"):
                                if me["ecus"] >= prix_t:
                                    me["ecus"] -= prix_t
                                    me["nb_terrains"] += 1
                                    me["action_du_jour"] = "GESTION"
                                    if st.session_state.user_name not in data.get("joueurs_prets", []):
                                        data["joueurs_prets"].append(st.session_state.user_name)
                                    save_data(data)
                                    st.rerun()
                                else:
                                    st.error("💸 Pas assez d'argent")

                        with c_b:
                            st.write("**Ouvriers**")
                            st.metric("Ouvriers embauchés", me.get('nb_ouvriers', 0))
                            toits = helper.get_toits_disponibles_pour_embauche()
                            st.caption(f"Toits libres : {toits} (Requis: 2 par ouvrier)")
                            if st.button(f"Recruter Ouvrier (-{PRIX_OUVRIER}$)", key="bo"):
                                if me["ecus"] < PRIX_OUVRIER:
                                    st.error("💸 Pas assez d'argent")
                                elif toits < 2:
                                    st.error("🏠 Pas de lit disponible")
                                else:
                                    me["ecus"] -= PRIX_OUVRIER
                                    me["nb_ouvriers"] += 1
                                    me["action_du_jour"] = "GESTION"
                                    if st.session_state.user_name not in data.get("joueurs_prets", []):
                                        data["joueurs_prets"].append(st.session_state.user_name)
                                    save_data(data)
                                    st.rerun()

                    # --- TRAVAIL ---
                    with tab2:
                        stats = STATS_METIERS.get(me["metier"], STATS_METIERS["Fermier"])
                        cout = stats["cout_fatigue"]

                        st.subheader(f"⚒️ Travailler ({me['metier']})")
                        st.info("💡 Une fois que vous travaillez, vous ne pouvez plus faire d'autre action (Gestion/Vente/Guerre)")
                        st.write(f"Coût en fatigue : **{cout}** points")

                        coeff = helper.get_prod_coeff(data["jour"])
                        st.caption(f"Coefficient actuel : x{coeff:.2f}")

                        # Estimation du gain de production (min / max)
                        bonus_fixe = helper.get_bonus_fixe_production()
                        gain_min = int(stats["base_min"] * coeff) + bonus_fixe
                        gain_max = int(stats["base_max"] * coeff) + bonus_fixe

                        if st.button("🔨 Travailler maintenant", type="primary"):
                            if me["faim"] >= cout:
                                me["faim"] -= cout

                                gain = int(random.randint(stats["base_min"], stats["base_max"]) * coeff) + helper.get_bonus_fixe_production()

                                if me["metier"] == "Fermier":
                                    me["stock_ble"] += gain
                                    st.toast(f"✅ Récolte : +{gain} Blé 🌾", icon="🌾")
                                elif me["metier"] == "Bûcheron":
                                    me["kaplas"] += gain
                                    st.toast(f"✅ Production : +{gain} Kaplas 🧱", icon="🧱")
                                elif me["metier"] == "Vigneron":
                                    if me["ecus"] >= 10:
                                        me["ecus"] -= 10
                                        me["stock_vin"].append(0)
                                        st.toast("✅ Nouvelle cuvée lancée 🍷", icon="🍷")
                                    else:
                                        st.toast("❌ Pas assez d'or (10$ requis)", icon="💸")

                                # Marquer que le joueur est en mode TRAVAIL
                                me["action_du_jour"] = "TRAVAIL_EN_COURS"
                                save_data(data)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("😫 Trop fatigué ! Mangez d'abord.")

                    # --- VENTE ---
                    with tab3:
                        st.subheader("⚖️ Vendre vos ressources")
                        st.info("💡 Une fois que vous vendez, vous ne pouvez plus faire d'autre action (Gestion/Travail/Guerre)")

                        if me["metier"] == "Fermier":
                            st.write(f"Stock de Blé : **{me['stock_ble']}** 🌾")
                            st.write(f"Cours actuel : **{data['cours_ble']}$** / unité")

                            if me['stock_ble'] > 0:
                                q = st.number_input("Quantité à vendre", 1, me['stock_ble'], 1, key="vente_ble")
                                bonus = 1.1 if helper.a_objet("Charrette") else 1.0
                                gain_estime = int(q * data["cours_ble"] * bonus)
                                st.caption(f"Gain estimé : {gain_estime}$")

                                if st.button("💰 Vendre"):
                                    me["stock_ble"] -= q
                                    me["ecus"] += gain_estime
                                    me["action_du_jour"] = "VENTE_EN_COURS"
                                    st.toast(f"💰 Vendu {q} Blé pour {gain_estime}$", icon="💰")
                                    save_data(data)
                                    st.rerun()

                        elif me["metier"] == "Bûcheron":
                            st.write(f"Stock de Kaplas : **{me['kaplas']}** 🧱")
                            cours_vente = max(1, data["cours_kapla"] - 2)
                            st.write(f"Cours de vente : **{cours_vente}$** / unité")

                            if me['kaplas'] > 0:
                                q = st.number_input("Quantité à vendre", 1, me['kaplas'], 1, key="vente_kapla")
                                bonus = 1.1 if helper.a_objet("Charrette") else 1.0
                                gain_estime = int(q * cours_vente * bonus)
                                st.caption(f"Gain estimé : {gain_estime}$")

                                if st.button("💰 Vendre"):
                                    me["kaplas"] -= q
                                    me["ecus"] += gain_estime
                                    me["action_du_jour"] = "VENTE_EN_COURS"
                                    st.toast(f"💰 Vendu {q} Kaplas pour {gain_estime}$", icon="💰")
                                    save_data(data)
                                    st.rerun()

                        elif me["metier"] == "Vigneron" and me["stock_vin"]:
                            st.write("🍷 **Vos cuvées de vin**")

                            for idx, age in enumerate(me["stock_vin"]):
                                prix = int(1.2 * helper.get_prod_coeff(data["jour"]) * (age ** 2))
                                prix = max(5, prix)
                                col1, col2 = st.columns([3, 1])
                                col1.write(f"Bouteille #{idx+1} - Âge: {age} jours - Valeur: {prix}$")
                                if col2.button(f"Vendre", key=f"vin_{idx}"):
                                    me["stock_vin"].pop(idx)
                                    me["ecus"] += prix
                                    me["action_du_jour"] = "VENTE_EN_COURS"
                                    save_data(data)
                                    st.rerun()

                    # --- GUERRE (Action coup de poing) ---
                    with tab4:
                        st.subheader("⚔️ Attaquer un autre joueur")
                        st.warning("⚠️ Attaquer termine votre tour !")

                        cibles = [p["nom"] for p in data["joueurs"] if p["nom"] != me["nom"] and p.get("vie", 0) > 0]
                        if not cibles:
                            st.info("Personne à attaquer.")
                        else:
                            cible_nom = st.selectbox("Choisir la cible", cibles)
                            cible = next(p for p in data["joueurs"] if p["nom"] == cible_nom)

                            # Initialisation de la boite aux lettres si elle n'existe pas (sécurité)
                            if "rapport_combat" not in cible: 
                                cible["rapport_combat"] = []

                            st.write("---")
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.write(f"**🕵️ Renseignement sur {cible_nom}**")
                                st.write(f"- Tours visibles : {cible.get('nb_tours', 0)} 🗼")
                                st.write(f"- Or visible (estimé) : {cible.get('ecus', 0) // 10 * 10}+ 💰")

                            with col_info2:
                                rive_j = helper.get_rive()
                                rive_c = JoueurHelper(cible).get_rive()
                                malus = False

                                st.write("**📍 Position Stratégique**")
                                if rive_j != rive_c:
                                    if helper.a_un_pont():
                                        st.success("🌉 PONT : Traversée sécurisée")
                                    else:
                                        st.error("🌊 RIVIÈRE : Malus d'attaque (Force / 2)")
                                        malus = True
                                else:
                                    st.info("⛺ Même rive : Pas de pénalité")

                            puissance = helper.get_puissance()
                            st.metric("⚔️ Votre Puissance Militaire", puissance)

                            if puissance == 0:
                                st.warning("⚠️ Vous n'avez pas d'armée ! Recrutez des soldats avant d'attaquer.")
                            else:
                                if st.button("⚔️ LANCER L'ASSAUT", type="primary", use_container_width=True):
                                    # --- ANIMATION DE GUERRE ---
                                    progress_text = "Mobilisation des troupes..."
                                    my_bar = st.progress(0, text=progress_text)

                                    phrases_guerre = [
                                        "🎺 Les trompettes sonnent...",
                                        "🏹 Les archers bandent leurs arcs...",
                                        "🐎 La cavalerie charge !",
                                        "⚔️ Choc des armées !",
                                        "🔥 Les défenses tremblent..."
                                    ]

                                    for i in range(100):
                                        time.sleep(0.02)  # Durée de l'animation (2 secondes total)
                                        if i % 20 == 0:
                                            my_bar.progress(i + 1, text=random.choice(phrases_guerre))
                                        else:
                                            my_bar.progress(i + 1)
                                    my_bar.empty()

                                    # --- RÉSOLUTION ---
                                    force_att, force_def, logs = simuler_combat(me, cible, malus)

                                    st.divider()
                                    c_res1, c_res2 = st.columns(2)
                                    c_res1.markdown(f"<h2 style='text-align:center; color:blue'>{force_att}</h2>", unsafe_allow_html=True)
                                    c_res1.caption("⚔️ Votre Force de Frappe")

                                    c_res2.markdown(f"<h2 style='text-align:center; color:red'>{force_def}</h2>", unsafe_allow_html=True)
                                    c_res2.caption(f"🛡️ Défense de {cible_nom}")

                                    with st.expander("📜 Voir le détail du combat", expanded=False):
                                        for l in logs:
                                            st.write(l)

                                    # GESTION VICTOIRE / DÉFAITE
                                    if force_att > force_def:
                                        gain_k = min(15, cible["kaplas"])
                                        gain_e = min(40, cible["ecus"])

                                        me["kaplas"] += gain_k
                                        me["ecus"] += gain_e
                                        cible["kaplas"] -= gain_k
                                        cible["ecus"] -= gain_e

                                        st.success(f"🎉 VICTOIRE ÉCRASANTE !")
                                        st.write(f"💰 Vous avez pillé : **{gain_k} Kaplas** et **{gain_e} Ecus** !")

                                        # Message pour la victime
                                        msg_victime = f"⚔️ **ATTAQUE SUBIE** : {me['nom']} vous a attaqué et a GAGNÉ ! Vous avez perdu {gain_k} Kaplas et {gain_e} Ecus."
                                        cible["rapport_combat"].append(msg_victime)

                                    else:
                                        pertes = int((force_def - force_att)/10)
                                        pertes = max(5, pertes)
                                        me["vie"] -= pertes

                                        st.error(f"💀 DÉFAITE...")
                                        st.write(f"🚑 Vos troupes se replient. Vous perdez **{pertes} PV** dans la bataille.")

                                        # Message pour la victime
                                        msg_victime = f"🛡️ **DÉFENSE HÉROÏQUE** : {me['nom']} vous a attaqué mais vos défenses ont tenu bon ! Il est reparti bredouille."
                                        cible["rapport_combat"].append(msg_victime)

                                    # Finalisation
                                    me["action_du_jour"] = "GUERRE"
                                    # Ne pas ajouter automatiquement aux joueurs prêts
                                    # Le joueur doit lire les résultats et cliquer sur PRÊT manuellement

                                    # Sauvegarder les logs du combat pour affichage post-guerre
                                    me["dernier_combat_logs"] = logs

                                    data["logs_guerre"].append(f"{me['nom']} a attaqué {cible['nom']}.")
                                    save_data(data)
                                    time.sleep(3)  # Temps pour lire le résultat
                                    st.rerun()

                # CAS B : Mode TRAVAIL EN COURS
                elif act == "TRAVAIL_EN_COURS":
                    st.info("🔨 Vous êtes en mode TRAVAIL. Vous pouvez continuer à travailler ou terminer votre journée.")

                    stats = STATS_METIERS.get(me["metier"], STATS_METIERS["Fermier"])
                    cout = stats["cout_fatigue"]

                    st.subheader(f"⚒️ Travailler ({me['metier']})")
                    st.write(f"Coût en fatigue : **{cout}** points")

                    coeff = helper.get_prod_coeff(data["jour"])
                    st.caption(f"Coefficient actuel : x{coeff:.2f}")

                    # Estimation du gain de production (min / max)
                    bonus_fixe = helper.get_bonus_fixe_production()
                    gain_min = int(stats["base_min"] * coeff) + bonus_fixe
                    gain_max = int(stats["base_max"] * coeff) + bonus_fixe

                    if st.button("🔨 Travailler encore", type="primary"):
                        if me["faim"] >= cout:
                            me["faim"] -= cout

                            gain = int(random.randint(stats["base_min"], stats["base_max"]) * coeff) + helper.get_bonus_fixe_production()

                            if me["metier"] == "Fermier":
                                me["stock_ble"] += gain
                                st.toast(f"✅ Récolte : +{gain} Blé 🌾", icon="🌾")
                            elif me["metier"] == "Bûcheron":
                                me["kaplas"] += gain
                                st.toast(f"✅ Production : +{gain} Kaplas 🧱", icon="🧱")
                            elif me["metier"] == "Vigneron":
                                if me["ecus"] >= 10:
                                    me["ecus"] -= 10
                                    me["stock_vin"].append(0)
                                    st.toast("✅ Nouvelle cuvée lancée 🍷", icon="🍷")
                                else:
                                    st.toast("❌ Pas assez d'or (10$ requis)", icon="💸")

                            save_data(data)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("😫 Trop fatigué ! Mangez d'abord.")

                    st.caption(f"Gain estimé : entre {gain_min} et {gain_max} ressources")

                    st.divider()
                    if st.button("✅ TERMINER MA JOURNÉE", type="secondary", use_container_width=True):
                        me["action_du_jour"] = "TERMINÉ"
                        if st.session_state.user_name not in data.get("joueurs_prets", []):
                            data["joueurs_prets"].append(st.session_state.user_name)
                        save_data(data)
                        st.rerun()

                # CAS C : Mode VENTE EN COURS
                elif act == "VENTE_EN_COURS":
                    st.info("💰 Vous êtes en mode VENTE. Vous pouvez continuer à vendre ou terminer votre journée.")

                    st.subheader("⚖️ Vendre vos ressources")

                    if me["metier"] == "Fermier":
                        st.write(f"Stock de Blé : **{me['stock_ble']}** 🌾")
                        st.write(f"Cours actuel : **{data['cours_ble']}$** / unité")

                        if me['stock_ble'] > 0:
                            q = st.number_input("Quantité à vendre", 1, me['stock_ble'], 1, key="vente_ble_cont")
                            bonus = 1.1 if helper.a_objet("Charrette") else 1.0
                            gain_estime = int(q * data["cours_ble"] * bonus)
                            st.caption(f"Gain estimé : {gain_estime}$")

                            if st.button("💰 Vendre"):
                                me["stock_ble"] -= q
                                me["ecus"] += gain_estime
                                st.toast(f"💰 Vendu {q} Blé pour {gain_estime}$", icon="💰")
                                save_data(data)
                                st.rerun()
                        else:
                            st.warning("Stock épuisé")

                    elif me["metier"] == "Bûcheron":
                        st.write(f"Stock de Kaplas : **{me['kaplas']}** 🧱")
                        cours_vente = max(1, data["cours_kapla"] - 2)
                        st.write(f"Cours de vente : **{cours_vente}$** / unité")

                        if me['kaplas'] > 0:
                            q = st.number_input("Quantité à vendre", 1, me['kaplas'], 1, key="vente_kapla_cont")
                            bonus = 1.1 if helper.a_objet("Charrette") else 1.0
                            gain_estime = int(q * cours_vente * bonus)
                            st.caption(f"Gain estimé : {gain_estime}$")

                            if st.button("💰 Vendre"):
                                me["kaplas"] -= q
                                me["ecus"] += gain_estime
                                st.toast(f"💰 Vendu {q} Kaplas pour {gain_estime}$", icon="💰")
                                save_data(data)
                                st.rerun()
                        else:
                            st.warning("Stock épuisé")

                    elif me["metier"] == "Vigneron" and me["stock_vin"]:
                        st.write("🍷 **Vos cuvées de vin**")

                        for idx, age in enumerate(me["stock_vin"]):
                            prix = int(1.2 * helper.get_prod_coeff(data["jour"]) * (age ** 2))
                            prix = max(5, prix)
                            col1, col2 = st.columns([3, 1])
                            col1.write(f"Bouteille #{idx+1} - Âge: {age} jours - Valeur: {prix}$")
                            if col2.button(f"Vendre", key=f"vin_cont_{idx}"):
                                me["stock_vin"].pop(idx)
                                me["ecus"] += prix
                                save_data(data)
                                st.rerun()

                    st.divider()
                    if st.button("✅ TERMINER MA JOURNÉE", type="secondary", use_container_width=True):
                        me["action_du_jour"] = "TERMINÉ"
                        if st.session_state.user_name not in data.get("joueurs_prets", []):
                            data["joueurs_prets"].append(st.session_state.user_name)
                        save_data(data)
                        st.rerun()

                # CAS D : FIN DE GUERRE (Post-combat)
                elif act == "GUERRE":
                    st.success("⚔️ Votre attaque est terminée !")
                    st.info("📖 Prenez le temps de lire les résultats ci-dessous.")

                    # Affichage des logs du dernier combat (si disponibles)
                    logs_combat = me.get("dernier_combat_logs", [])
                    if logs_combat:
                        with st.expander("📜 Revoir le détail du combat", expanded=False):
                            for log in logs_combat:
                                st.write(log)

                    st.divider()
                    if st.button("✅ JE SUIS PRÊT", type="primary", use_container_width=True, key="btn_pret_guerre"):
                        me["action_du_jour"] = "TERMINÉ"
                        if st.session_state.user_name not in data.get("joueurs_prets", []):
                            data["joueurs_prets"].append(st.session_state.user_name)
                        save_data(data)
                        st.rerun()

                # CAS E : GESTION (Achat terrain/ouvrier terminé)
                elif act == "GESTION":
                    st.success("💼 Votre gestion est terminée !")
                    st.info("Vous avez acheté un terrain ou recruté un ouvrier. Cliquez sur PRÊT pour continuer.")

                    st.divider()
                    if st.button("✅ JE SUIS PRÊT", type="primary", use_container_width=True, key="btn_pret_gestion"):
                        me["action_du_jour"] = "TERMINÉ"
                        if st.session_state.user_name not in data.get("joueurs_prets", []):
                            data["joueurs_prets"].append(st.session_state.user_name)
                        save_data(data)
                        st.rerun()

        elif phase == 3:
            st.header("🛒 Phase 3 : Marché & Vie Sociale")

            tab1, tab2, tab3, tab4 = st.tabs(["🍖 Survie", "⚔️ Armée", "🏪 Objets", "👥 Vie Sociale"])

            with tab1:
                st.subheader("Nourriture & Soins")

                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Nourriture**")
                    if st.button(f"🍞 Encas (+25 Faim) - {PRIX_REPAS_SIMPLE}$"):
                        if me["ecus"] >= PRIX_REPAS_SIMPLE:
                            me["ecus"] -= PRIX_REPAS_SIMPLE
                            me["faim"] = min(me["faim_max"], me["faim"] + 25)
                            save_data(data)
                            st.rerun()

                    if st.button(f"🍞 Pain (+5 MaxFaim) - {PRIX_PAIN_MAX}$"):
                        if me["ecus"] >= PRIX_PAIN_MAX:
                            me["ecus"] -= PRIX_PAIN_MAX
                            me["faim_max"] += 5
                            me["faim"] += 5
                            save_data(data)
                            st.rerun()

                    # POMME - Prix dynamique selon la faim manquante
                    faim_manquante = me["faim_max"] - me["faim"]
                    if faim_manquante > 0:
                        # 1$ pour 5 points de faim manquants, arrondi à l'entier supérieur, minimum 1$
                        prix_pomme = max(1, (faim_manquante + 4) // 5)
                        if st.button(f"🍎 Pomme (Restaure toute la faim) - {prix_pomme}$"):
                            if me["ecus"] >= prix_pomme:
                                me["ecus"] -= prix_pomme
                                me["faim"] = me["faim_max"]
                                save_data(data)
                                st.rerun()
                            else:
                                st.error("💸 Pas assez d'argent")
                    else:
                        st.success("🍎 Pomme : Faim déjà au maximum")

                with col2:
                    st.write("**Soins**")
                    if st.button(f"🧪 Potion (+10 PV) - {PRIX_POTION}$"):
                        if me["ecus"] >= PRIX_POTION:
                            me["ecus"] -= PRIX_POTION
                            me["vie"] = min(me["vie_max"], me["vie"] + 10)
                            save_data(data)
                            st.rerun()

            with tab2:
                st.subheader("Recrutement militaire")

                for nom_u, stats in STATS_COMBAT.items():
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"{stats['icon']} **{nom_u}** - {stats['desc']} - Force: {stats['base']}")
                    if col2.button(f"{stats['cout']}$", key=f"rec_{nom_u}"):
                        if me["ecus"] >= stats['cout']:
                            me["ecus"] -= stats['cout']
                            me["armee"][nom_u] += 1
                            save_data(data)
                            st.rerun()

            with tab3:
                st.subheader("Boutique d'objets")

                for nom_obj, info in CATALOGUE_OBJETS.items():
                    deja_possede = helper.a_objet(nom_obj)
                    is_stackable = info.get("stackable", False)

                    # On affiche le bouton d'achat si l'objet n'est pas possédé OU s'il est cumulable
                    if deja_possede and not is_stackable:
                        st.success(f"✅ {info['icon']} {nom_obj} - Déjà possédé")
                    else:
                        col1, col2 = st.columns([3, 1])
                        titre = f"{info['icon']} **{nom_obj}** - {info['desc']}"

                        # Si cumulable et déjà possédé, on montre combien on en a
                        if is_stackable and deja_possede:
                            count = len([o for o in me["objets_reels"] if o["nom"] == nom_obj])
                            titre += f" (Possédé: {count})"

                        col1.write(titre)
                        col1.caption(info.get('help', ''))
                        if col2.button(f"{info['prix']}$", key=f"obj_{nom_obj}"):
                            if me["ecus"] >= info['prix']:
                                me["ecus"] -= info['prix']
                                me["objets_reels"].append({"nom": nom_obj, "type": info['type'], "valeur": info['prix']})
                                save_data(data)
                                st.rerun()

                st.divider()

                st.subheader("Éléments de construction / Décoration")
                choix_type = st.selectbox("Type", ["Élément de construction", "Décoration"])
                nom_custom = st.text_input("Nom de l'objet", "Monument")
                prix_custom = st.number_input("Prix à investir", 0, 500, 50)

                if st.button("Acheter"):
                    if me["ecus"] >= prix_custom:
                        me["ecus"] -= prix_custom
                        me["objets_reels"].append({"nom": nom_custom, "type": choix_type, "valeur": prix_custom})
                        save_data(data)
                        st.rerun()

                st.divider()

                st.subheader("🍖 Vente de gibier")
                cours = data["cours_gibier"]
                gibier = me.get("stock_gibier", {})

                for taille, icon in ICON_GIBIER.items():
                    if gibier.get(taille, 0) > 0:
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"{icon} {taille} - Stock: {gibier[taille]} - Prix: {cours[taille]}$/u")
                        if col2.button(f"Vendre", key=f"gib_{taille}"):
                            gibier[taille] -= 1
                            me["ecus"] += cours[taille]
                            save_data(data)
                            st.rerun()

                if me.get("stock_champignons", 0) > 0:
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"🍄 Champignons - Stock: {me['stock_champignons']} - Prix: {PRIX_CHAMPIGNON}$/u")
                    if col2.button(f"Vendre", key="champ"):
                        me["stock_champignons"] -= 1
                        me["ecus"] += PRIX_CHAMPIGNON
                        save_data(data)
                        st.rerun()

            with tab4:
                st.subheader("👥 Vie sociale")
                if not me.get("conjoint"):
                    st.write("Vous êtes célibataire. Se marier apporte un bonus de production croissant.")
                    if st.button(f"💍 Se marier (-{PRIX_MARIAGE}$)"):
                        if me["ecus"] >= PRIX_MARIAGE:
                            me["ecus"] -= PRIX_MARIAGE
                            me["conjoint"] = generer_conjoint(data["joueurs"])
                            save_data(data)
                            st.rerun()
                        else:
                            st.error("💸 Pas assez d'argent")
                else:
                    conj = me["conjoint"]
                    st.success(f"💑 Marié(e) avec {conj['nom']} depuis {conj['jours_mariage']} jours")
                    st.caption(f"Enfants: {me.get('enfants', 0)} 👶")

        elif phase == 4:
            st.header("🏗️ Phase 4 : Construction")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**🏠 Toits**")
                st.metric("Toits actuels", me.get("nb_toits", 0))
                nb = st.number_input("Nombre de toits", 0, 10, 0, key="toits")
                if st.button("Construire Toits"):
                    cout = nb * 2
                    if me["kaplas"] >= cout:
                        me["kaplas"] -= cout
                        me["nb_toits"] += nb
                        save_data(data)
                        st.rerun()

            with col2:
                st.write("**🗼 Tours**")
                st.metric("Tours actuelles", me.get("nb_tours", 0))
                nb_t = st.number_input("Nombre de tours", 0, 5, 0, key="tours")
                if st.button("Construire Tours"):
                    cout = nb_t * 2
                    if me["kaplas"] >= cout and me["armee"]["Archer"] >= nb_t:
                        me["kaplas"] -= cout
                        me["armee"]["Archer"] -= nb_t
                        me["nb_tours"] += nb_t
                        save_data(data)
                        st.rerun()

            with col3:
                st.write("**🌉 Pont**")
                pont_actuel = me.get("pont_construit", False)
                pont = st.checkbox("Construire un pont", value=pont_actuel, key="pont")
                if pont != pont_actuel:
                    me["pont_construit"] = pont
                    save_data(data)
                    st.rerun()

            st.divider()

            st.subheader("🏰 Fortifications")
            col_a, col_b = st.columns(2)

            with col_a:
                # 1. ENCEINTE (Pour la Guerre)
                enceinte = me.get("def_physique", {}).get("enceinte", False)
                st.write("**🛡️ Enceinte Fortifiée**")
                st.caption("Bonus : +50 Défense (Guerre)")

                if st.checkbox("Construire Enceinte", value=enceinte, key="enceinte_war"):
                    if not enceinte:
                        me["def_physique"]["enceinte"] = True
                        save_data(data)
                        st.rerun()
                else:
                    if enceinte:
                        me["def_physique"]["enceinte"] = False
                        save_data(data)
                        st.rerun()

            with col_b:
                # 2. PROTECTION CULTURES (Pour l'Événement Vol)
                prot_cult = me.get("def_physique", {}).get("protection_cultures", False)
                st.write("**🌾 Protection Cultures**")
                st.caption("Requis : Mur de 1 Kapla autour des champs (IRL)")

                if st.checkbox("Champs protégés (IRL)", value=prot_cult, key="prot_cult"):
                    if not prot_cult:
                        me["def_physique"]["protection_cultures"] = True
                        save_data(data)
                        st.rerun()
                else:
                    if prot_cult:
                        me["def_physique"]["protection_cultures"] = False
                        save_data(data)
                        st.rerun()

            # La porte reste en dessous ou à côté si tu veux, ou tu l'ajoutes à la suite
            porte = me.get("def_physique", {}).get("porte", False)
            if st.checkbox("Porte renforcée (+20 défense)", value=porte, key="porte"):
                if not porte:
                    me["def_physique"]["porte"] = True
                    save_data(data)
                    st.rerun()
            elif porte:
                me["def_physique"]["porte"] = False
                save_data(data)
                st.rerun()

        # BOUTON PRÊT EN BAS
        if phase > 0:
            st.divider()
            est_pret = st.session_state.user_name in data.get("joueurs_prets", [])

            if not est_pret:
                # Le joueur n'est pas encore prêt
                if st.button("✅ JE SUIS PRÊT", type="primary", use_container_width=True, key="btn_pret_footer"):
                    if st.session_state.user_name not in data.get("joueurs_prets", []):
                        data["joueurs_prets"].append(st.session_state.user_name)
                    st.session_state.auto_refresh = True
                    save_data(data)
                    st.rerun()
            else:
                # Le joueur est déjà prêt -> On lance la boucle d'attente
                st.success("✅ PRÊT - En attente des autres joueurs...")
                st.caption(f"Joueurs prêts: {len(data.get('joueurs_prets', []))}/{len(data['joueurs'])}")

                # --- CORRECTION : AJOUT DU REFRESH ---
                time.sleep(2)
                st.rerun()
