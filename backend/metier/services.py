"""Règles métier : circuits de validation, exécution des décisions, notifications, exercices clôturés."""
import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.models import Profil
from finances.models import Transaction
from patrimoine.models import Mouvement
from patrimoine.whatsapp import envoyer

from .models import Avis, ClotureExercice, Demande, Echeance, OrdreTravail

log = logging.getLogger(__name__)
R = Profil.Role
T = Demande.Type

# Au-delà de ce montant (monnaie locale), la direction (évêque) valide en dernier
SEUIL_DIRECTION = Decimal(os.environ.get("SEUIL_APPROBATION_DIRECTION", "5000000"))


# ---------------------------------------------------------------------- Circuits
def circuit_pour(type_demande, montant):
    """Rôles qui valident, dans l'ordre. Les décisions sur le patrimoine remontent toujours à la direction."""
    montant = Decimal(montant or 0)
    if type_demande in (T.CESSION, T.ACQUISITION, T.TRANSFERT):
        return [R.SURINTENDANT, R.EVEQUE]
    circuit = [R.SURINTENDANT, R.TRESORIER]
    if montant >= SEUIL_DIRECTION:
        circuit.append(R.EVEQUE)
    return circuit


def peut_valider(profil, demande):
    """Le bon rôle, au bon niveau, dans le bon district, et jamais sur sa propre demande (séparation des tâches)."""
    role = demande.role_attendu
    if role is None or profil.organisation_id != demande.organisation_id:
        return False
    if demande.demandeur_id == profil.user_id:
        return False
    if demande.avis.filter(utilisateur_id=profil.user_id).exists():
        return False  # une même personne ne valide qu'une fois
    if profil.role != role:
        return False
    if role == R.SURINTENDANT and profil.district_id != demande.district_id:
        return False
    return True


def destinataires(organisation_id, role, district_id=None):
    qs = Profil.objects.filter(organisation_id=organisation_id, role=role, user__is_active=True)
    if role == R.SURINTENDANT and district_id:
        qs = qs.filter(district_id=district_id)
    return list(qs.select_related("user"))


def notifier(profils, texte):
    """Prévient par WhatsApp (si configuré ; sinon le message est journalisé). Renvoie le nombre de destinataires."""
    n = 0
    for p in profils:
        if p.telephone:
            envoyer(p.telephone, texte)
            n += 1
        else:
            log.info("Notification pour %s (pas de numéro) : %s", p.user.username, texte)
    return n


def _prevenir_niveau(demande):
    role = demande.role_attendu
    if role:
        notifier(destinataires(demande.organisation_id, role, demande.district_id),
                 f"UMURAGE — Validation attendue : {demande.get_type_display()} « {demande.titre} »"
                 f"{' — ' + f'{demande.montant:,.0f}'.replace(',', ' ') if demande.montant else ''}. Ouvrez l'application, rubrique Approbations.")


def creer_demande(demande):
    demande.circuit = circuit_pour(demande.type, demande.montant)
    demande.niveau = 0
    demande.statut = Demande.Statut.EN_ATTENTE
    if demande.type in (T.CESSION, T.TRANSFERT) and not demande.bien_id:
        raise ValidationError({"bien": "Indiquez le bien concerné."})
    if demande.type == T.TRANSFERT and not demande.district_destination_id:
        raise ValidationError({"district_destination": "Indiquez le district qui reçoit le bien."})
    demande.save()
    _prevenir_niveau(demande)
    return demande


def decider(demande, profil, decision, commentaire=""):
    if not peut_valider(profil, demande):
        raise PermissionDenied("Cette demande n'attend pas votre validation.")
    if decision == Avis.Decision.REJETE and not commentaire.strip():
        raise ValidationError({"commentaire": "Expliquez le motif du rejet."})
    Avis.objects.create(demande=demande, utilisateur=profil.user, role=profil.role, niveau=demande.niveau,
                        decision=decision, commentaire=commentaire)
    demandeur = destinataires_utilisateur(demande.demandeur_id)
    if decision == Avis.Decision.REJETE:
        demande.statut = Demande.Statut.REJETEE
        demande.decide_le = timezone.now()
        demande.save()
        notifier(demandeur, f"UMURAGE — Votre demande « {demande.titre} » a été rejetée : {commentaire}")
        return demande
    demande.niveau += 1
    if demande.niveau >= len(demande.circuit):
        demande.statut = Demande.Statut.APPROUVEE
        demande.decide_le = timezone.now()
        demande.save()
        notifier(demandeur, f"UMURAGE — Votre demande « {demande.titre} » est approuvée.")
    else:
        demande.save()
        _prevenir_niveau(demande)
    return demande


def destinataires_utilisateur(user_id):
    return list(Profil.objects.filter(user_id=user_id).select_related("user")) if user_id else []


def peut_executer(profil, demande):
    if demande.statut != Demande.Statut.APPROUVEE or profil.organisation_id != demande.organisation_id:
        return False
    if demande.type == T.DEPENSE:
        return profil.role in (R.TRESORIER, R.ADMIN)
    return profil.role in (R.EVEQUE, R.ADMIN, R.TRESORIER if demande.type == T.TRAVAUX else R.EVEQUE)


@db_transaction.atomic
def executer(demande, profil, date_execution=None):
    """Applique la décision approuvée sur le patrimoine et garde la trace de ce qui a été produit."""
    if not peut_executer(profil, demande):
        raise PermissionDenied("Vous ne pouvez pas exécuter cette demande.")
    jour = date_execution or date.today()
    auteur = profil.user.get_full_name() or profil.user.username
    bien = demande.bien
    if demande.type == T.CESSION:
        Mouvement.objects.create(bien=bien, type=Mouvement.Type.CESSION, date=jour, montant=demande.montant,
                                 description=f"Cession approuvée : {demande.titre}", auteur=auteur)
        bien.date_sortie = jour
        bien.save(update_fields=["date_sortie"])
        resultat = f"{bien.code} sorti de l'inventaire le {jour:%d/%m/%Y}"
        if demande.montant:
            verifier_exercice_ouvert(demande.organisation_id, jour)
            t = Transaction.objects.create(date=jour, sens=Transaction.Sens.RECETTE, categorie=Transaction.Categorie.CESSION,
                                           montant=demande.montant, devise=demande.organisation.devise, district=bien.district,
                                           bien=bien, tiers="", description=f"Produit de cession {bien.code}")
            resultat += f", recette enregistrée (transaction {t.pk})"
    elif demande.type == T.TRANSFERT:
        ancien = bien.district
        Mouvement.objects.create(bien=bien, type=Mouvement.Type.TRANSFERT, date=jour,
                                 description=f"Transfert de {ancien.nom} vers {demande.district_destination.nom}", auteur=auteur)
        bien.district, bien.paroisse = demande.district_destination, None
        bien.save(update_fields=["district", "paroisse"])
        resultat = f"{bien.code} transféré de {ancien.nom} vers {demande.district_destination.nom}"
    elif demande.type == T.TRAVAUX:
        ot = OrdreTravail.objects.create(bien=bien, titre=demande.titre, description=demande.description,
                                         cout_estime=demande.montant, origine=OrdreTravail.Origine.DEMANDE,
                                         statut=OrdreTravail.Statut.PLANIFIE, demande=demande, cree_par=profil.user) if bien else None
        resultat = f"Ordre de travail OT-{ot.pk} créé" if ot else "Travaux approuvés (aucun bien rattaché)"
    elif demande.type == T.DEPENSE:
        verifier_exercice_ouvert(demande.organisation_id, jour)
        t = Transaction.objects.create(date=jour, sens=Transaction.Sens.DEPENSE,
                                       categorie=demande.categorie_depense or Transaction.Categorie.FONCTIONNEMENT,
                                       montant=demande.montant, devise=demande.organisation.devise, district=demande.district,
                                       bien=bien, description=demande.titre[:255])
        resultat = f"Dépense enregistrée (transaction {t.pk})"
    else:  # ACQUISITION : le bien est ensuite enregistré dans l'inventaire
        resultat = "Acquisition autorisée : enregistrez le bien dans l'inventaire"
    demande.statut = Demande.Statut.EXECUTEE
    demande.execute_le = timezone.now()
    demande.resultat = resultat[:255]
    demande.save()
    return demande


# ---------------------------------------------------------------------- Exercices clôturés
def exercice_clos(organisation_id, jour):
    return bool(jour) and ClotureExercice.objects.filter(organisation_id=organisation_id, annee=jour.year).exists()


def verifier_exercice_ouvert(organisation_id, jour):
    if exercice_clos(organisation_id, jour):
        raise ValidationError({"date": f"L'exercice {jour.year} est clôturé : aucune écriture n'est plus possible sur cette année."})


# ---------------------------------------------------------------------- Échéances
def responsables_echeance(e):
    if e.responsable_id:
        r = destinataires_utilisateur(e.responsable_id)
        if r:
            return r
    if e.district_id:
        r = destinataires(e.organisation_id, R.SURINTENDANT, e.district_id)
        if r:
            return r
    return destinataires(e.organisation_id, R.EVEQUE) + destinataires(e.organisation_id, R.ADMIN)


def marquer_faite(e, jour=None):
    """Clôt l'échéance ; si elle est périodique, la suivante est créée aussitôt."""
    from .models import ajouter_mois

    e.statut, e.fait_le = Echeance.Statut.FAIT, jour or date.today()
    e.save(update_fields=["statut", "fait_le"])
    suivante = None
    if e.periodicite_mois:
        suivante = Echeance.objects.create(
            organisation_id=e.organisation_id, district_id=e.district_id, bien_id=e.bien_id, type=e.type, libelle=e.libelle,
            date=ajouter_mois(e.date, e.periodicite_mois), periodicite_mois=e.periodicite_mois, montant=e.montant,
            responsable_id=e.responsable_id, origine=e.origine,
        )
    return suivante


def envoyer_rappels(aujourd_hui=None):
    """Rappels J-30, J-7 et retard. Chaque rappel n'est envoyé qu'une fois."""
    j = aujourd_hui or date.today()
    n = 0
    for e in Echeance.objects.filter(statut=Echeance.Statut.A_FAIRE, date__lte=j + timedelta(days=30)).select_related("bien"):
        reste = (e.date - j).days
        champ = "rappel_retard" if reste < 0 else "rappel_j7" if reste <= 7 else "rappel_j30"
        if getattr(e, champ):
            continue
        quand = f"en retard de {-reste} jour(s)" if reste < 0 else "aujourd'hui" if reste == 0 else f"dans {reste} jour(s)"
        notifier(responsables_echeance(e), f"UMURAGE — Échéance {quand} : {e.libelle}"
                 f"{' (' + e.bien.code + ')' if e.bien else ''}, le {e.date:%d/%m/%Y}.")
        setattr(e, champ, True)
        if champ == "rappel_j7":
            e.rappel_j30 = True
        e.save(update_fields=["rappel_j30", "rappel_j7", "rappel_retard"])
        n += 1
    return n
