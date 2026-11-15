"""
Accès des membres de l'Église à UMURAGE.

Les administrateurs donnent (ou retirent) l'accès à l'espace membre aux fidèles inscrits au
registre officiel. Un fidèle peut aussi demander l'accès lui-même ; rien n'est ouvert sans
la décision d'un administrateur.

Ce qu'un membre voit dans son espace :
- sa fiche du registre et sa carte de membre (il corrige lui-même ses coordonnées) ;
- son église locale : pasteur, surintendant, communauté, biens (sans aucune valeur financière)
  et projets publics du district ;
- ses signalements (« le toit de l'école fuit »), qui suivent le circuit de validation habituel.

Il ne voit jamais : les finances, les valeurs des biens, les titres de propriété, les autres
membres, le journal, les tableaux de bord. Le cloisonnement est garanti côté serveur par la
permission par défaut `EstPersonnel` (voir core/securite.py).
"""
import re
import secrets
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from core.jetons import revoquer_tout
from core.models import JournalAction, Organisation, Profil
from core.fichiers import url_signee
from core.securite import EstMembre, JournalMixin, profil_de
from patrimoine.models import Bien, Declaration, Projet

from .models import DemandeAcces, MembreEglise

R = Profil.Role

# Rôles qui donnent et retirent les accès des membres (modifiable ici si l'Église le souhaite)
GESTIONNAIRES_ACCES = (R.ADMIN,)
MAX_GROUPE = 500

MOTS = ["Amahoro", "Urukundo", "Ukwizera", "Umucyo", "Ineza", "Ijambo", "Imana", "Umugisha", "Agaciro", "Ubumwe"]


def mot_de_passe_provisoire():
    """Facile à dicter au téléphone, difficile à deviner : Amahoro-4821-kqz."""
    lettres = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(3))
    return f"{secrets.choice(MOTS)}-{secrets.randbelow(9000) + 1000}-{lettres}"


def _chiffres(n):
    return re.sub(r"\D", "", n or "")


def memes_numeros(a, b):
    """+257 79 00 00 01 et 79000001 désignent le même téléphone (on compare les 8 derniers chiffres)."""
    a, b = _chiffres(a), _chiffres(b)
    return len(a) >= 8 and len(b) >= 8 and a[-8:] == b[-8:]


def _gestionnaire(request):
    profil = profil_de(request.user)
    if profil is None or profil.role not in GESTIONNAIRES_ACCES:
        raise PermissionDenied("Seul un administrateur peut donner ou retirer l'accès des membres.")
    return profil


def _journal(request, action_, fiche, details):
    profil = profil_de(request.user)
    JournalAction.objects.create(
        organisation_id=profil.organisation_id, utilisateur=request.user, action=action_,
        objet_type="Accès membre", objet_id=str(fiche.pk), objet_libelle=str(fiche)[:255], details=details,
    )


def _message_identifiants(fiche, identifiant, mdp, adresse):
    org = fiche.paroisse.district.organisation
    return (f"Bonjour {fiche.prenom}, votre accès à l'espace membre de {org.nom} est ouvert.\n"
            f"Adresse : {adresse}\nIdentifiant : {identifiant}\nMot de passe provisoire : {mdp}\n"
            "Vous choisirez votre propre mot de passe à la première connexion. Ne le communiquez à personne.")


def _envoyer_whatsapp(telephone, texte):
    from patrimoine import whatsapp
    # Sans API branchée, on n'appelle pas envoyer() : il écrirait le mot de passe provisoire dans les journaux du serveur
    return bool(telephone) and whatsapp.configure() and whatsapp.envoyer(telephone, texte)


class AccesRefuse(ValidationError):
    """Refus motivé ; `code` permet à l'interface de proposer la bonne action (ex. saisir l'accord parental)."""

    def __init__(self, message, code, **extra):
        super().__init__({"detail": message, "code": code, **extra})
        self.message, self.raison = message, code


def verifier_age(fiche, request, accord=None):
    """
    Règle des mineurs : sous l'âge fixé par l'organisation (16 ans par défaut), l'accès n'est ouvert
    qu'avec l'accord d'un parent ou tuteur, enregistré sur la fiche et au journal d'audit.
    La date de naissance est donc obligatoire pour ouvrir un accès.
    """
    org = fiche.paroisse.district.organisation
    age = fiche.age()
    if age is None:
        raise AccesRefuse("Renseignez d'abord la date de naissance dans le registre : elle est nécessaire pour appliquer "
                          "la règle des mineurs.", "date_naissance_manquante")
    if age >= org.age_minimum_acces or fiche.accord_parental_nom:
        return
    accord = accord or {}
    nom, lien = (accord.get("nom") or "").strip()[:120], (accord.get("lien") or "").strip()[:40]
    if len(nom) < 4 or not lien or not accord.get("confirme"):
        raise AccesRefuse(f"{fiche.prenom} a {age} ans (moins de {org.age_minimum_acces} ans) : l'accord d'un parent ou "
                          "tuteur est nécessaire. Indiquez son nom, son lien et confirmez que vous l'avez recueilli.",
                          "accord_parental_requis", age=age, age_minimum=org.age_minimum_acces)
    fiche.accord_parental_nom, fiche.accord_parental_lien = nom, lien
    fiche.accord_parental_le, fiche.accord_parental_par = date.today(), request.user
    fiche.save(update_fields=["accord_parental_nom", "accord_parental_lien", "accord_parental_le", "accord_parental_par"])
    _journal(request, "MODIFICATION", fiche, {"accord_parental": {"nom": nom, "lien": lien, "age": age}})


@transaction.atomic
def accorder_acces(fiche, request, envoyer=False, accord=None):
    """
    Crée (ou réactive) le compte du membre avec un mot de passe provisoire.
    Renvoie un dict avec l'identifiant et le mot de passe à transmettre au membre.
    """
    if not fiche.actif:
        raise AccesRefuse(f"{fiche.prenom} {fiche.nom} est « {fiche.get_statut_display().lower()} » : "
                          "seuls les membres actifs reçoivent un accès.", "membre_inactif")
    verifier_age(fiche, request, accord)
    org = fiche.paroisse.district.organisation
    mdp = mot_de_passe_provisoire()
    if fiche.compte_id:
        u = fiche.compte
        if getattr(u, "profil", None) and not u.profil.est_membre_simple:
            raise ValidationError("Cette fiche est liée au compte d'un responsable : gérez-le dans Paramètres.")
        u.is_active = True
        u.set_password(mdp)
        u.save()
        revoquer_tout(u)  # l'ancien mot de passe et les sessions ouvertes ne servent plus
        nouveau = False
    else:
        base = fiche.numero
        identifiant, n = base, 2
        while User.objects.filter(username__iexact=identifiant).exists():
            identifiant, n = f"{base}-{n}", n + 1
        u = User.objects.create_user(identifiant, password=mdp, first_name=fiche.prenom, last_name=fiche.nom)
        fiche.compte = u
        fiche.save(update_fields=["compte"])
        nouveau = True
    profil, _ = Profil.objects.update_or_create(user=u, defaults={
        "organisation": org, "role": R.MEMBRE, "district": fiche.paroisse.district,
        "telephone": re.sub(r"[^\d+]", "", fiche.telephone or ""), "doit_changer_mdp": True,
    })
    adresse = request.build_absolute_uri("/connexion")
    envoye = _envoyer_whatsapp(fiche.telephone, _message_identifiants(fiche, u.username, mdp, adresse)) if envoyer else False
    _journal(request, "CREATION" if nouveau else "MODIFICATION", fiche,
             {"acces": "accordé" if nouveau else "réactivé, nouveau mot de passe provisoire", "identifiant": u.username,
              "whatsapp": envoye})
    return {"fiche": fiche.id, "numero": fiche.numero, "nom": f"{fiche.prenom} {fiche.nom}", "paroisse": fiche.paroisse.nom,
            "telephone": fiche.telephone, "identifiant": u.username, "mot_de_passe": mdp, "whatsapp_envoye": envoye,
            "adresse": adresse}


# ====================================================================== Administration des accès

class AccesMembreSerializer(serializers.ModelSerializer):
    paroisse_nom = serializers.CharField(source="paroisse.nom", read_only=True)
    district_nom = serializers.CharField(source="paroisse.district.nom", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    actif = serializers.BooleanField(read_only=True)
    acces = serializers.SerializerMethodField()

    class Meta:
        model = MembreEglise
        fields = ["id", "numero", "prenom", "nom", "sexe", "telephone", "paroisse", "paroisse_nom", "district_nom",
                  "statut", "statut_libelle", "actif", "photo", "acces", "age", "mineur", "accord_parental"]

    age = serializers.SerializerMethodField()
    mineur = serializers.SerializerMethodField()
    accord_parental = serializers.SerializerMethodField()

    def get_age(self, m):
        return m.age()

    def get_mineur(self, m):
        a = m.age()
        return a is not None and a < m.paroisse.district.organisation.age_minimum_acces

    def get_accord_parental(self, m):
        if not m.accord_parental_nom:
            return None
        return {"nom": m.accord_parental_nom, "lien": m.accord_parental_lien, "le": m.accord_parental_le}

    def get_acces(self, m):
        u = m.compte
        if u is None:
            return None
        p = getattr(u, "profil", None)
        return {"identifiant": u.username, "actif": u.is_active, "derniere_connexion": u.last_login,
                "cree_le": u.date_joined, "doit_changer_mdp": bool(p and p.doit_changer_mdp),
                "double_authentification": bool(p and p.totp_actif)}


class AccesMembresViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Accès des fidèles à l'espace membre, géré par les administrateurs.

    Filtre `etat` : sans (pas encore d'accès), avec (accès actif), suspendu, attente (mot de passe provisoire pas encore changé).
    """

    serializer_class = AccesMembreSerializer
    filterset_fields = ["paroisse", "statut", "paroisse__district"]
    search_fields = ["nom", "prenom", "numero", "telephone", "compte__username"]
    ordering_fields = ["nom", "numero", "compte__last_login"]

    def get_queryset(self):
        profil = _gestionnaire(self.request)
        qs = (MembreEglise.objects.filter(paroisse__district__organisation_id=profil.organisation_id)
              .select_related("paroisse", "paroisse__district", "compte", "compte__profil").order_by("nom", "prenom"))
        etat = self.request.query_params.get("etat")
        if etat == "sans":
            qs = qs.filter(compte__isnull=True, statut__in=MembreEglise.ACTIFS)
        elif etat == "avec":
            qs = qs.filter(compte__isnull=False, compte__is_active=True)
        elif etat == "suspendu":
            qs = qs.filter(compte__isnull=False, compte__is_active=False)
        elif etat == "attente":
            qs = qs.filter(compte__is_active=True, compte__profil__doit_changer_mdp=True)
        return qs

    @action(detail=True, methods=["post"])
    def accorder(self, request, pk=None):
        """Donne l'accès (ou le rétablit avec un nouveau mot de passe provisoire)."""
        fiche = self.get_object()
        return Response(accorder_acces(fiche, request, envoyer=bool(request.data.get("envoyer_whatsapp")),
                                       accord=request.data.get("accord_parental")), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reinitialiser(self, request, pk=None):
        """Mot de passe oublié : nouveau mot de passe provisoire."""
        fiche = self.get_object()
        if not fiche.compte_id:
            raise ValidationError("Ce membre n'a pas encore d'accès.")
        return Response(accorder_acces(fiche, request, envoyer=bool(request.data.get("envoyer_whatsapp"))))

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        fiche = self.get_object()
        if not fiche.compte_id:
            raise ValidationError("Ce membre n'a pas d'accès.")
        fiche.compte.is_active = False
        fiche.compte.save(update_fields=["is_active"])
        revoquer_tout(fiche.compte)
        _journal(request, "MODIFICATION", fiche, {"acces": "suspendu", "motif": request.data.get("motif", "")[:200]})
        return Response(self.get_serializer(fiche).data)

    @action(detail=True, methods=["post"])
    def reactiver(self, request, pk=None):
        fiche = self.get_object()
        if not fiche.compte_id:
            raise ValidationError("Ce membre n'a pas d'accès.")
        if not fiche.actif:
            raise ValidationError("Un membre transféré ou décédé ne peut pas retrouver l'accès.")
        fiche.compte.is_active = True
        fiche.compte.save(update_fields=["is_active"])
        _journal(request, "MODIFICATION", fiche, {"acces": "réactivé"})
        return Response(self.get_serializer(fiche).data)

    @action(detail=True, methods=["post"])
    def retirer(self, request, pk=None):
        """Supprime définitivement le compte (la fiche du registre est conservée)."""
        fiche = self.get_object()
        u = fiche.compte
        if u is None:
            raise ValidationError("Ce membre n'a pas d'accès.")
        if getattr(u, "profil", None) and not u.profil.est_membre_simple:
            raise ValidationError("Ce compte est celui d'un responsable : gérez-le dans Paramètres.")
        identifiant = u.username
        fiche.compte = None
        fiche.save(update_fields=["compte"])
        revoquer_tout(u)
        u.delete()
        _journal(request, "SUPPRESSION", fiche, {"acces": "retiré", "identifiant": identifiant})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="accorder-groupe")
    def accorder_groupe(self, request):
        """
        Donne l'accès à plusieurs membres d'un coup : une liste d'identifiants de fiches (`ids`),
        ou tous les membres actifs sans accès d'une église locale (`paroisse`), avec `avec_telephone` facultatif.
        Renvoie les identifiants et mots de passe provisoires, à imprimer ou envoyer.
        """
        qs = self.get_queryset().filter(compte__isnull=True, statut__in=MembreEglise.ACTIFS)
        ids, paroisse = request.data.get("ids"), request.data.get("paroisse")
        if ids:
            qs = qs.filter(pk__in=[int(i) for i in ids if str(i).isdigit()])
        elif paroisse:
            qs = qs.filter(paroisse_id=paroisse)
        else:
            raise ValidationError("Choisissez des membres ou une église locale.")
        if request.data.get("avec_telephone"):
            qs = qs.exclude(telephone="")
        fiches = list(qs[:MAX_GROUPE])
        if not fiches:
            raise ValidationError("Aucun membre actif sans accès ne correspond.")
        envoyer = bool(request.data.get("envoyer_whatsapp"))
        resultats, ignores = [], []
        for f in fiches:
            try:
                resultats.append(accorder_acces(f, request, envoyer=envoyer))
            except AccesRefuse as e:
                # Mineurs sans accord, date de naissance manquante : à traiter un par un
                ignores.append({"fiche": f.id, "numero": f.numero, "nom": f"{f.prenom} {f.nom}", "raison": e.raison, "message": e.message})
        return Response({"crees": resultats, "nombre": len(resultats), "ignores": ignores,
                         "limite_atteinte": len(fiches) == MAX_GROUPE}, status=status.HTTP_201_CREATED)

    @action(detail=False)
    def statistiques(self, request):
        profil = _gestionnaire(request)
        base = MembreEglise.objects.filter(paroisse__district__organisation_id=profil.organisation_id)
        actifs = base.filter(statut__in=MembreEglise.ACTIFS)
        avec = base.filter(compte__isnull=False)
        il_y_a_30j = timezone.now() - timedelta(days=30)
        return Response({
            "membres_actifs": actifs.count(),
            "avec_acces": avec.filter(compte__is_active=True).count(),
            "sans_acces": actifs.filter(compte__isnull=True).count(),
            "suspendus": avec.filter(compte__is_active=False).count(),
            "en_attente_premiere_connexion": avec.filter(compte__is_active=True, compte__profil__doit_changer_mdp=True).count(),
            "connectes_30j": avec.filter(compte__last_login__gte=il_y_a_30j).count(),
            "demandes_en_attente": DemandeAcces.objects.filter(organisation_id=profil.organisation_id,
                                                               statut=DemandeAcces.Statut.EN_ATTENTE).count(),
            "demandes_ouvertes": profil.organisation.demandes_acces_ouvertes,
        })


class DemandeAccesSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    membre_detail = serializers.SerializerMethodField()
    traitee_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = DemandeAcces
        exclude = ["organisation"]

    def get_membre_detail(self, d):
        m = d.membre
        if m is None:
            return None
        age = m.age()
        return {"id": m.id, "numero": m.numero, "nom": f"{m.prenom} {m.nom}", "paroisse_nom": m.paroisse.nom, "age": age,
                "mineur": age is not None and age < m.paroisse.district.organisation.age_minimum_acces,
                "accord_parental": bool(m.accord_parental_nom),
                "telephone": m.telephone, "statut_libelle": m.get_statut_display(), "a_deja_acces": bool(m.compte_id and m.compte.is_active)}

    def get_traitee_par_nom(self, d):
        u = d.traitee_par
        return (u.get_full_name() or u.username) if u else None


class DemandeAccesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = DemandeAccesSerializer
    filterset_fields = ["statut", "verifiee"]
    search_fields = ["nom_saisi", "numero_saisi", "telephone"]

    def get_queryset(self):
        profil = _gestionnaire(self.request)
        return (DemandeAcces.objects.filter(organisation_id=profil.organisation_id)
                .select_related("membre", "membre__paroisse", "membre__compte", "traitee_par"))

    def _a_traiter(self):
        d = self.get_object()
        if d.statut != DemandeAcces.Statut.EN_ATTENTE:
            raise ValidationError("Cette demande a déjà été traitée.")
        return d

    @action(detail=True, methods=["post"])
    def accorder(self, request, pk=None):
        """Accorde l'accès. L'administrateur peut rattacher la demande à une autre fiche (`membre`)."""
        d = self._a_traiter()
        if request.data.get("membre"):
            d.membre = MembreEglise.objects.filter(
                pk=request.data["membre"], paroisse__district__organisation_id=d.organisation_id).first()
        if d.membre is None:
            raise ValidationError("Rattachez d'abord cette demande à une fiche du registre (recherchez le membre).")
        if d.membre.compte_id and d.membre.compte.is_active:
            raise ValidationError("Ce membre a déjà un accès actif. Utilisez « Nouveau mot de passe » si besoin.")
        resultat = accorder_acces(d.membre, request, envoyer=False, accord=request.data.get("accord_parental"))
        # Les identifiants partent au numéro de la demande, qui a été vérifié par l'administrateur
        if request.data.get("envoyer_whatsapp", True):
            resultat["whatsapp_envoye"] = _envoyer_whatsapp(
                d.telephone, _message_identifiants(d.membre, resultat["identifiant"], resultat["mot_de_passe"], resultat["adresse"]))
        d.statut, d.traitee_par, d.traitee_le = DemandeAcces.Statut.ACCORDEE, request.user, timezone.now()
        d.save()
        return Response(resultat)

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        d = self._a_traiter()
        d.statut, d.traitee_par, d.traitee_le = DemandeAcces.Statut.REFUSEE, request.user, timezone.now()
        d.motif_refus = (request.data.get("motif") or "")[:255]
        d.save()
        if request.data.get("prevenir", True):
            _envoyer_whatsapp(d.telephone, "Votre demande d'accès à l'espace membre n'a pas pu être acceptée"
                              + (f" : {d.motif_refus}" if d.motif_refus else ".") + " Rapprochez-vous de votre pasteur.")
        return Response(self.get_serializer(d).data)


# ====================================================================== Demande publique

class DemandeAccesThrottle(AnonRateThrottle):
    rate = "5/hour"


@api_view(["GET"])
@permission_classes([AllowAny])
def organisations_acces(request):
    """Organisations dont les membres peuvent demander un accès."""
    qs = Organisation.objects.filter(demandes_acces_ouvertes=True).exclude(statut=Organisation.Statut.SUSPENDU)
    return Response(list(qs.values("slug", "nom", "sigle", "pays")))


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([DemandeAccesThrottle])
def demander_acces(request):
    """
    Un fidèle demande l'accès. La réponse est toujours la même, que le numéro de membre existe
    ou non : on ne révèle jamais qui est inscrit au registre.
    """
    d = request.data
    org = Organisation.objects.filter(slug=d.get("organisation"), demandes_acces_ouvertes=True).exclude(
        statut=Organisation.Statut.SUSPENDU).first()
    nom, telephone = (d.get("nom") or "").strip(), (d.get("telephone") or "").strip()
    erreurs = {}
    if org is None:
        erreurs["organisation"] = "Choisissez votre Église."
    if len(nom) < 4:
        erreurs["nom"] = "Indiquez votre prénom et votre nom."
    if len(_chiffres(telephone)) < 8:
        erreurs["telephone"] = "Indiquez un numéro de téléphone valide."
    if erreurs:
        raise ValidationError(erreurs)
    numero = (d.get("numero") or "").strip().upper()[:24]
    fiche = MembreEglise.objects.filter(numero__iexact=numero, paroisse__district__organisation=org).first() if numero else None
    verifiee = bool(fiche and memes_numeros(fiche.telephone, telephone))
    deja = DemandeAcces.objects.filter(organisation=org, statut=DemandeAcces.Statut.EN_ATTENTE).filter(
        Q(telephone=telephone) | (Q(membre=fiche) if fiche else Q(pk__in=[]))).exists()
    if not deja:
        DemandeAcces.objects.create(organisation=org, membre=fiche, numero_saisi=numero, nom_saisi=nom[:160],
                                    telephone=telephone[:30], message=(d.get("message") or "")[:500], verifiee=verifiee)
    return Response({"ok": True, "message": "Votre demande est enregistrée. Un administrateur de votre Église va la vérifier ; "
                     "vous recevrez vos identifiants sur ce numéro."}, status=status.HTTP_201_CREATED)


# ====================================================================== Espace membre

def _fiche(request):
    fiche = getattr(request.user, "fiche_membre", None)
    if fiche is None:
        raise PermissionDenied("Votre compte n'est relié à aucune fiche du registre. Contactez l'administrateur.")
    return fiche


def _bien_public(b, request=None):
    return {"id": b.id, "code": b.code, "nom": b.nom, "categorie": b.categorie, "categorie_libelle": b.get_categorie_display(),
            "sous_type": b.sous_type, "etat": b.etat, "etat_libelle": b.get_etat_display(),
            "photo": url_signee(b.photo, getattr(request, "user", None), request), "beneficiaires": b.beneficiaires}


def _biens_visibles(fiche):
    """Biens de l'église locale du membre, et biens communs de son district (non rattachés à une paroisse)."""
    return (Bien.objects.filter(date_sortie__isnull=True, district_id=fiche.paroisse.district_id)
            .filter(Q(paroisse_id=fiche.paroisse_id) | Q(paroisse__isnull=True)).order_by("paroisse_id", "nom"))


@api_view(["GET"])
@permission_classes([EstMembre])
def espace_membre(request):
    fiche = _fiche(request)
    paroisse, district = fiche.paroisse, fiche.paroisse.district
    org = district.organisation
    communaute = MembreEglise.objects.filter(paroisse=paroisse, statut__in=MembreEglise.ACTIFS)
    debut_annee = date(date.today().year, 1, 1)
    projets = Projet.objects.filter(district=district, public=True).order_by("statut", "nom")
    return Response({
        "fiche": {
            "id": fiche.id, "numero": fiche.numero, "prenom": fiche.prenom, "nom": fiche.nom, "sexe": fiche.sexe,
            "date_naissance": fiche.date_naissance, "lieu_naissance": fiche.lieu_naissance, "telephone": fiche.telephone,
            "adresse": fiche.adresse, "profession": fiche.profession, "situation_familiale": fiche.situation_familiale,
            "situation_libelle": fiche.get_situation_familiale_display() if fiche.situation_familiale else "",
            "statut": fiche.statut, "statut_libelle": fiche.get_statut_display(), "date_adhesion": fiche.date_adhesion,
            "date_bapteme": fiche.date_bapteme, "date_confirmation": fiche.date_confirmation, "ministere": fiche.ministere,
            "photo": url_signee(fiche.photo, request.user, request), "paroisse_nom": paroisse.nom, "district_nom": district.nom,
        },
        "eglise": {
            "nom": paroisse.nom, "pasteur": paroisse.pasteur, "district": district.nom, "surintendant": district.surintendant,
            "siege": district.siege, "membres_declares": paroisse.membres, "membres_inscrits": communaute.count(),
            "nouveaux_annee": communaute.filter(date_adhesion__gte=debut_annee).count(),
            "baptemes_annee": MembreEglise.objects.filter(paroisse=paroisse, date_bapteme__gte=debut_annee).count(),
        },
        "organisation": {"nom": org.nom, "sigle": org.sigle, "slug": org.slug, "whatsapp": org.whatsapp_numero,
                         "portail_public": org.portail_public},
        "biens": [_bien_public(b, request) for b in _biens_visibles(fiche)[:60]],
        "projets": [{"id": p.id, "nom": p.nom, "domaine": p.get_domaine_display(), "statut": p.statut,
                     "statut_libelle": p.get_statut_display(), "avancement": p.avancement, "beneficiaires": p.beneficiaires,
                     "financeur": p.financeur} for p in projets[:30]],
        "signalements_en_attente": Declaration.objects.filter(auteur=request.user, statut=Declaration.Statut.EN_ATTENTE).count(),
    })


CHAMPS_MODIFIABLES = ("telephone", "adresse", "profession", "situation_familiale")


@api_view(["PATCH"])
@permission_classes([EstMembre])
def mes_coordonnees(request):
    """Le membre tient lui-même ses coordonnées à jour ; chaque changement est inscrit au journal d'audit."""
    fiche = _fiche(request)
    changements = {}
    for champ in CHAMPS_MODIFIABLES:
        if champ not in request.data:
            continue
        valeur = str(request.data.get(champ) or "").strip()[:160]
        if champ == "situation_familiale" and valeur and valeur not in MembreEglise.Situation.values:
            raise ValidationError({champ: "Valeur inconnue."})
        if champ == "telephone" and valeur and len(_chiffres(valeur)) < 8:
            raise ValidationError({champ: "Numéro de téléphone invalide."})
        if valeur != getattr(fiche, champ):
            changements[champ] = {"avant": getattr(fiche, champ), "apres": valeur}
            setattr(fiche, champ, valeur)
    if changements:
        fiche.save()
        if "telephone" in changements:  # le numéro sert aussi aux signalements par WhatsApp
            Profil.objects.filter(user=request.user).update(telephone=re.sub(r"[^\d+]", "", fiche.telephone))
        JournalAction.objects.create(organisation_id=fiche.paroisse.district.organisation_id, utilisateur=request.user,
                                     action="MODIFICATION", objet_type="Membre De L'Église", objet_id=str(fiche.pk),
                                     objet_libelle=str(fiche)[:255], details={"par_le_membre": True, **changements})
    return Response({"ok": True, "modifies": list(changements)})


class SignalementSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    bien_code = serializers.CharField(source="bien.code", default=None, read_only=True)
    bien_nom = serializers.CharField(source="bien.nom", default=None, read_only=True)
    bien_signale = serializers.SerializerMethodField()

    class Meta:
        model = Declaration
        fields = ["id", "texte", "statut", "statut_libelle", "motif_rejet", "recue_le", "traitee_le", "bien_code", "bien_nom",
                  "bien_signale", "media_type"]

    def get_bien_signale(self, d):
        return (d.interpretation or {}).get("bien_existant")


@api_view(["GET", "POST"])
@permission_classes([EstMembre])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def mes_signalements(request):
    """Le membre signale un problème ou un bien ; le surintendant valide comme pour WhatsApp."""
    fiche = _fiche(request)
    if request.method == "GET":
        qs = Declaration.objects.filter(auteur=request.user).select_related("bien").order_by("-recue_le")[:50]
        return Response(SignalementSerializer(qs, many=True).data)
    texte = (request.data.get("texte") or "").strip()
    if len(texte) < 10:
        raise ValidationError({"texte": "Décrivez le problème en une phrase (10 caractères au moins)."})
    bien = None
    if request.data.get("bien"):
        bien = _biens_visibles(fiche).filter(pk=request.data["bien"]).first()
        if bien is None:
            raise ValidationError({"bien": "Ce bien n'appartient pas à votre église locale."})
    media = None
    photo = request.FILES.get("photo")
    if photo:
        if photo.size > 5 * 1024 * 1024 or not (photo.content_type or "").startswith("image/"):
            raise ValidationError({"photo": "Une image de 5 Mo au plus."})
        media = {"contenu": photo.read(), "type": "image", "nom": photo.name}
    from patrimoine import whatsapp
    profil = profil_de(request.user)
    d, reponse = whatsapp.traiter_message_profil(profil, fiche.telephone or "espace-membre", texte, media,
                                                 canal=Declaration.Canal.WEB, bien=bien)
    return Response({"signalement": SignalementSerializer(d).data, "message": reponse}, status=status.HTTP_201_CREATED)
