from django.contrib import admin

from .models import ComparableMarche, EntrainementModele

admin.site.register(ComparableMarche, list_display=("categorie", "district", "surface_m2", "prix_bif", "date"))
admin.site.register(EntrainementModele, list_display=("modele", "date", "nb_exemples", "metriques"))
