"""
Tâches automatiques, lancées chaque jour par `python manage.py executer_taches`
(Planificateur de tâches Windows, cron, ou le service « taches » de docker-compose.prod.yml).

Chaque tâche est idempotente : la relancer plusieurs fois le même jour ne crée pas de doublon.
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

from patrimoine.models import Bien, Document

from . import services
from .models import Bail, Echeance, OrdreTravail, PlanMaintenance

SEUIL_RISQUE = 70        # au-delà, un ordre de travail est ouvert automatiquement
HORIZON_PLAN = 15        # jours d'avance pour préparer un entretien préventif
CLE_DERNIERE = "umurage:taches:derniere"


def generer_loyers(j):
    n = 0
    for bail in Bail.objects.filter(statut=Bail.Statut.ACTIF):
        n += bail.generer_loyers(j)
        if bail.date_fin and bail.date_fin < j:
            bail.statut = Bail.Statut.TERMINE
            bail.save(update_fields=["statut"])
    return n


def _echeance_unique(origine, **champs):
    if Echeance.objects.filter(origine=origine, organisation_id=champs["organisation_id"]).exists():
        return 0
    Echeance.objects.create(origine=origine, **champs)
    return 1


def echeances_automatiques(j):
    n = 0
    for bail in Bail.objects.filter(statut=Bail.Statut.ACTIF, date_fin__isnull=False).select_related("bien__district"):
        d = bail.bien.district
        n += _echeance_unique(f"bail:{bail.pk}", organisation_id=d.organisation_id, district_id=d.pk, bien_id=bail.bien_id,
                              type=Echeance.Type.FIN_BAIL, libelle=f"Fin du bail de {bail.locataire} ({bail.objet or bail.bien.nom})",
                              date=bail.date_fin)
    for doc in Document.objects.filter(date_expiration__isnull=False, date_expiration__gte=j - timedelta(days=30)).select_related("bien__district"):
        org = doc.organisation_id or (doc.bien.district.organisation_id if doc.bien_id else None)
        if org is None:
            continue
        n += _echeance_unique(f"document:{doc.pk}:{doc.date_expiration:%Y%m%d}", organisation_id=org,
                              district_id=doc.district_id or (doc.bien.district_id if doc.bien_id else None), bien_id=doc.bien_id,
                              type=Echeance.Type.DOCUMENT, libelle=f"Renouveler : {doc.titre}", date=doc.date_expiration)
    return n


def ordres_depuis_plans(j):
    n = 0
    for plan in PlanMaintenance.objects.filter(actif=True, prochaine_date__lte=j + timedelta(days=HORIZON_PLAN)):
        if plan.ordres.filter(statut__in=OrdreTravail.OUVERTS).exists():
            continue
        OrdreTravail.objects.create(bien_id=plan.bien_id, titre=plan.libelle, type=OrdreTravail.Type.MAINTENANCE,
                                    statut=OrdreTravail.Statut.PLANIFIE, origine=OrdreTravail.Origine.PLAN, plan=plan,
                                    fournisseur_id=plan.fournisseur_id, cout_estime=plan.cout_estime, date_prevue=plan.prochaine_date)
        n += 1
    return n


def ordres_depuis_risques(j, organisation_id=None):
    """Le score de risque de l'IA devient une action : inspection prioritaire des biens les plus exposés."""
    qs = Bien.objects.filter(score_risque__gte=SEUIL_RISQUE, date_sortie__isnull=True)
    if organisation_id:
        qs = qs.filter(district__organisation_id=organisation_id)
    qs = qs.exclude(ordres_travail__statut__in=OrdreTravail.OUVERTS)
    n = 0
    for b in qs:
        OrdreTravail.objects.create(
            bien=b, titre=f"Inspection prioritaire — {b.nom}", type=OrdreTravail.Type.INSPECTION,
            priorite=OrdreTravail.Priorite.URGENTE if (b.score_risque or 0) >= 85 else OrdreTravail.Priorite.HAUTE,
            origine=OrdreTravail.Origine.RISQUE, date_prevue=j + timedelta(days=14),
            description=f"Score de risque {round(b.score_risque)}/100 calculé par l'IA (âge, état, entretien, alertes).",
        )
        n += 1
    return n


def executer_tout(j=None):
    j = j or date.today()
    bilan = {
        "loyers_generes": generer_loyers(j),
        "echeances_creees": echeances_automatiques(j),
        "ordres_plans": ordres_depuis_plans(j),
        "ordres_risques": ordres_depuis_risques(j),
        "rappels_envoyes": services.envoyer_rappels(j),
    }
    cache.set(CLE_DERNIERE, {"date": timezone.now().isoformat(), **bilan}, timeout=None)
    return bilan


def derniere_execution():
    return cache.get(CLE_DERNIERE)
