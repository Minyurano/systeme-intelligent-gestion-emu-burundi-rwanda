from django.contrib import admin

from .models import District, JournalAction, Paroisse, Profil


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "siege", "surintendant")


@admin.register(Paroisse)
class ParoisseAdmin(admin.ModelAdmin):
    list_display = ("nom", "district", "pasteur", "membres")
    list_filter = ("district",)
    search_fields = ("nom",)


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "district")
    list_filter = ("role", "district")


@admin.register(JournalAction)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("date", "utilisateur", "action", "objet_type", "objet_libelle")
    list_filter = ("action", "objet_type")

    def has_change_permission(self, request, obj=None):
        return False  # le journal d'audit n'est pas modifiable

    def has_delete_permission(self, request, obj=None):
        return False
