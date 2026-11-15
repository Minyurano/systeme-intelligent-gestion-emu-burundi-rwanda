"""
Assistant UMURAGE : questions en langage naturel sur le patrimoine et les archives.

Architecture RAG (Retrieval-Augmented Generation) :
1. Récupération : les documents sont découpés en passages et indexés (TF-IDF).
   Les passages les plus proches de la question sont retrouvés.
2. Données structurées : si la question porte sur les biens (combien, valeur,
   district, catégorie, titre foncier...), la base de données est interrogée
   directement — un chiffre exact vaut mieux qu'un texte approximatif.
3. Génération : si un LLM est configuré (LLM_BASE_URL, ex. Ollama en local),
   il rédige la réponse à partir de ces éléments uniquement. Sinon, l'assistant
   répond de façon extractive, en citant ses sources.
"""
import json
import re
import unicodedata
import urllib.request

from django.conf import settings
from django.db.models import Count, Q, Sum
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.models import District, Paroisse
from iot.models import Alerte
from patrimoine.models import Bien, Document, Projet

TAILLE_PASSAGE = 700
MOTS_VIDES = (
    "le la les un une des de du et en a au aux pour par sur dans est sont que qui quoi quel quels quelle "
    "quelles ce ces cette il elle ils elles on nous vous leur leurs son sa ses ne pas plus avec comme "
    "combien comment pourquoi ou d l y t s"
).split()

MOTS_CATEGORIES = {
    "FON": ["terrain", "terrains", "foncier", "parcelle", "parcelles"],
    "IMM": ["batiment", "batiments", "immeuble", "eglise", "eglises", "ecole", "ecoles", "centre", "centres"],
    "INF": ["forage", "forages", "infrastructure", "infrastructures", "usine", "puits"],
    "EQP": ["equipement", "equipements", "materiel", "machine", "machines", "ordinateur"],
    "VEH": ["vehicule", "vehicules", "voiture", "voitures", "moto", "motos"],
    "AGR": ["agricole", "betail", "elevage", "porcherie", "cheptel", "chevres", "tournesol", "manioc"],
}


def normaliser(texte):
    t = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------ Index
_cache = {"cle": None, "index": None}


def _decouper(doc):
    """Découpe un document en passages d'environ TAILLE_PASSAGE caractères, par paragraphes."""
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n|\n", doc.contenu or "") if p.strip()]
    passages, courant = [], ""
    for p in paragraphes:
        if len(courant) + len(p) > TAILLE_PASSAGE and courant:
            passages.append(courant)
            courant = ""
        courant = f"{courant}\n{p}".strip()
    if courant:
        passages.append(courant)
    return [{"doc_id": doc.pk, "titre": doc.titre, "district_id": doc.district_id, "organisation_id": doc.organisation_id, "texte": t}
            for t in passages]


def _index():
    docs = Document.objects.exclude(contenu="")
    cle = (docs.count(), max(docs.values_list("pk", flat=True), default=0), sum(len(c) for c in docs.values_list("contenu", flat=True)))
    if _cache["cle"] != cle:
        passages = [p for d in docs for p in _decouper(d)]
        vect = TfidfVectorizer(strip_accents="unicode", lowercase=True, stop_words=MOTS_VIDES, ngram_range=(1, 2), sublinear_tf=True)
        matrice = vect.fit_transform([f"{p['titre']} {p['texte']}" for p in passages]) if passages else None
        _cache.update(cle=cle, index=(passages, vect, matrice))
    return _cache["index"]


def rechercher(question, profil, k=4):
    passages, vect, matrice = _index()
    if not passages:
        return []
    scores = cosine_similarity(vect.transform([question]), matrice)[0]
    ordre = scores.argsort()[::-1]
    resultats = []
    # On ne garde que les passages proches du meilleur, pour éviter les sources hors sujet
    seuil = max(0.05, 0.35 * float(scores[ordre[0]]))
    for i in ordre:
        if scores[i] < seuil or len(resultats) >= k:
            break
        p = passages[i]
        if profil and p["organisation_id"] != profil.organisation_id:
            continue  # jamais de documents d'une autre organisation
        if profil and not profil.voit_tout and p["district_id"] not in (None, profil.district_id):
            continue
        resultats.append({**p, "score": round(float(scores[i]), 3)})
    return resultats


# ------------------------------------------------------------------ Données
def faits_structures(question, profil):
    """Répond avec des chiffres exacts tirés de la base quand la question s'y prête."""
    q = normaliser(question)
    mots = set(re.findall(r"[a-z]+", q))
    biens = Bien.objects.select_related("district").filter(district__organisation_id=profil.organisation_id)
    if not profil.voit_tout:
        biens = biens.filter(district_id=profil.district_id)

    districts = [d for d in District.objects.filter(organisation_id=profil.organisation_id) if re.search(rf"\b{normaliser(d.nom)}\b", q)]
    paroisses = [p for p in Paroisse.objects.filter(district__organisation_id=profil.organisation_id)
                 if re.search(rf"\b{normaliser(p.nom)}\b", q)] if not districts else []
    cats = [c for c, m in MOTS_CATEGORIES.items() if mots & set(m)]
    faits = []
    filtre = Q()
    if districts:
        filtre &= Q(district__in=districts)
    elif paroisses:
        filtre &= Q(paroisse__in=paroisses)
    if cats:
        filtre &= Q(categorie__in=cats)
    portee = biens.filter(filtre)
    defaut = "tous districts" if profil.voit_tout else f"district de {profil.district.nom}"
    libelle = " / ".join(d.nom for d in districts) or " / ".join(p.nom for p in paroisses) or defaut
    libelle_cat = ", ".join(Bien.Categorie(c).label for c in cats) or "tous types"

    if mots & {"titre", "titres", "juridique", "propriete", "sans"}:
        sans = portee.filter(statut_juridique__in=["SANS_TITRE", "EN_COURS"])
        liste = ", ".join(f"{b.nom} ({b.get_statut_juridique_display().lower()})" for b in sans[:10])
        faits.append(f"Biens sans titre définitif ({libelle}) : {sans.count()}. {liste}")
    if mots & {"valeur", "vaut", "valent", "patrimoine", "total", "estimation", "estime"}:
        tot = sum(float(b.valeur_courante or 0) for b in portee)
        montant = f"{tot:,.0f}".replace(",", " ")
        faits.append(f"Valeur estimée ({libelle_cat}, {libelle}) : {montant} {profil.organisation.devise} pour {portee.count()} biens.")
    if mots & {"finance", "financement", "financeur", "financeurs", "bailleur", "bailleurs", "partenaire", "partenaires"}:
        avec = portee.exclude(financeur="")[:10]
        faits.append("Financeurs : " + ("; ".join(f"{b.nom} — {b.financeur}" for b in avec) or "aucun financeur enregistré"))
    if mots & {"combien", "nombre", "liste", "lister", "inventaire"} or (mots & {"quels", "quelles"} and cats and not faits):
        repartition = portee.values("categorie").annotate(n=Count("id")).order_by("-n")
        detail = ", ".join(f"{Bien.Categorie(r['categorie']).label} : {r['n']}" for r in repartition)
        faits.append(f"Nombre de biens ({libelle_cat}, {libelle}) : {portee.count()}. Répartition — {detail}.")
        if 0 < portee.count() <= 12:
            faits.append("Liste : " + "; ".join(f"{b.code} {b.nom} [{b.get_etat_display()}]" for b in portee))
    if mots & {"risque", "urgent", "urgence", "entretien", "maintenance", "panne", "reparer"}:
        risques = portee.filter(score_risque__gte=50).order_by("-score_risque")[:8]
        faits.append("Biens à risque élevé : " + ("; ".join(f"{b.nom} (score {b.score_risque:.0f}/100)" for b in risques) or "aucun"))
    if mots & {"alerte", "alertes", "capteur", "capteurs"}:
        al = Alerte.objects.filter(resolue=False, bien__in=portee)
        faits.append(f"Alertes non résolues : {al.count()}. " + "; ".join(a.message for a in al[:5]))
    if mots & {"projet", "projets", "chantier", "chantiers", "construction"}:
        pr = Projet.objects.filter(district__organisation_id=profil.organisation_id).filter(Q(district__in=districts) if districts else Q())
        if not profil.voit_tout:
            pr = pr.filter(district_id=profil.district_id)
        faits.append("Projets : " + "; ".join(f"{p.nom} — {p.get_statut_display()}, {p.avancement} %" for p in pr[:10]))
    return faits


# ------------------------------------------------------------------ Génération
def _appeler_llm(question, faits, passages):
    cfg = settings.UMURAGE
    contexte = "\n".join(f"- {f}" for f in faits)
    contexte += "\n\n" + "\n\n".join(f"[Source {i + 1} : {p['titre']}]\n{p['texte']}" for i, p in enumerate(passages))
    corps = {
        "model": cfg["LLM_MODEL"],
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": (
                "Tu es l'assistant UMURAGE de l'Église Méthodiste Unie du Burundi. Réponds en français, "
                "clairement et brièvement, UNIQUEMENT à partir du contexte fourni. Cite les sources sous la forme "
                "[Source n]. Si le contexte ne contient pas la réponse, dis-le honnêtement."
            )},
            {"role": "user", "content": f"Contexte :\n{contexte}\n\nQuestion : {question}"},
        ],
    }
    req = urllib.request.Request(
        cfg["LLM_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['LLM_API_KEY']}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def _meilleure_phrase(texte, question):
    """Choisit, dans un passage, les phrases qui partagent le plus de mots avec la question."""
    mots_q = set(re.findall(r"[a-z]{4,}", normaliser(question))) - set(MOTS_VIDES)
    phrases = [p for p in re.split(r"(?<=[.!?])\s+|\n+", texte) if len(p) > 25]
    if not phrases:
        return texte[:300]
    def note(ph):
        return len(mots_q & set(re.findall(r"[a-z]{4,}", normaliser(ph))))
    notees = sorted(phrases, key=lambda ph: -note(ph))
    retenues = [notees[0]] + [ph for ph in notees[1:2] if note(ph) >= max(2, note(notees[0]))]
    return " ".join(retenues)


def repondre(question, profil):
    faits = faits_structures(question, profil)
    passages = rechercher(question, profil)
    sources = [{"titre": p["titre"], "document_id": p["doc_id"], "extrait": p["texte"][:400], "score": p["score"]} for p in passages]

    erreur = None
    if settings.UMURAGE["LLM_BASE_URL"] and (faits or passages):
        try:
            return {"reponse": _appeler_llm(question, faits, passages), "faits": faits, "sources": sources, "mode": "llm"}
        except Exception as e:  # le LLM est optionnel : on bascule en mode extractif
            erreur = str(e)

    morceaux = []
    if faits:
        morceaux.append("D'après la base de données :\n" + "\n".join(f"• {f}" for f in faits))
    if passages:
        morceaux.append("Dans les archives :\n" + "\n".join(
            f"• {_meilleure_phrase(p['texte'], question)} [Source {i + 1}]" for i, p in enumerate(passages[:3])
        ))
    if not morceaux:
        morceaux.append(
            "Je n'ai trouvé aucune information correspondante dans les données ni dans les archives. "
            "Essayez de reformuler, ou ajoutez le document concerné dans la section Documents."
        )
    rep = {"reponse": "\n\n".join(morceaux), "faits": faits, "sources": sources, "mode": "extractif"}
    if erreur:
        rep["avertissement"] = f"LLM indisponible ({erreur[:80]}), réponse extractive."
    return rep
