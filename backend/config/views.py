from django.conf import settings
from django.http import HttpResponse


def application(request, chemin=""):
    """
    Renvoie l'interface React pour toutes les adresses qui ne sont pas l'API :
    c'est le routeur de l'interface qui affiche la bonne page.
    """
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "<h1>UMURAGE</h1><p>L'interface n'est pas encore construite. Dans le dossier <code>frontend</code>, "
            "lancez <code>npm install</code> puis <code>npm run build</code>, ou utilisez <code>npm run dev</code> "
            "et ouvrez http://localhost:5173.</p><p>L'API fonctionne : <a href='/api/'>/api/</a></p>",
            status=503,
        )
    rep = HttpResponse(index.read_bytes(), content_type="text/html; charset=utf-8")
    rep["Cache-Control"] = "no-cache"
    return rep
