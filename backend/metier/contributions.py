"""
Dîmes, offrandes et cotisations des membres ; reçus numérotés ; attestation annuelle vérifiable.

- Saisie par les responsables de l'église locale (agent, surintendant) ou par le trésorier.
- Chaque contribution reçoit un numéro de reçu définitif (SIGLE-ANNÉE-NNNNNN, attribué sous verrou)
  et alimente la comptabilité : une recette « Dîmes et offrandes » est créée dans les transactions.
- Une erreur ne se supprime pas : elle s'annule avec un motif (trésorier ou administrateur), tant que
  l'exercice n'est pas clôturé. Tout passe au journal d'audit.
- Le membre voit ses dons dans son espace et télécharge son attestation annuelle. L'attestation porte
  un QR code : n'importe qui peut vérifier qu'elle est authentique, sans voir le détail des dons.
"""
import base64
import io
import secrets
from datetime import date
from decimal import Decimal

import qrcode
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.models import JournalAction, Profil
from core.securite import DistrictScopedMixin, EstMembre, JournalMixin, profil_de
from finances.models import Transaction

from . import services
from .models import AttestationAnnuelle, Contribution, MembreEglise

R = Profil.Role
SAISIE = (R.ADMIN, R.TRESORIER, R.SURINTENDANT, R.AGENT)
ANNULATION = (R.ADMIN, R.TRESORIER)
MODE_VERS_CANAL = {"ESPECES": "ESPECES", "MOBILE": "MOBILE", "BANQUE": "BANQUE", "NATURE": "ESPECES"}


def _nom_membre(m):
    return f"{m.prenom} {m.nom}" if m else None


class ContributionSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    mode_libelle = serializers.CharField(source="get_mode_display", read_only=True)
    paroisse_nom = serializers.CharField(source="paroisse.nom", read_only=True)
    district_nom = serializers.CharField(source="paroisse.district.nom", read_only=True)
    membre_nom = serializers.SerializerMethodField()
    membre_numero = serializers.CharField(source="membre.numero", default=None, read_only=True)
    enregistre_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Contribution
        exclude = ["organisation", "transaction"]
        read_only_fields = ["numero_recu", "enregistre_par", "cree_le", "annulee", "annulee_le", "annulee_par", "motif_annulation"]
        extra_kwargs = {"paroisse": {"required": False}}  # par défaut : l'église locale du membre

    def get_membre_nom(self, c):
        return _nom_membre(c.membre)

    def get_enregistre_par_nom(self, c):
        u = c.enregistre_par
        return (u.get_full_name() or u.username) if u else None

    def validate_montant(self, v):
        if v is None or v <= 0:
            raise serializers.ValidationError("Le montant doit être positif.")
        if v > Decimal("10000000000"):
            raise serializers.ValidationError("Montant anormalement élevé : vérifiez la saisie.")
        return v

    def validate(self, data):
        membre, paroisse = data.get("membre"), data.get("paroisse")
        if data.get("date") and data["date"] > date.today():
            raise serializers.ValidationError({"date": "La date ne peut pas être dans le futur."})
        if membre is not None:
            if not membre.actif and membre.statut != MembreEglise.Statut.TRANSFERE:
                raise serializers.ValidationError({"membre": f"{membre.prenom} {membre.nom} est « {membre.get_statut_display().lower()} »."})
            data.setdefault("paroisse", membre.paroisse)
            paroisse = data["paroisse"]
        if paroisse is None:
            raise serializers.ValidationError({"paroisse": "Choisissez l'église locale qui reçoit la contribution."})
        if data.get("mode") == Contribution.Mode.MOBILE and not data.get("reference"):
            raise serializers.ValidationError({"reference": "Indiquez la référence de l'opération Mobile Money."})
        return data


class ContributionViewSet(DistrictScopedMixin, JournalMixin, mixins.CreateModelMixin, mixins.ListModelMixin,
                          mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Les contributions sont visibles des responsables de leur district (direction et trésorier : toutes).
    Elles ne se modifient pas et ne se suppriment pas : elles s'annulent.
    """

    queryset = Contribution.objects.select_related("membre", "paroisse", "paroisse__district", "enregistre_par")
    serializer_class = ContributionSerializer
    district_field = "paroisse__district"
    roles_ecriture = SAISIE
    filterset_fields = ["type", "mode", "paroisse", "membre", "annulee", "paroisse__district"]
    search_fields = ["numero_recu", "membre__nom", "membre__prenom", "membre__numero", "reference"]
    ordering_fields = ["date", "montant", "cree_le"]

    def get_queryset(self):
        qs = super().get_queryset()
        annee = self.request.query_params.get("annee")
        if annee and annee.isdigit():
            qs = qs.filter(date__year=int(annee))
        mois = self.request.query_params.get("mois")
        if mois and mois.isdigit():
            qs = qs.filter(date__month=int(mois))
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        self._verifier_district(serializer)
        profil = profil_de(self.request.user)
        d = serializer.validated_data
        if d.get("membre") is not None and d["membre"].paroisse.district.organisation_id != profil.organisation_id:
            raise PermissionDenied("Ce membre n'appartient pas à votre organisation.")
        jour = d.get("date") or date.today()
        services.verifier_exercice_ouvert(profil.organisation_id, jour)
        c = serializer.save(organisation=profil.organisation, enregistre_par=self.request.user)
        # Comptabilité : chaque contribution est une recette « Dîmes et offrandes » de son district
        c.transaction = Transaction.objects.create(
            date=c.date, sens=Transaction.Sens.RECETTE, categorie=Transaction.Categorie.DIME, montant=c.montant,
            devise=profil.organisation.devise, canal=MODE_VERS_CANAL.get(c.mode, "ESPECES"), reference_externe=c.reference[:60],
            district=c.paroisse.district, tiers=(_nom_membre(c.membre) or f"Collecte — {c.paroisse.nom}")[:120],
            description=f"{c.get_type_display()} — reçu {c.numero_recu}"[:255],
        )
        c.save(update_fields=["transaction"])
        self._journaliser("CREATION", c, {"montant": str(c.montant), "type": c.type, "membre": c.membre_id})

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        profil = profil_de(request.user)
        if profil.role not in ANNULATION:
            raise PermissionDenied("Seuls le trésorier et l'administrateur annulent une contribution.")
        c = self.get_object()
        if c.annulee:
            raise ValidationError("Cette contribution est déjà annulée.")
        motif = (request.data.get("motif") or "").strip()
        if len(motif) < 5:
            raise ValidationError({"motif": "Indiquez le motif de l'annulation."})
        services.verifier_exercice_ouvert(profil.organisation_id, c.date)
        with transaction.atomic():
            t = c.transaction
            c.transaction = None
            if t is not None:
                t.delete()  # la recette disparaît de la comptabilité ; la contribution reste, annulée
            c.annulee, c.annulee_le, c.annulee_par, c.motif_annulation = True, timezone.now(), request.user, motif[:255]
            c.save()
            self._journaliser("SUPPRESSION", c, {"annulation": motif[:255], "montant": str(c.montant)})
        return Response(self.get_serializer(c).data)

    @action(detail=False)
    def synthese(self, request):
        """Totaux de l'année : par mois, par type, par église locale ; comparaison avec l'année précédente."""
        annee = int(request.query_params.get("annee") or date.today().year)
        base = DistrictScopedMixin.get_queryset(self).filter(annulee=False)  # même périmètre que la liste
        if request.query_params.get("paroisse"):
            base = base.filter(paroisse_id=request.query_params["paroisse"])
        an = base.filter(date__year=annee)
        # À date égale : du 1er janvier au même jour de l'année précédente (29 février → 28)
        j = date.today()
        borne = date(annee - 1, j.month, min(j.day, 28 if j.month == 2 else 31 if j.month in (1, 3, 5, 7, 8, 10, 12) else 30)) \
            if annee == j.year else date(annee - 1, 12, 31)
        precedent = base.filter(date__year=annee - 1, date__lte=borne)
        total = an.aggregate(t=Sum("montant"))["t"] or 0
        total_prec = precedent.aggregate(t=Sum("montant"))["t"] or 0
        mois = {r["m"]: r for r in an.annotate(m=ExtractMonth("date")).order_by().values("m").annotate(t=Sum("montant"), n=Count("id"))}
        mois_prec = {r["m"]: r["t"] for r in base.filter(date__year=annee - 1).annotate(m=ExtractMonth("date")).order_by().values("m").annotate(t=Sum("montant"))}
        types = dict(Contribution.Type.choices)
        return Response({
            "annee": annee, "total": total, "nombre": an.count(),
            "donateurs": an.exclude(membre__isnull=True).order_by().values("membre").distinct().count(),
            "anonyme": an.filter(membre__isnull=True).aggregate(t=Sum("montant"))["t"] or 0,
            "total_meme_periode_annee_precedente": total_prec,
            "evolution_pct": round(100 * (total - total_prec) / total_prec, 1) if total_prec else None,
            "par_mois": [{"mois": m, "total": (mois.get(m) or {}).get("t", 0), "nombre": (mois.get(m) or {}).get("n", 0),
                          "annee_precedente": mois_prec.get(m, 0)} for m in range(1, 13)],
            "par_type": [{"type": r["type"], "libelle": types.get(r["type"], r["type"]), "total": r["t"], "nombre": r["n"]}
                         for r in an.order_by().values("type").annotate(t=Sum("montant"), n=Count("id")).order_by("-t")],
            "par_paroisse": [{"paroisse": r["paroisse"], "nom": r["paroisse__nom"], "total": r["t"], "donateurs": r["d"]}
                             for r in an.order_by().values("paroisse", "paroisse__nom").annotate(t=Sum("montant"), d=Count("membre", distinct=True)).order_by("-t")[:15]],
            "annees": sorted({d.year for d in base.dates("date", "year")} | {date.today().year}, reverse=True),
        })

    @action(detail=False, methods=["post"])
    def attestation(self, request):
        """Émet l'attestation annuelle d'un membre (dans le périmètre du responsable)."""
        membre = MembreEglise.objects.filter(pk=request.data.get("membre")).select_related("paroisse__district").first()
        profil = profil_de(request.user)
        if membre is None or membre.paroisse.district.organisation_id != profil.organisation_id:
            raise ValidationError({"membre": "Membre introuvable."})
        if not profil.voit_tout and membre.paroisse.district_id != profil.district_id:
            raise PermissionDenied("Ce membre n'est pas dans votre district.")
        return Response(emettre_attestation(membre, int(request.data.get("annee") or date.today().year - 1), request),
                        status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------- Attestation annuelle

def _code():
    """12 caractères lisibles, sans 0/O ni 1/I : facile à recopier si le QR code est abîmé."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    brut = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"{brut[:4]}-{brut[4:8]}-{brut[8:]}"


def _qr(url):
    img = qrcode.make(url, box_size=6, border=1)
    tampon = io.BytesIO()
    img.save(tampon, format="PNG")
    return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode()


def releve(membre, annee):
    qs = Contribution.objects.filter(membre=membre, date__year=annee, annulee=False).order_by("date", "id")
    types = dict(Contribution.Type.choices)
    par_type = {r["type"]: r["t"] for r in qs.order_by().values("type").annotate(t=Sum("montant"))}
    return qs, {"par_type": [{"type": k, "libelle": types[k], "total": str(v)} for k, v in par_type.items()],
                "total": qs.aggregate(t=Sum("montant"))["t"] or Decimal(0), "nombre": qs.count()}


def emettre_attestation(membre, annee, request):
    if annee > date.today().year or annee < 2000:
        raise ValidationError({"annee": "Année invalide."})
    qs, r = releve(membre, annee)
    if not r["nombre"]:
        raise ValidationError({"annee": f"Aucune contribution enregistrée en {annee}."})
    definitive = annee < date.today().year
    # Une attestation identique déjà émise est réutilisée (même code) ; sinon une nouvelle version est créée
    att = AttestationAnnuelle.objects.filter(membre=membre, annee=annee, total=r["total"], nombre=r["nombre"],
                                             definitive=definitive).first()
    if att is None:
        att = AttestationAnnuelle.objects.create(membre=membre, annee=annee, total=r["total"], nombre=r["nombre"],
                                                 detail={"par_type": r["par_type"]}, code=_code(), definitive=definitive,
                                                 emise_par=request.user)
        org = membre.paroisse.district.organisation
        JournalAction.objects.create(organisation=org, utilisateur=request.user, action="CREATION", objet_type="Attestation annuelle",
                                     objet_id=str(att.pk), objet_libelle=str(att)[:255], details={"total": str(r["total"]), "annee": annee})
    org = membre.paroisse.district.organisation
    url = request.build_absolute_uri(f"/verifier/{att.code}")
    return {
        "code": att.code, "url_verification": url, "qr": _qr(url), "annee": annee, "definitive": definitive,
        "emise_le": att.emise_le, "total": str(r["total"]), "nombre": r["nombre"], "par_type": r["par_type"],
        "devise": org.devise,
        "organisation": {"nom": org.nom, "sigle": org.sigle, "pays": org.pays},
        "membre": {"nom": f"{membre.prenom} {membre.nom}", "numero": membre.numero, "paroisse": membre.paroisse.nom,
                   "district": membre.paroisse.district.nom, "adresse": membre.adresse},
        "pasteur": membre.paroisse.pasteur,
        "lignes": [{"date": c.date, "recu": c.numero_recu, "type": c.get_type_display(), "mode": c.get_mode_display(),
                    "montant": str(c.montant)} for c in qs],
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def verifier_attestation(request, code):
    """
    Vérification publique d'une attestation (QR code). On montre seulement de quoi comparer avec le papier :
    organisation, nom abrégé, année, total. Jamais le détail des dons ni les coordonnées.
    """
    att = AttestationAnnuelle.objects.filter(code=code.strip().upper()).select_related("membre__paroisse__district__organisation").first()
    if att is None:
        return Response({"valide": False, "message": "Aucune attestation ne porte ce code. Le document n'est pas authentique."},
                        status=status.HTTP_404_NOT_FOUND)
    m, org = att.membre, att.membre.paroisse.district.organisation
    _, r = releve(m, att.annee)
    a_jour = r["total"] == att.total and r["nombre"] == att.nombre
    return Response({
        "valide": True, "a_jour": a_jour, "annee": att.annee, "definitive": att.definitive,
        "total": str(att.total), "devise": org.devise, "nombre": att.nombre, "emise_le": att.emise_le,
        "organisation": org.nom, "paroisse": m.paroisse.nom,
        "membre": f"{m.prenom} {m.nom[:1]}.", "numero_partiel": f"{m.numero[:4]}…{m.numero[-3:]}",
        "message": "Attestation authentique." + ("" if a_jour else " Attention : les contributions de cette année ont changé "
                                                  "depuis son émission (une version plus récente existe)."),
    })


# ---------------------------------------------------------------------- Espace membre

@api_view(["GET"])
@permission_classes([EstMembre])
def mes_contributions(request):
    fiche = getattr(request.user, "fiche_membre", None)
    if fiche is None:
        raise PermissionDenied("Aucune fiche liée à ce compte.")
    annee = int(request.query_params.get("annee") or date.today().year)
    qs, r = releve(fiche, annee)
    annees = sorted({d.year for d in Contribution.objects.filter(membre=fiche, annulee=False).dates("date", "year")} | {date.today().year},
                    reverse=True)
    par_mois = {x["m"]: x["t"] for x in qs.annotate(m=ExtractMonth("date")).order_by().values("m").annotate(t=Sum("montant"))}
    return Response({
        "annee": annee, "annees": annees, "total": str(r["total"]), "nombre": r["nombre"], "par_type": r["par_type"],
        "par_mois": [{"mois": m, "total": str(par_mois.get(m, 0))} for m in range(1, 13)],
        "devise": fiche.paroisse.district.organisation.devise,
        "contributions": [{"id": c.id, "date": c.date, "recu": c.numero_recu, "type": c.get_type_display(),
                           "mode": c.get_mode_display(), "montant": str(c.montant), "paroisse": fiche.paroisse.nom} for c in qs.order_by("-date")],
        "attestations": [{"annee": a.annee, "code": a.code, "emise_le": a.emise_le, "definitive": a.definitive, "total": str(a.total)}
                         for a in AttestationAnnuelle.objects.filter(membre=fiche).order_by("-annee", "-emise_le")[:10]],
    })


@api_view(["POST"])
@permission_classes([EstMembre])
def mon_attestation(request):
    fiche = getattr(request.user, "fiche_membre", None)
    if fiche is None:
        raise PermissionDenied("Aucune fiche liée à ce compte.")
    return Response(emettre_attestation(fiche, int(request.data.get("annee") or date.today().year - 1), request),
                    status=status.HTTP_201_CREATED)
