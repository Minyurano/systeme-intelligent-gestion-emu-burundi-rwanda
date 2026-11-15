import { describe, expect, it } from "vitest";
import { bif, definirDevise, devise, nombre, moisCourt, CATEGORIES, COULEUR_CATEGORIE } from "./format";

describe("format des montants", () => {
  it("affiche un tiret pour une valeur absente", () => {
    expect(bif(null)).toBe("—");
    expect(bif(undefined)).toBe("—");
    expect(bif("")).toBe("—");
    expect(nombre(null)).toBe("—");
  });

  it("utilise la monnaie de l'organisation", () => {
    definirDevise("RWF");
    expect(devise()).toBe("RWF");
    expect(bif(1500)).toMatch(/1.500 RWF$/);
    definirDevise(null);
    expect(devise()).toBe("BIF");
  });

  it("abrège les grands montants", () => {
    definirDevise("BIF");
    expect(bif(2_500_000, true)).toMatch(/^2,5 M BIF$/);
    expect(bif(3_000_000_000, true)).toMatch(/^3 Md BIF$/);
  });

  it("formate un mois court", () => {
    expect(moisCourt("2026-01")).toMatch(/26/);
  });

  it("donne une couleur à chaque catégorie", () => {
    for (const c of Object.keys(CATEGORIES)) expect(COULEUR_CATEGORIE[c]).toMatch(/^#[0-9A-F]{6}$/i);
  });
});
