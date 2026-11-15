from django.contrib import admin

from .models import Bien, Document, Mouvement, Projet


class MouvementInline(admin.TabularInline):
    model = Mouvement
    extra = 0


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "categorie", "district", "etat", "statut_juridique", "valeur_estimee", "score_risque")
    list_filter = ("categorie", "district", "etat", "statut_juridique")
    search_fields = ("code", "nom", "sous_type")
    inlines = [MouvementInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("titre", "type", "district", "bien", "date")
    list_filter = ("type", "district")
    search_fields = ("titre", "contenu")


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ("nom", "domaine", "district", "statut", "avancement", "budget", "public")
    list_filter = ("domaine", "district", "statut", "public")
