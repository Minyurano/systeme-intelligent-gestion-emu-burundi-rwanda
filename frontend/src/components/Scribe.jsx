/*
  Illustration animée du registre : une personne écrit dans le grand livre des membres.
  - les lignes d'encre se tracent l'une après l'autre, la plume suit la ligne en cours ;
  - quand quelqu'un tape dans le formulaire (actif), l'écriture accélère et des étincelles apparaissent ;
  - l'anneau extérieur montre la progression de la fiche (0 à 100 %), il bat quand la fiche est prête ;
  - la pastille « EN COURS » clignote pendant la saisie, « PRÊT » quand tout l'obligatoire est rempli.
  Dessin original, uniquement des formes simples.
*/
export default function Scribe({ actif = false, progression = 0, pret = false }) {
  const R = 132;
  const circ = 2 * Math.PI * R;
  return (
    <div className={`scribe${actif ? " actif" : ""}${pret ? " pret" : ""}`} aria-hidden="true">
      <svg viewBox="0 0 320 320" role="presentation">
        <defs>
          <radialGradient id="sc-fond" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor="var(--sc-fond-1)" />
            <stop offset="100%" stopColor="var(--sc-fond-2)" />
          </radialGradient>
          <radialGradient id="sc-lampe" cx="50%" cy="0%" r="100%">
            <stop offset="0%" stopColor="#ffd77a" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#ffd77a" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="sc-page" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#fffdf6" />
            <stop offset="100%" stopColor="#f3ecd9" />
          </linearGradient>
          <clipPath id="sc-cercle"><circle cx="160" cy="160" r="120" /></clipPath>
        </defs>

        {/* Ondes de fond */}
        <circle className="sc-onde o1" cx="160" cy="160" r="120" />
        <circle className="sc-onde o2" cx="160" cy="160" r="120" />

        {/* Anneau de progression */}
        <circle cx="160" cy="160" r={R} className="sc-piste" />
        <circle cx="160" cy="160" r={R} className="sc-progres"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - Math.min(100, progression) / 100)} transform="rotate(-90 160 160)" />

        <g clipPath="url(#sc-cercle)">
          <rect x="0" y="0" width="320" height="320" fill="url(#sc-fond)" />
          {/* Fenêtre et croix discrète au mur */}
          <rect x="196" y="62" width="58" height="70" rx="6" className="sc-fenetre" />
          <path d="M225 62 V132 M196 97 H254" className="sc-fenetre-trait" />
          <path d="M150 46 v26 M141 55 h18" className="sc-croix" />

          {/* Lumière de la lampe */}
          <path className="sc-halo-lampe" d="M70 118 L20 260 L190 260 L110 118 Z" fill="url(#sc-lampe)" />
          <path d="M62 112 h56 l-10 -20 h-36 z" className="sc-abat-jour" />
          <path d="M90 112 v-30" className="sc-pied-lampe" />

          {/* Personne : buste, tête, cheveux */}
          <g className="sc-personne">
            <path d="M118 262 C118 205 140 188 178 188 C216 188 238 205 238 262 Z" className="sc-buste" />
            <path d="M166 188 l12 20 l12 -20" className="sc-col" />
            <rect x="170" y="172" width="16" height="20" rx="6" className="sc-peau" />
            <g className="sc-tete">
              <ellipse cx="178" cy="150" rx="25" ry="28" className="sc-peau" />
              <path d="M153 147 C152 120 170 112 182 114 C200 116 206 132 203 146 C196 136 182 132 168 136 C162 138 157 142 153 147 Z" className="sc-cheveux" />
              {/* regard baissé vers le livre */}
              <path d="M167 156 q4 3 8 0 M184 156 q4 3 8 0" className="sc-yeux" />
              <path d="M174 168 q5 3 10 0" className="sc-bouche" />
            </g>
          </g>

          {/* Bureau */}
          <rect x="-10" y="250" width="340" height="80" className="sc-bureau" />
          <rect x="-10" y="250" width="340" height="6" className="sc-bureau-bord" />

          {/* Registre ouvert */}
          <g transform="translate(78 206) rotate(-4)">
            <path d="M0 8 L84 0 L84 62 L0 70 Z" fill="url(#sc-page)" className="sc-livre" />
            <path d="M84 0 L168 8 L168 70 L84 62 Z" fill="url(#sc-page)" className="sc-livre" />
            <path d="M84 0 V62" className="sc-reliure" />
            {/* lignes déjà écrites, page de gauche */}
            <path d="M12 20 H72 M12 30 H66 M12 40 H70 M12 50 H58" className="sc-ecrit" />
            {/* lignes en cours d'écriture, page de droite */}
            <path d="M96 16 H156" className="sc-ligne l1" pathLength="1" />
            <path d="M96 28 H150" className="sc-ligne l2" pathLength="1" />
            <path d="M96 40 H154" className="sc-ligne l3" pathLength="1" />
            {/* plume qui suit la ligne */}
            <g className="sc-plume">
              <g transform="translate(96 16)">
                <circle r="2.4" className="sc-encre" />
                <path d="M0 0 L22 -30 L27 -26 Z" className="sc-plume-corps" />
                <path d="M22 -30 C30 -42 40 -46 46 -44 C40 -36 33 -30 27 -26 Z" className="sc-plume-barbe" />
                {/* main qui tient la plume */}
                <ellipse cx="17" cy="-16" rx="9" ry="7" className="sc-peau sc-main" />
                <path d="M24 -12 C40 -4 60 -10 76 -30" className="sc-bras" />
              </g>
            </g>
          </g>

          {/* Étincelles quand on tape */}
          <g className="sc-etincelles">
            <circle cx="236" cy="190" r="2.5" /><circle cx="250" cy="214" r="1.8" /><circle cx="226" cy="226" r="2" />
          </g>
        </g>

        {/* Sceau de validation */}
        <g className="sc-sceau" transform="translate(252 250)">
          <circle r="22" />
          <path d="M-9 0 l6 6 l12 -13" />
        </g>
      </svg>
      <div className="sc-etat">
        <i />{pret ? "Fiche prête" : actif ? "Écriture en cours" : "En attente de saisie"}
        <b>{Math.round(progression)} %</b>
      </div>
    </div>
  );
}
