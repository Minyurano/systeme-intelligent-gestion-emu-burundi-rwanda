"""
Détection d'anomalies financières.

Combine deux approches complémentaires :
1. Isolation Forest (apprentissage non supervisé) : repère les transactions qui
   « ne ressemblent pas » aux autres.
2. Règles métier lisibles par le trésorier : montants hors norme, doublons,
   grosses dépenses en espèces, opérations le dimanche.
Chaque anomalie est accompagnée de ses motifs, pour pouvoir être vérifiée.
"""
import math
from collections import defaultdict
from statistics import median

import numpy as np
from sklearn.ensemble import IsolationForest

from finances.models import Transaction

from .models import EntrainementModele
from patrimoine.cache_donnees import donnees_modifiees

CATS = [c for c, _ in Transaction.Categorie.choices]
CANAUX = [c for c, _ in Transaction.Canal.choices]
SEUIL_ESPECES = 2_000_000  # BIF
SEUIL_DIMANCHE = 1_000_000  # BIF


def _groupe(t):
    """Groupe de comparaison : le projet pour une tranche de projet, sinon le district et la catégorie."""
    return ("P", t.projet_id, t.sens) if t.projet_id else ("D", t.district_id, t.sens, t.categorie)


def _caracteristiques(t, medianes):
    m = float(t.montant_bif)
    med = medianes.get(_groupe(t), m) or 1
    return [
        math.log1p(m),
        math.log((m + 1) / (med + 1)),
        1 if t.sens == "DEPENSE" else 0,
        CATS.index(t.categorie),
        CANAUX.index(t.canal),
        t.date.weekday(),
        t.date.day,
    ]


def analyser(qs=None):
    qs = list((qs if qs is not None else Transaction.objects.all()).select_related("projet"))
    if len(qs) < 30:
        return {"analysees": len(qs), "anomalies": 0, "message": "Pas assez de transactions (minimum 30)."}

    par_groupe = defaultdict(list)
    for t in qs:
        par_groupe[_groupe(t)].append(float(t.montant_bif))
    medianes = {k: median(v) for k, v in par_groupe.items()}

    # Dépenses cumulées par projet, pour détecter un dépassement de budget
    cumul, depasse = defaultdict(float), set()
    for t in sorted(qs, key=lambda x: (x.date, x.pk)):
        if t.projet_id and t.sens == "DEPENSE":
            cumul[t.projet_id] += float(t.montant_bif)
            if cumul[t.projet_id] > float(t.projet.budget) * 1.05:
                depasse.add(t.pk)

    X = np.array([_caracteristiques(t, medianes) for t in qs])
    foret = IsolationForest(n_estimators=200, contamination=0.04, random_state=42)
    foret.fit(X)
    scores = -foret.score_samples(X)  # plus c'est élevé, plus c'est anormal
    preds = foret.predict(X)
    smin, smax = scores.min(), scores.max()

    # Détection des doublons : même tiers, même montant, à moins de 3 jours d'écart
    vus = defaultdict(list)
    for t in qs:
        vus[(t.tiers.strip().lower(), t.montant_bif, t.sens)].append(t)

    nb = 0
    for t, s, p in zip(qs, scores, preds):
        motifs = []
        m = float(t.montant_bif)
        med = medianes[_groupe(t)]
        if med and m > 4 * med and len(par_groupe[_groupe(t)]) >= 4:
            ref = f"le projet « {t.projet.nom} »" if t.projet_id else f"« {t.get_categorie_display()} » dans ce district"
            motifs.append(f"Montant {m / med:.1f}× supérieur à l'habitude pour {ref}")
        if t.pk in depasse:
            motifs.append("Les dépenses cumulées dépassent le budget du projet")
        if t.sens == "DEPENSE" and t.canal == "ESPECES" and m >= SEUIL_ESPECES:
            motifs.append("Dépense importante payée en espèces")
        if t.sens == "DEPENSE" and t.date.weekday() == 6 and m >= SEUIL_DIMANCHE:
            motifs.append("Dépense importante enregistrée un dimanche")
        if t.tiers:
            for autre in vus[(t.tiers.strip().lower(), t.montant_bif, t.sens)]:
                if autre.pk != t.pk and abs((autre.date - t.date).days) <= 3:
                    motifs.append(f"Doublon possible avec l'opération du {autre.date:%d/%m/%Y}")
                    break
        if p == -1:
            motifs.append("Profil inhabituel détecté par le modèle (Isolation Forest)")

        score = round(float((s - smin) / (smax - smin + 1e-9)), 3)
        # Anomalie si le modèle ET au moins une règle concordent, ou si deux règles concordent
        regles = [mo for mo in motifs if "Isolation" not in mo]
        anomalie = (p == -1 and len(regles) >= 1) or len(regles) >= 2 or any("Doublon" in mo for mo in regles)
        t.score_anomalie = score
        t.est_anomalie = anomalie
        t.motifs_anomalie = motifs if anomalie else []
        nb += anomalie
    Transaction.objects.bulk_update(qs, ["score_anomalie", "est_anomalie", "motifs_anomalie"])
    donnees_modifiees()  # bulk_update ne déclenche pas de signal : on invalide le cache des tableaux de bord
    EntrainementModele.objects.create(
        modele="anomalies", nb_exemples=len(qs), metriques={"anomalies_detectees": nb, "taux": round(nb / len(qs), 3)}
    )
    return {"analysees": len(qs), "anomalies": nb}
