#!/usr/bin/env python3
"""Bandeaux d'effets 128x32 (entrées 2688-2703) en français ; textes choisis à la main (vocabulaire officiel : technique / envoûtement)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_technique_banners import render

TEXTS = {
    2688: "Chance d'attaque !", 2689: 'Chance de technique !', 2690: 'PV restaurés', 2691: 'Énergie récupérée !',
    2692: 'Technique restaurée !', 2693: 'Envoûtement restauré !', 2694: 'Purification !', 2695: 'Esquive garantie !',
    2696: 'EXP en hausse !', 2697: 'Argent en hausse !', 2698: 'Prochain tour accéléré !', 2699: 'Un tour de plus !',
    2700: 'Envoûte tous les ennemis !', 2702: 'Dégâts subis réduits de moitié !', 2703: 'Encaisse 1 coup !',
}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for e, t in TEXTS.items(): render(t, 128, 32).save(os.path.join(a.out, f'{e}_0.png'))
    print(len(TEXTS), 'bandeaux ->', a.out)
