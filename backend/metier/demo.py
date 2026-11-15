"""Données de démonstration des modules métier (fictives), pour que chaque écran soit parlant dès l'installation."""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User

from core.models import District, Organisation, Paroisse
from finances.models import Transaction
from patrimoine.models import Bien, Document

from . import services, taches
from .models import (
    Avis, Bail, Budget, Campagne, Constat, Demande, Echeance, Fournisseur, Loyer, MembreEglise, OrdreTravail, PlanMaintenance,
    ajouter_mois,
)


def charger(org: Organisation):
    random.seed(7)
    j = date.today()
    d = {x.code: x for x in District.objects.filter(organisation=org)}
    u = {x.username: x for x in User.objects.filter(username__in=["eveque", "tresorier", "surintendant.gitega", "agent.burunga", "admin"])}
    biens = Bien.objects.filter(district__organisation=org)
    un = lambda **f: biens.filter(**f).order_by("code").first()

    # ---- Fournisseurs et maintenance
    f_forage = Fournisseur.objects.create(organisation=org, nom="Hydro Services Burundi", specialite="Forages et pompes", telephone="+25779111111")
    f_bat = Fournisseur.objects.create(organisation=org, nom="Bâtir Gitega SARL", specialite="Toiture, maçonnerie", telephone="+25779222222")
    Fournisseur.objects.create(organisation=org, nom="Garage Mutoyi", specialite="Mécanique automobile", telephone="+25779333333")
    for b in biens.filter(sous_type__icontains="forage")[:4]:
        PlanMaintenance.objects.create(bien=b, libelle="Entretien de la pompe et analyse de l'eau", periodicite_mois=6,
                                       prochaine_date=j + timedelta(days=random.randint(-5, 40)), fournisseur=f_forage, cout_estime=Decimal(450_000))
    ecole = un(sous_type__icontains="école", district__code="GIT") or un(categorie="IMM")
    OrdreTravail.objects.create(bien=ecole, titre="Réfection de la toiture (fuites saison des pluies)", type="REPARATION", priorite="HAUTE",
                                statut="EN_COURS", fournisseur=f_bat, cout_estime=Decimal(3_800_000), date_prevue=j + timedelta(days=5),
                                cree_par=u.get("surintendant.gitega"))
    termine = OrdreTravail.objects.create(bien=ecole, titre="Remplacement des vitres de la classe 3", type="REPARATION", statut="PLANIFIE",
                                          fournisseur=f_bat, cout_estime=Decimal(600_000), cree_par=u.get("surintendant.gitega"))
    termine.statut, termine.termine_le, termine.cout_reel, termine.rapport = "TERMINE", j - timedelta(days=12), Decimal(560_000), "12 vitres remplacées."
    termine.save()

    # ---- Baux et loyers
    boutique = un(district__code="BJM", categorie="IMM") or un(categorie="IMM")
    salle = un(district__code="GIT", categorie="IMM") or boutique
    terrain = un(district__code="BRG", categorie="FON") or un(categorie="FON")
    baux = [
        Bail(bien=boutique, locataire="Boutique Amahoro (Mme Niyonzima)", telephone="+25779444444", objet="Boutique n°2 en façade",
             loyer_mensuel=Decimal(350_000), caution=Decimal(700_000), date_debut=ajouter_mois(j.replace(day=1), -10), jour_echeance=5),
        Bail(bien=salle, locataire="Coopérative Twiyungunganye", telephone="+25779555555", objet="Salle de réunion (2 jours par semaine)",
             loyer_mensuel=Decimal(180_000), date_debut=ajouter_mois(j.replace(day=1), -6), date_fin=j + timedelta(days=45), jour_echeance=10),
        Bail(bien=terrain, locataire="M. Ndayishimiye (culture du manioc)", objet="Parcelle agricole de 2 ha",
             loyer_mensuel=Decimal(60_000), date_debut=ajouter_mois(j.replace(day=1), -4), jour_echeance=1),
    ]
    for b in baux:
        b.save()
        b.generer_loyers(j)
    for i, l in enumerate(Loyer.objects.filter(bail__in=baux).order_by("periode")):
        if l.echeance < j - timedelta(days=20) and not (l.bail == baux[2] and i % 3 == 0):
            t = Transaction.objects.create(date=l.echeance + timedelta(days=random.randint(0, 6)), sens="RECETTE", categorie="LOYER",
                                           montant=l.montant_du, devise=org.devise, district=l.bail.bien.district, bien=l.bail.bien,
                                           tiers=l.bail.locataire[:120], canal="MOBILE", reference_externe=f"LUMI{100000 + l.pk}",
                                           description=f"Loyer {l.periode:%m/%Y}")
            l.montant_paye, l.paye_le, l.transaction = l.montant_du, t.date, t
            l.save()

    # ---- Échéancier
    vehicule = un(categorie="VEH")
    for lib, typ, delai, per, bien, dist in [
        ("Assurance multirisque des bâtiments de la conférence", "ASSURANCE", 21, 12, None, None),
        ("Impôt foncier — parcelles de Bujumbura", "IMPOT", 55, 12, None, d.get("BJM")),
        ("Contrôle technique du véhicule", "CONTROLE", 6, 12, vehicule, vehicule.district if vehicule else None),
        ("Renouvellement du titre de la parcelle de Muyange", "TITRE", -4, 0, terrain, terrain.district if terrain else None),
    ]:
        Echeance.objects.create(organisation=org, district=dist, bien=bien, type=typ, libelle=lib, date=j + timedelta(days=delai),
                                periodicite_mois=per, responsable=u.get("tresorier") if typ in ("ASSURANCE", "IMPOT") else None)
    if vehicule:
        Document.objects.create(organisation=org, bien=vehicule, district=vehicule.district, titre="Attestation d'assurance du véhicule",
                                type="ASSURANCE", date=j - timedelta(days=330), date_expiration=j + timedelta(days=35),
                                contenu="Attestation d'assurance (démonstration).")

    # ---- Budget de l'année
    # Budget voté : réalisé annualisé de l'année, ajusté poste par poste (quelques dépassements pour la démonstration)
    from django.db.models import Sum
    fraction = max(j.timetuple().tm_yday / 365, 0.25)
    ajustement = {"CONSTRUCTION": 0.85, "MAINTENANCE": 1.25, "SALAIRE": 1.05, "FONCTIONNEMENT": 0.95, "DIME": 1.1, "SUBVENTION": 1.3, "LOYER": 1.2}
    reel = Transaction.objects.filter(district__organisation=org, date__year=j.year).values("sens", "categorie").annotate(t=Sum("montant_bif"))
    for l in reel:
        if l["categorie"] in ajustement:
            montant = Decimal(round(float(l["t"]) / fraction * ajustement[l["categorie"]], -6))
            Budget.objects.create(organisation=org, annee=j.year, sens=l["sens"], categorie=l["categorie"], montant=montant)

    # ---- Demandes à différents stades du circuit
    git = d.get("GIT")
    sur, ev, tr, ag = u.get("surintendant.gitega"), u.get("eveque"), u.get("tresorier"), u.get("agent.burunga")
    from core.models import Profil
    p = {k: Profil.objects.get(user=v) for k, v in u.items() if v}
    terrain_git = un(district__code="GIT", categorie="FON")
    d1 = services.creer_demande(Demande(organisation=org, district=git, type="CESSION", bien=terrain_git, montant=Decimal(45_000_000),
                                        titre=f"Vente de la parcelle {terrain_git.code if terrain_git else ''} (non exploitée)",
                                        description="Parcelle enclavée, non exploitée depuis 2015. Le produit financera l'extension de l'école.",
                                        demandeur=ag or sur))
    d2 = services.creer_demande(Demande(organisation=org, district=git, type="TRAVAUX", bien=ecole, montant=Decimal(12_500_000),
                                        titre="Construction de latrines pour l'école", description="Devis Bâtir Gitega joint.", demandeur=ag or sur))
    if "surintendant.gitega" in p:
        services.decider(d2, p["surintendant.gitega"], Avis.Decision.APPROUVE, "Besoin confirmé sur place.")
        services.decider(d1, p["surintendant.gitega"], Avis.Decision.APPROUVE, "Avis favorable du conseil de district du 12 septembre.")
    brg = d.get("BRG")
    services.creer_demande(Demande(organisation=org, district=brg, type="DEPENSE", montant=Decimal(850_000), categorie_depense="ACHAT",
                                   titre="Achat d'un groupe électrogène pour la paroisse", demandeur=ag))

    # ---- Campagne d'inventaire en cours à Gitega
    c = Campagne.objects.create(organisation=org, district=git, nom=f"Inventaire annuel {j.year} — Gitega", date_debut=j - timedelta(days=3),
                                cree_par=sur)
    for i, b in enumerate(biens.filter(district=git).order_by("code")[:5]):
        Constat.objects.create(campagne=c, bien=b, agent=sur, trouve=i != 3,
                               etat_constate="MAUVAIS" if i == 1 else "", commentaire="Introuvable à l'adresse indiquée" if i == 3 else "")

    charger_membres(org, sur or ag, nombre=160)
    charger_acces_membres(org)
    charger_contributions(org)
    taches.executer_tout(j)


NOMS = ["NDAYISHIMIYE", "NIYONZIMA", "HAKIZIMANA", "NSHIMIRIMANA", "IRAKOZE", "NIYONKURU", "BIZIMANA", "NDIKUMANA", "MANIRAKIZA",
        "NTAKIRUTIMANA", "HABONIMANA", "NIYOMWUNGERE", "KWIZERA", "NZEYIMANA", "BARANYIKWA", "MINANI"]
PRENOMS_H = ["Jean-Claude", "Emmanuel", "Pacifique", "Fabrice", "Innocent", "Eric", "Prosper", "Désiré", "Gédéon", "Samuel"]
PRENOMS_F = ["Esther", "Grâce", "Divine", "Josiane", "Aline", "Gloria", "Claudine", "Joëlla", "Ange", "Sandrine"]
MINISTERES = ["Chorale", "Femmes méthodistes", "Jeunesse", "École du dimanche", "Hommes méthodistes", "Intercession", ""]


def charger_membres(org, auteur, nombre=48, graine=11):
    """Fiches fictives dans les églises locales, pour que le registre et les statistiques soient parlants dès l'installation."""
    rnd = random.Random(graine)
    j = date.today()
    paroisses = list(Paroisse.objects.filter(district__organisation=org).order_by("nom"))
    if not paroisses:
        return
    for i in range(nombre):
        femme = rnd.random() < 0.55
        statut = rnd.choices(["CONFESSANT", "BAPTISE", "CATECHUMENE", "SYMPATHISANT", "TRANSFERE", "DECEDE"], [40, 28, 16, 10, 4, 2])[0]
        naissance = j - timedelta(days=rnd.randint(14, 75) * 365 + rnd.randint(0, 364))
        bapteme = naissance + timedelta(days=rnd.randint(12, 30) * 365) if statut in ("BAPTISE", "CONFESSANT") else None
        if bapteme and (bapteme > j or rnd.random() < 0.3):
            bapteme = j - timedelta(days=rnd.randint(10, 640))  # baptêmes récents : cette année et l'an dernier
        # Adhésions : une bonne part sur les deux dernières années, pour une courbe de croissance réaliste
        adhesion = j - timedelta(days=rnd.randint(0, 720) if rnd.random() < 0.6 else rnd.randint(721, 3650))
        MembreEglise.objects.create(
            paroisse=paroisses[i % len(paroisses)] if i % 3 else rnd.choice(paroisses[:6]),
            nom=rnd.choice(NOMS), prenom=rnd.choice(PRENOMS_F if femme else PRENOMS_H), sexe="F" if femme else "H",
            date_naissance=naissance, lieu_naissance=rnd.choice(["Gitega", "Bujumbura", "Ngozi", "Cankuzo", "Rumonge", "Muyinga"]),
            telephone=f"+2576{rnd.randint(1000000, 9999999)}", adresse=f"Colline {rnd.choice(['Mweya', 'Kayero', 'Rohero', 'Murore', 'Nyabugogo', 'Muyange'])}",
            situation_familiale=rnd.choice(["CELIBATAIRE", "MARIE", "MARIE", "VEUF"]),
            profession=rnd.choice(["Enseignant(e)", "Agriculteur", "Commerçant(e)", "Infirmier(ère)", "Étudiant(e)", "Couturière", "Chauffeur"]),
            statut=statut, date_adhesion=adhesion, date_bapteme=bapteme,
            date_confirmation=bapteme + timedelta(days=rnd.randint(60, 900)) if statut == "CONFESSANT" and bapteme and bapteme < j - timedelta(days=900) else None,
            ministere=rnd.choice(MINISTERES), enregistre_par=auteur,
            notes="Fiche de démonstration (personne fictive)."
        )


def charger_acces_membres(org):
    """
    Démonstration de l'espace membre : une fidèle de Kayero (Burunga) avec un accès,
    et deux demandes d'accès en attente. Identifiant « membre.kayero », mot de passe de démonstration.
    """
    from core.models import Profil
    from .models import DemandeAcces

    if User.objects.filter(username="membre.kayero").exists():
        return
    kayero = Paroisse.objects.filter(district__organisation=org, nom="Kayero").first()
    if kayero is None:
        return
    j = date.today()
    fiche = MembreEglise.objects.create(
        paroisse=kayero, nom="NDAYISHIMIYE", prenom="Esther", sexe="F", date_naissance=date(1991, 4, 17), lieu_naissance="Kayero",
        telephone="+25779000010", adresse="Colline Kayero", situation_familiale="MARIE", profession="Enseignante",
        statut="CONFESSANT", date_adhesion=date(2009, 3, 1), date_bapteme=date(2005, 12, 25), date_confirmation=date(2009, 3, 1),
        ministere="Chorale", notes="Fiche de démonstration (personne fictive).",
    )
    u = User.objects.create_user("membre.kayero", password="umurage2026", first_name="Esther", last_name="NDAYISHIMIYE")
    fiche.compte = u
    fiche.save(update_fields=["compte"])
    Profil.objects.create(user=u, organisation=org, role=Profil.Role.MEMBRE, district=kayero.district, telephone="+25779000010")

    # Une demande vérifiée (numéro de membre et téléphone concordent) et une à rapprocher à la main
    autre = (MembreEglise.objects.filter(paroisse__district__organisation=org, statut="CONFESSANT", compte__isnull=True)
             .exclude(telephone="").order_by("numero").first())
    if autre:
        DemandeAcces.objects.create(organisation=org, membre=autre, numero_saisi=autre.numero, nom_saisi=f"{autre.prenom} {autre.nom}",
                                    telephone=autre.telephone, verifiee=True, message="Je voudrais voir ma fiche et suivre les projets de ma paroisse.")
    DemandeAcces.objects.create(organisation=org, nom_saisi="Pacifique HAKIZIMANA", telephone="+25768123456",
                                message="J'ai perdu ma carte de membre, je suis à la chorale de Kayero.")


def charger_contributions(org, graine=7):
    """
    Dîmes et offrandes fictives sur l'année passée et l'année en cours : dîmes mensuelles d'une partie des membres
    (dont Esther, compte membre.kayero), offrandes ponctuelles et quêtes anonymes du dimanche.
    Les reçus de démonstration ne créent pas de transactions comptables (les finances de démonstration
    contiennent déjà les recettes agrégées).
    """
    from core.models import Verrou
    from .models import Contribution

    if Contribution.objects.filter(organisation=org).exists():
        return
    rnd = random.Random(graine)
    j = date.today()
    auteur = User.objects.filter(username="tresorier").first()
    membres = list(MembreEglise.objects.filter(paroisse__district__organisation=org, statut__in=["CONFESSANT", "BAPTISE"])
                   .select_related("paroisse").order_by("numero"))
    esther = MembreEglise.objects.filter(compte__username="membre.kayero").first()
    donateurs = ([esther] if esther else []) + rnd.sample(membres, min(70, len(membres)))
    lignes = []

    def ajouter(m, paroisse, type_, montant, jour, mode="ESPECES", ref=""):
        if jour <= j:
            lignes.append(Contribution(organisation=org, paroisse=paroisse, membre=m, type=type_, montant=Decimal(montant),
                                       date=jour, mode=mode, reference=ref, enregistre_par=auteur, note="Démonstration"))

    for m in donateurs:
        if m is None:
            continue
        base = rnd.choice([5_000, 10_000, 15_000, 20_000, 30_000, 50_000]) if m != esther else 25_000
        regulier = m == esther or rnd.random() < 0.6
        for annee in (j.year - 1, j.year):
            for mois in range(1, 13):
                if not regulier and rnd.random() < 0.45:
                    continue
                mode = rnd.choices(["ESPECES", "MOBILE", "BANQUE"], [60, 32, 8])[0]
                ref = f"LUM{rnd.randint(10**7, 10**8 - 1)}" if mode == "MOBILE" else ""
                ajouter(m, m.paroisse, "DIME", base, date(annee, mois, rnd.randint(1, 28)), mode, ref)
            if rnd.random() < 0.5 or m == esther:
                ajouter(m, m.paroisse, "ACTION_GRACES", base * rnd.choice([1, 2, 3]), date(annee, 12, rnd.randint(1, 24)))
            if rnd.random() < 0.35 or m == esther:
                ajouter(m, m.paroisse, "CONSTRUCTION", rnd.choice([20_000, 50_000, 100_000]), date(annee, rnd.randint(3, 9), rnd.randint(1, 28)))
    # Quêtes anonymes du dimanche dans quelques églises
    for p in Paroisse.objects.filter(district__organisation=org).order_by("nom")[:8]:
        d = date(j.year - 1, 1, 7)
        while d <= j:
            if rnd.random() < 0.8:
                ajouter(None, p, "OFFRANDE", rnd.randint(40, 260) * 1_000, d)
            d += timedelta(days=7)

    lignes.sort(key=lambda c: (c.date, c.paroisse_id))
    sigle = "".join(c for c in org.sigle.upper() if c.isalnum())[:12] or "R"
    rangs = {}
    for c in lignes:
        rangs[c.date.year] = rangs.get(c.date.year, 0) + 1
        c.numero_recu = f"{sigle}-{c.date.year}-{rangs[c.date.year]:06d}"
    Contribution.objects.bulk_create(lignes, batch_size=500)
    for annee, n in rangs.items():  # les prochains reçus continuent la numérotation
        Verrou.objects.update_or_create(nom=f"recu:{org.id}:{annee}", defaults={"valeur": n})
