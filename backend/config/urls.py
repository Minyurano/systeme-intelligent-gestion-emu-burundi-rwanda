from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.throttling import ScopedRateThrottle

from config.views import application
from core.fichiers import fichier_protege

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core import deuxfacteurs, jetons, mdp_oublie, views as core
from core.deuxfacteurs import Connexion
from metier import acces, contributions, views as metier
from finances.views import TransactionViewSet
from ia import views as ia
from iot import views as iot
from patrimoine import views as pat
from patrimoine import outils
from patrimoine.declarations import DeclarationViewSet, webhook_whatsapp


routeur = DefaultRouter()
routeur.register("districts", core.DistrictViewSet)
routeur.register("paroisses", core.ParoisseViewSet)
routeur.register("journal", core.JournalViewSet)
routeur.register("biens", pat.BienViewSet)
routeur.register("mouvements", pat.MouvementViewSet)
routeur.register("documents", pat.DocumentViewSet)
routeur.register("projets", pat.ProjetViewSet)
routeur.register("transactions", TransactionViewSet)
routeur.register("capteurs", iot.CapteurViewSet)
routeur.register("alertes", iot.AlerteViewSet)
routeur.register("declarations", DeclarationViewSet)
routeur.register("membres", core.MembreViewSet, basename="membre")
# Modules métier
routeur.register("demandes", metier.DemandeViewSet)
routeur.register("echeances", metier.EcheanceViewSet)
routeur.register("baux", metier.BailViewSet)
routeur.register("loyers", metier.LoyerViewSet)
routeur.register("fournisseurs", metier.FournisseurViewSet)
routeur.register("plans-maintenance", metier.PlanMaintenanceViewSet)
routeur.register("ordres-travail", metier.OrdreTravailViewSet)
routeur.register("budgets", metier.BudgetViewSet)
routeur.register("clotures", metier.ClotureViewSet)
routeur.register("campagnes", metier.CampagneViewSet)
routeur.register("registre", metier.MembreEgliseViewSet, basename="registre")
# Accès des membres de l'Église (donnés par les administrateurs)
routeur.register("acces-membres", acces.AccesMembresViewSet, basename="acces-membre")
routeur.register("demandes-acces", acces.DemandeAccesViewSet, basename="demande-acces")
# Dîmes et offrandes
routeur.register("contributions", contributions.ContributionViewSet)

admin.site.site_header = "UMURAGE — Administration"
admin.site.site_title = "UMURAGE"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/token/", Connexion.as_view()),
    path("api/auth/refresh/", jetons.rafraichir),
    path("api/auth/deconnexion/", jetons.deconnexion),
    path("api/auth/mot-de-passe-oublie/", mdp_oublie.demander_code),
    path("api/auth/reinitialiser/", mdp_oublie.reinitialiser),
    path("api/moi/", core.moi),
    path("api/moi/mot-de-passe/", core.changer_mot_de_passe),
    path("api/acces/organisations/", acces.organisations_acces),
    path("api/acces/demande/", acces.demander_acces),
    path("api/espace-membre/", acces.espace_membre),
    path("api/espace-membre/coordonnees/", acces.mes_coordonnees),
    path("api/espace-membre/signalements/", acces.mes_signalements),
    path("api/espace-membre/contributions/", contributions.mes_contributions),
    path("api/espace-membre/attestation/", contributions.mon_attestation),
    path("api/attestations/verifier/<str:code>/", contributions.verifier_attestation),
    path("api/organisation/", core.mon_organisation),
    path("api/inscription/", core.inscription),
    path("api/organisations-publiques/", core.organisations_publiques),
    path("api/whatsapp/webhook/", webhook_whatsapp),
    path("api/import/biens/", outils.importer_biens),
    path("api/import/modele/", outils.modele_import),
    path("api/export/iati/", outils.export_iati),
    path("api/export/transactions/", outils.export_transactions),
    path("api/qualite/", outils.qualite),
    path("api/tableau-de-bord/", pat.tableau_de_bord),
    path("api/carte/", pat.carte),
    path("api/recherche/", pat.recherche),
    path("api/compteurs/", pat.compteurs),
    path("api/public/", pat.portail_public),
    path("api/iot/ingestion/", iot.ingestion),
    path("api/ia/assistant/", ia.poser_question),
    path("api/ia/analyses/", ia.relancer_analyses),
    path("api/ia/modeles/", ia.historique_modeles),
    path("api/compta/registre/", metier.registre_immobilisations),
    path("api/compta/rapprochement/", metier.rapprochement),
    path("api/documents-manquants/", metier.documents_manquants),
    path("api/metier/compteurs/", metier.compteurs_metier),
    path("api/comparaison/", metier.comparer_eglises),
    path("api/comparaison/analyse/", metier.analyse_comparaison),
    path("api/statistiques-eglise/", metier.statistiques_eglise),
    path("api/taches/executer/", metier.executer_taches),
    path("api/2fa/activer/", deuxfacteurs.activer),
    path("api/2fa/confirmer/", deuxfacteurs.confirmer),
    path("api/2fa/desactiver/", deuxfacteurs.desactiver),
    path("api/sante/", core.sante),
    path("api/diagnostic/adresse-ip/", core.diagnostic_adresse_ip),
    path("api/", include(routeur.urls)),
    # Fichiers téléversés : jamais publics (lien signé et temporaire, ou en-tête Bearer avec contrôle du périmètre)
    re_path(r"^media/(?P<chemin>.+)$", fichier_protege),
]

# Toutes les autres adresses affichent l'interface (doit rester en dernier)
urlpatterns += [re_path(r"^(?!api/|admin/|media/|static/).*$", application)]
