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

Exécutions de `main` après la fusion de la PR #1 (commit de fusion
`47e325a94c7b7fb67fbb049357d5a663810af139`) :
[Java](https://github.com/rdalmasghub/tp2rental/actions/runs/45629599131) et
[Python](https://github.com/rdalmasghub/tp2rental/actions/runs/45629599254).
Les dix jobs (tests, qualité, image, `supply-chain`, `scan` pour chaque service)
sont verts.

| Preuve | Java | Python |
|---|---|---|
| Digest vérifié | `sha256:e3d164d234e28c816cace3f8337ae3d9aa6e1f1593facd5d635eb0db2079f1b9` | `sha256:e911a44c39f8c265b72f30ebee5a3914a7398d35193a1bc79c809b2fba6e8161` |
| Identité du certificat Cosign | `https://github.com/rdalmasghub/tp2rental/.github/workflows/ci-car-rental.yml@refs/heads/main` | `https://github.com/rdalmasghub/tp2rental/.github/workflows/ci-pricing.yml@refs/heads/main` |
| Dépôt et commit de la provenance | `rdalmasghub/tp2rental`, `refs/heads/main`, commit `47e325a94c7b7fb67fbb049357d5a663810af139` | identique |
| Deux composants du SBOM | `libc6` 2.35-0ubuntu3.18 (paquet système) ; `spring-web` 6.2.0 (bibliothèque) | `libc6` 2.41-12+deb13u5 (paquet système) ; `fastapi` 0.162.7 (bibliothèque) |
| Rapport Trivy | [Code scanning](https://github.com/rdalmasghub/tp2rental/security/code-scanning), catégorie `trivy-car-rental` | idem, catégorie `trivy-pricing` |

Le résumé du job `supply-chain` affiche le digest, l'identité du certificat et le
commit source. Le SBOM se télécharge depuis les artefacts de l'exécution
(`sbom-java.spdx.json`, `sbom-python.spdx.json`, conservés sept jours). Le paquet
racine de chaque SBOM porte le digest ci-dessus.

Contrôles faits en dehors des jobs, à partir de l'API GitHub :

- chaque digest a deux attestations, une provenance SLSA et un SBOM SPDX 2.3
  (177 paquets pour Java, 110 pour Python), dont le sujet est ce digest ;
- le tag `latest` de chaque image pointe sur ce même digest ;
- les deux analyses Trivy sont enregistrées sur le commit de fusion.

La vérification se rejoue depuis un poste, sans clé ni secret. Elle retourne le
code 0 pour le bon dépôt et échoue pour un autre dépôt :

```bash
gh attestation verify "oci://ghcr.io/rdalmasghub/tp2rental/car-rental-service@sha256:e3d164d234e28c816cace3f8337ae3d9aa6e1f1593facd5d635eb0db2079f1b9" \
  --repo rdalmasghub/tp2rental
```

## 5. Ce que les preuves établissent, et leurs limites

Elles établissent :

- **Quel contenu** : le déploiement peut référencer `image@digest`, qui ne change
  pas, alors que `latest` peut être déplacé.
- **Qui l'a produit** : la signature Cosign lie ce digest à l'identité du workflow
  sur `refs/heads/main`, par un certificat à courte durée de vie obtenu avec le
  jeton OIDC de GitHub. Aucune clé privée ni secret de signature n'existe.
- **D'où il vient** : la provenance relie le digest au dépôt, au workflow et au
  commit de fusion.
- **Ce qu'il contient** : le SBOM, attesté sur le même digest, liste les paquets
  système et applicatifs.

Elles n'établissent pas :

- **L'absence de vulnérabilité.** Une signature prouve l'origine, pas la
  sécurité. C'est le rôle de Trivy, dont le résultat dépend de la base de
  vulnérabilités du jour de l'analyse.
- **Une protection effective.** Une signature que personne ne vérifie ne protège
  rien. Une règle d'admission côté cluster, qui refuserait une image non signée,
  fermerait cette étape.
- **Un contrôle indépendant dans le workflow.** Le workflow vérifie sa propre
  sortie : cela prouve la cohérence de la chaîne, pas qu'un tiers l'a contrôlée.
  La vérification rejouée depuis un poste, avec `gh attestation verify`, en est un.

## 6. Incident rencontré

Sur la PR #1, `Java quality` a échoué : Maven Central a répondu
`429 Too Many Requests` pendant la résolution des dépendances Gradle. Ce n'était
pas une erreur Checkstyle, et `Java tests` avait réussi sur le même commit. Le
même job est vert sur `main`. La PR a été fusionnée avec ce contrôle rouge, ce que
l'absence de protection de branche permet ; il aurait fallu relancer le job
(`gh run rerun --failed`) avant de fusionner.
