"""
Migration de données : les installations existantes (une seule Église) sont
rattachées à une organisation par défaut. Aucune donnée n'est perdue.
"""
from django.db import migrations


def rattacher(apps, schema_editor):
    Organisation = apps.get_model("core", "Organisation")
    District = apps.get_model("core", "District")
    Profil = apps.get_model("core", "Profil")
    JournalAction = apps.get_model("core", "JournalAction")
    Document = apps.get_model("patrimoine", "Document")
    if not (District.objects.filter(organisation__isnull=True).exists() or Profil.objects.filter(organisation__isnull=True).exists()):
        return
    org, _ = Organisation.objects.get_or_create(
        slug="emu-burundi",
        defaults={"nom": "Église Méthodiste Unie du Burundi", "sigle": "EMU Burundi", "pays": "Burundi",
                  "devise": "BIF", "taux_usd": 2950, "langue": "fr"},
    )
    District.objects.filter(organisation__isnull=True).update(organisation=org)
    Profil.objects.filter(organisation__isnull=True).update(organisation=org)
    JournalAction.objects.filter(organisation__isnull=True).update(organisation=org)
    Document.objects.filter(organisation__isnull=True).update(organisation=org)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organisation_alter_district_code_and_more"),
        ("patrimoine", "0002_document_organisation_alter_bien_code"),
    ]
    operations = [migrations.RunPython(rattacher, migrations.RunPython.noop)]
