# TP 02 — compte rendu

## 1. Références avant le TP

Toutes les références étaient **mutables** : un tag ou une branche peut être
déplacé sans que notre dépôt change.

| Type | Référence | Statut avant | Statut après |
|---|---|---|---|
| Action | `actions/checkout@v6`, `setup-java@v6`, `setup-python@v7`, `upload-artifact@v7` | mutable (tag) | SHA de 40 caractères |
| Action | `docker/*@v4`, `@v6`, `@v7`, `github/codeql-action/upload-sarif@v4`, `gitleaks-action@v3` | mutable (tag) | SHA de 40 caractères |
| Action | `aquasecurity/trivy-action@master` | mutable (**branche**, change à chaque commit) | SHA, release v0.36.0 |
| Image de base | `gradle:8.14-jdk17`, `eclipse-temurin:17-jre-jammy`, `python:3.12-slim` | mutable (tag) | tag **et** digest `sha256` |

Le digest retenu est celui de l'index multi-architecture, pas celui d'une
plateforme : la même référence se résout sur un poste arm64 et sur un runner
amd64.

## 2. Modèle de risques

| Élément | Scénario de substitution | Impact | Contrôle qui le réduit |
|---|---|---|---|
| Action GitHub | Le tag `v6` est déplacé vers un commit malveillant (compte mainteneur compromis). | Le code s'exécute dans nos jobs avec leur `GITHUB_TOKEN`, y compris `packages: write` : modification d'images publiées, exfiltration. | SHA complet, `supply-chain-policy`, mises à jour Dependabot relues en PR. |
| Image de base | Le manifeste derrière `python:3.12-slim` est remplacé. | Le même Dockerfile produit un contenu différent et non relu ; build non reproductible. | Digest `sha256` en plus du tag, `supply-chain-policy`, Dependabot `docker`. |
| Image produite | `latest` est repointé après le scan. | On déploie une image qui n'est pas celle qui a été testée, scannée et signée. | Seul `image@digest` est utilisé ; signature Cosign et provenance vérifiées avant Trivy. |

Le tag `latest` reste publié pour la lisibilité, mais aucun job en aval ne s'en
sert.

## 3. Dependency review et Trivy

Les deux contrôles regardent à deux moments et à deux endroits différents.

- **Dependency review** compare les dépendances déclarées entre la base et la
  tête d'une pull request. Il est *préventif* et centré sur le **changement** :
  il bloque l'introduction d'une dépendance vulnérable avant la fusion. Il ne voit
  que ce que le graphe de dépendances connaît.
- **Trivy** analyse le **contenu final de l'image** une fois construite : paquets
  du système de l'image de base, bibliothèques applicatives effectivement
  présentes, dépendances transitives. Il décrit l'état réel livré, mais
  seulement après publication et selon la base de vulnérabilités du jour.

Une dépendance saine à l'entrée d'une PR peut devenir vulnérable plus tard, et un
paquet système vulnérable n'apparaît dans aucun manifeste : il faut les deux.

## 4. Preuves d'une exécution réussie sur `main`

À compléter après la première exécution verte sur `main` (onglet Actions, jobs
`supply-chain` et `scan`, puis page *Summary* du job).

| Preuve | Java | Python |
|---|---|---|
| Digest vérifié | _à compléter_ | _à compléter_ |
| Identité du certificat Cosign | _à compléter_ | _à compléter_ |
| Dépôt et commit de la provenance | _à compléter_ | _à compléter_ |
| Deux composants du SBOM (un paquet système, une bibliothèque) | _à compléter_ | _à compléter_ |
| Lien vers le rapport Trivy | _à compléter_ | _à compléter_ |

Le résumé du job `supply-chain` affiche déjà le digest, l'identité du certificat
et le commit source. Le SBOM se télécharge depuis les artefacts de l'exécution
(`sbom-java.spdx.json`, `sbom-python.spdx.json`, conservés sept jours).
