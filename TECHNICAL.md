# Notes techniques — News Analyser

## 1. Objectifs du brief

1. Collecter des articles de 8 sources (titre, contenu, URL, source) dans MongoDB  
2. Classifier la toxicité (label + score de confiance)  
3. Exposer une API `POST /predict` (validation, Swagger, persistance)  
4. Calculer le % d’articles *lightly toxic* / *highly toxic* par source + graphique  
5. Packager l’API + Mongo avec Docker  

---

## 2. Architecture retenue

Découpage **par responsabilité**, volontairement minimal :

| Module | Responsabilité |
|--------|----------------|
| `config/settings.py` | Config unique via `.env` (Pydantic Settings) |
| `src/scrapers/` | Interface commune + 1 scraper / site + helpers |
| `src/db/` | Connexion Mongo + repositories typés |
| `src/ml/` | Un seul wrapper de classification |
| `src/api/` | FastAPI : schemas + route `/predict` |
| `src/analysis/` | Agrégation stats + chart matplotlib |
| `scripts/` | Orchestration CLI (collect / predict / stats) |

**Pourquoi pas un monolithe script unique ?**  
Le brief demande API + Docker + stats + scrapers hétérogènes. Séparer scrape / ML / API évite de recharger le modèle à chaque scrape et permet de relancer chaque étape indépendamment.

**Pourquoi MongoDB ?**  
Imposé par le brief ; adapté au stockage semi-structuré (articles, prédictions, stats) avec upsert par URL.

---

## 3. Choix scraping

Les 8 sites ne se comportent pas de la même façon (bot walls, archives datées, cookies CMP). Approche retenue : **le moyen le plus simple qui marche pour chaque site**, après probes.

| Source | Méthode | Justification |
|--------|---------|---------------|
| humanite, marianne, france3 | httpx + archives datées | HTML accessible, pagination / date-walk stables |
| mediacites | RSS + HTML corps | Pas d’archive utile |
| gamespot | RSS fulltext | Listing HTML souvent bloqué |
| france24 | Playwright + archives mensuelles paginées | Cookie wall / rendu dynamique |
| lemonde, lepoint | Playwright headed + archives | Anti-bot / shell vide en headless (Le Point) |

### Décisions transverses

- **Date-walk** jour par jour (ou mois pour France24) jusqu’à `MAX_ARTICLES_PER_SOURCE` (30) : couverture temporelle sans dependre d’un seul listing homepage.  
- **Dedup par URL normalisée** : upsert Mongo `articles.url` unique.  
- **Pagination bornée** (`limit` passé à `collect_paginated_links`) : évite de sur-fetcher au-delà du quota.  
- **Sauvegarde incrémentale** pendant le scrape : un crash Playwright ne perd plus toute la source.  
- **Consent banners** : clics limités aux CMP (Didomi / OneTrust…), pas aux boutons éditoriaux.

On n’a **pas** unifié tous les sites sur Playwright : trop lent et fragile pour les sites déjà OK en httpx/RSS.

---

## 4. Choix ML (toxicité)

### Modèle

[`textdetox/xlmr-base-toxicity-classifier`](https://huggingface.co/textdetox/xlmr-base-toxicity-classifier)

| Critère | Décision |
|---------|----------|
| Tâche | Classification **binaire** toxic / neutral → exposée en `toxic` / `non-toxic` |
| Langues | Multilingue XLM-R (FR + EN) → utile pour France + Gamespot |
| Taille | **Base** plutôt que Large / Twitter-Large : RAM, temps CPU, Docker raisonnables |
| Entrée | `title + "\n" + content`, tronqué à 512 tokens (limite du modèle) |
| Score | Softmax de la classe prédite (confiance) |
| Niveaux Partie 3 | `P(toxic) < 0.5` → non-toxic ; `[0.5, 0.8)` lightly ; `≥ 0.8` highly |

**Pourquoi pas un embedder séparé ?**  
Le classifieur Transformer tokenise et encode déjà le texte en interne. Un embedder (sentence-transformers) servirait à de la similarité / clustering, pas à ce brief.

**Pourquoi pas CamemBERT FR-only ?**  
Gamespot est en anglais ; un modèle FR-only dégraderait cette source.

**Pourquoi pas Large / twitter-xlmr ?**  
Meilleure précision théorique, mais ~2 Go+, téléchargement et inference CPU trop lourds pour une démo Docker portable. Le base reste aligné TextDetox / même famille de dataset.

---

## 5. Pourquoi les prédictions sont (quasi) toutes « non-toxic »

Sur la base collectée (~220 articles de presse), le batch `predict_all` a produit **100 % `non-toxic`**, donc les stats `lightly_%` / `highly_%` sont à **0 %** pour chaque source.

Ce n’est **pas un bug** du pipeline.

### Ce que le modèle mesure

Il détecte le **langage toxique** (insultes, agressivité, haine formulée à la 2ᵉ personne, etc.), tel qu’annoté dans des datasets type commentaires / réseaux sociaux (TextDetox / Jigsaw-like).

Il ne détecte **pas** :

- le fait qu’un article *parle* de racisme, de guerre ou de violence ;  
- la « toxicité » politique ou éditoriale ;  
- un sujet sensible traité en ton journalistique neutre.

### Exemple observé

| Texte | Résultat |
|-------|----------|
| Article France3 *« Sale noir » : un match interrompu…* (reportage) | `non-toxic` (P(toxic) ≈ 0.003) |
| Phrase mock *« Tu es un idiot de merde… »* | `toxic` / `highly-toxic` (P(toxic) ≈ 0.999) |

Le reportage **cite** ou **décrit** un incident ; le style reste celui d’une rédaction. Le classifieur répond correctement : ce n’est pas du discours toxique au sens entraînement du modèle.

### Conséquence pour la Partie 3

Des pourcentages à 0 % sur de la **presse écrite mainstream** sont un résultat **attendu et argumentable** :

1. Corpus = articles éditoriaux, pas fils de commentaires.  
2. Seuils 0.5 / 0.8 restent exigeants (volontairement).  
3. Le modèle est validé hors corpus presse via `/predict` et textes d’insulte synthétiques (réponse `toxic`).

Si l’on voulait des taux non nuls **sur ce corpus**, il faudrait changer de question métier (ex. « sujet sensible », autre modèle / labels, baisser artificiellement les seuils — ce qui fausse la toxicité au sens TextDetox). On a choisi de **garder le comportement fidèle au modèle**.

---

## 6. API FastAPI

- `POST /predict` : validation Pydantic (`text` obligatoire, non vide), réponse typée, insertion Mongo `predictions`.  
- Swagger auto : `/docs`.  
- Chargement modèle au **lifespan** : première requête déjà chaude.  
- Pas d’auth : hors scope brief.

---

## 7. Stats

`scripts/compute_stats.py` :

1. Lit `predictions`  
2. Agrège par `source` via `toxicity_level`  
3. Upsert dans `stats`  
4. Table console + `outputs_toxicity_stats.json` + `outputs_toxicity_stats.png`

---

## 8. Docker

| Choix | Pourquoi |
|-------|----------|
| Compose `api` + `mongo:7` | Reproductible sur un autre PC |
| Torch **CPU** dans l’image | Pas de GPU requis |
| Modèle **pré-téléchargé** au build | Évite un download surprise au premier `up` |
| Mongo publié en **27018** | N’écrase pas un Mongo local sur 27017 |
| Entrypoint Python (pas `.sh`) | Évite les bugs CRLF Windows (`exec format error`) |
| Volume `hf_cache` | Cache HF entre rebuilds partiels |

Scraping / batch scoring restent plutôt **hors container** (Playwright headed, cookies sites FR). L’image Docker cible surtout l’**API + Mongo**.

---

## 9. Limites connues

- Presse ≠ commentaires : taux toxiques bas / nuls.  
- Troncature 512 tokens : seuls le début titre+corps sont scorés.  
- Playwright headed : dépend de l’environnement graphique pour collecter Le Point / Le Monde / France24.  
- Mediacités peut renvoyer moins de 30 items selon le RSS.  
- Premier `docker compose build` est long (dépendances + modèle).

---

## 10. Fichiers de config utiles

| Fichier | Rôle |
|---------|------|
| `.env` / `.env.example` | URI Mongo, quotas scrape, modèle, seuils |
| `DOCKER.md` | Run Docker détaillé |
| `outputs_toxicity_stats.*` | Dernière analyse Partie 3 |
