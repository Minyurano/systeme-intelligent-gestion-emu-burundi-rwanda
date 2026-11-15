from django.contrib import admin

from .models import Alerte, Capteur, Mesure

admin.site.register(Capteur, list_display=("code", "type", "bien", "derniere_valeur", "derniere_mesure", "actif"))
admin.site.register(Alerte, list_display=("date", "niveau", "message", "resolue"), list_filter=("niveau", "resolue"))
admin.site.register(Mesure, list_display=("capteur", "horodatage", "valeur"), list_filter=("capteur",))
