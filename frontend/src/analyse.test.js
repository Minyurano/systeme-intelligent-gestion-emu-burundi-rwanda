import { describe, expect, it } from "vitest";
import { couleurProfil, donneesEcarts, etiquettesVisibles, ficheEglise, niveauEcart, signe } from "./analyse";

const d = {
  disponible: true,
  carte: { points: [{ id: 1, nom: "Ngozi", profil: 0, indice: 93 }, { id: 2, nom: "Musenyi", profil: 1, indice: 22 }] },
  profils: [{ id: 0, nom: "Églises bien gérées", effectif: 13 }, { id: 1, nom: "Églises à accompagner", effectif: 2 }],
  attendu: { lignes: [{ id: 1, nom: "Ngozi", ecart: 25, texte: "Fait nettement mieux." }, { id: 2, nom: "Musenyi", ecart: -40, texte: "En dessous." }] },
  atypiques: { lignes: [{ id: 2, atypique: true, raisons: ["Biens à risque : 100 %"] }] },
  jumelles: [{ id: 2, nom: "Musenyi", texte: "Musenyi peut s'inspirer de Ngozi.", lecons: ["Terrains titrés : 0 % contre 100 %"], modele: { id: 1, nom: "Ngozi" } }],
};

describe("analyse intelligente", () => {
  it("écrit les écarts avec leur signe", () => {
    expect(signe(12)).toBe("+12");
    expect(signe(-3)).toBe("-3");
    expect(signe(null)).toBe("—");
  });

  it("traduit un écart-type en mots", () => {
    expect(niveauEcart(0.1)).toBe("dans la moyenne");
    expect(niveauEcart(-1)).toBe("nettement en dessous de la moyenne");
    expect(niveauEcart(2)).toBe("très au-dessus de la moyenne");
  });

  it("garde la couleur attachée au profil", () => {
    expect(couleurProfil(0)).toBe(couleurProfil(4));
    expect(couleurProfil(0)).not.toBe(couleurProfil(1));
  });

  it("rédige la fiche d'une église à accompagner", () => {
    const f = ficheEglise(d, 2);
    expect(f.nom).toBe("Musenyi");
    const types = f.phrases.map((p) => p.type);
    expect(types).toEqual(["profil", "alerte", "alerte", "piste"]);
    expect(f.phrases[3].texte).toContain("Terrains titrés");
  });

  it("signale l'église qui sert de modèle", () => {
    const f = ficheEglise(d, 1);
    expect(f.phrases.at(-1).texte).toContain("Musenyi");
  });

  it("ne plante pas sans données", () => {
    expect(ficheEglise(null, 1)).toBeNull();
    expect(ficheEglise({ disponible: false }, 1)).toBeNull();
    expect(donneesEcarts(undefined)).toEqual([]);
  });

  it("évite que les noms se chevauchent sur la carte", () => {
    const pts = [{ id: 1, x: 0, y: 0, profil: 0 }, { id: 2, x: 0.01, y: 0.01, profil: 0 }, { id: 3, x: 5, y: 5, profil: 1 }, { id: 4, x: -5, y: -5, profil: 0 }];
    const v = etiquettesVisibles(pts, { 0: 3 + 10, 1: 1 });
    expect(v.has(3)).toBe(true);
    expect(v.has(1) && v.has(2)).toBe(false);
    expect(etiquettesVisibles(pts, {}, 2).has(2)).toBe(true);
  });
});
