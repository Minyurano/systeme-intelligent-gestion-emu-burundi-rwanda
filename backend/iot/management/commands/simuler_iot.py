"""
Simulateur de capteurs : envoie une mesure par capteur toutes les N secondes,
comme le feraient les ESP32 sur le terrain. Pratique pour une démonstration en direct.

Usage : python manage.py simuler_iot --intervalle 5
"""
import math
import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from iot.models import Capteur
from iot.services import enregistrer_mesure


class Command(BaseCommand):
    help = "Simule des capteurs IoT qui envoient des mesures en continu."

    def add_arguments(self, parser):
        parser.add_argument("--intervalle", type=int, default=5, help="Secondes entre deux envois")
        parser.add_argument("--cycles", type=int, default=0, help="Nombre d'envois (0 = infini)")

    def handle(self, intervalle, cycles, **kw):
        n = 0
        self.stdout.write("Simulation en cours (Ctrl+C pour arrêter)...")
        try:
            while cycles == 0 or n < cycles:
                h = timezone.now().hour
                cycle = math.sin(2 * math.pi * (h - 6) / 24)
                for c in Capteur.objects.filter(actif=True):
                    base = c.derniere_valeur if c.derniere_valeur is not None else 5
                    if c.type == "TEMPERATURE":
                        v = 5 + 0.6 * cycle + random.gauss(0, 0.3)
                    elif c.type == "ENERGIE":
                        v = max(0, 18 * (0.4 + 0.8 * max(0, cycle)) + random.gauss(0, 1.5))
                    else:
                        v = max(0, base + random.gauss(0, 0.05 * max(base, 1)))
                    enregistrer_mesure(c, round(v, 2))
                    self.stdout.write(f"{c.code:15} {v:8.2f} {c.unite}")
                n += 1
                time.sleep(intervalle)
        except KeyboardInterrupt:
            self.stdout.write("Simulation arrêtée.")
