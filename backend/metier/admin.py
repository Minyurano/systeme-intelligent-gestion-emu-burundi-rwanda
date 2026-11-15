from django.contrib import admin

from .models import (
    Avis, Bail, Budget, Campagne, ClotureExercice, Constat, Demande, Echeance, Fournisseur, Loyer, OrdreTravail, PlanMaintenance,
)


class AvisEnLigne(admin.TabularInline):
    model = Avis
    extra = 0
    readonly_fields = ["utilisateur", "role", "niveau", "decision", "commentaire", "date"]


@admin.register(Demande)
class DemandeAdmin(admin.ModelAdmin):
    list_display = ("titre", "type", "district", "montant", "statut", "cree_le")
    list_filter = ("type", "statut")
    inlines = [AvisEnLigne]


@admin.register(Echeance)
class EcheanceAdmin(admin.ModelAdmin):
    list_display = ("libelle", "type", "date", "statut", "bien")
    list_filter = ("type", "statut")


class LoyerEnLigne(admin.TabularInline):
    model = Loyer
    extra = 0


@admin.register(Bail)
class BailAdmin(admin.ModelAdmin):
    list_display = ("locataire", "bien", "loyer_mensuel", "date_debut", "date_fin", "statut")
    inlines = [LoyerEnLigne]


@admin.register(OrdreTravail)
class OrdreTravailAdmin(admin.ModelAdmin):
    list_display = ("titre", "bien", "priorite", "statut", "origine", "cout_estime", "cout_reel")
    list_filter = ("statut", "priorite", "origine")


admin.site.register([Fournisseur, PlanMaintenance, Budget, ClotureExercice, Campagne, Constat])


from .models import MembreEglise  # noqa: E402


@admin.register(MembreEglise)
class MembreEgliseAdmin(admin.ModelAdmin):
    list_display = ("numero", "nom", "prenom", "sexe", "paroisse", "statut", "date_adhesion")
    list_filter = ("statut", "sexe", "paroisse__district")
    search_fields = ("numero", "nom", "prenom", "telephone")
    readonly_fields = ("numero", "enregistre_par", "cree_le", "modifie_le")


from .models import DemandeAcces  # noqa: E402


@admin.register(DemandeAcces)
class DemandeAccesAdmin(admin.ModelAdmin):
    list_display = ("nom_saisi", "numero_saisi", "telephone", "organisation", "verifiee", "statut", "cree_le")
    list_filter = ("statut", "verifiee", "organisation")
    search_fields = ("nom_saisi", "numero_saisi", "telephone")
    raw_id_fields = ("membre",)
