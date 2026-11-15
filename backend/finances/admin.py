from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "sens", "categorie", "montant", "devise", "district", "tiers", "est_anomalie", "verifiee")
    list_filter = ("sens", "categorie", "district", "canal", "est_anomalie", "verifiee")
    search_fields = ("tiers", "description", "reference_externe")
