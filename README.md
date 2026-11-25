# Rental DevOps — checkpoint 01

Ce monorepo est le socle d'une formation DevOps pratique destinée à des
étudiants de master. Le checkpoint 01 ajoute une boucle d'intégration continue
observable au socle applicatif : tests, qualité, artefacts de diagnostic,
construction des images et détection de secrets.

## Architecture actuelle

| Service | Technologie | Port | Responsabilité |
|---|---|---:|---|
| `car-rental-service` | Java 17, Spring Boot, Gradle | 8080 | Gestion en mémoire des voitures et locations |
| `pricing-service` | Python 3.12, FastAPI | 8000 | Calcul autonome des tarifs |

Les deux services partagent un réseau Docker. Ils ne communiquent pas encore
entre eux.

## Prérequis

- Git ;
- JDK 17 ou supérieur ;
- Python 3.12 ou une version compatible ;
- Docker avec Docker Compose.

Vérification rapide :

```bash
python scripts/course.py prerequisites
```

## Installation des dépendances Python

```bash
cd apps/pricing-service
python -m venv .venv
```

Activation sous Linux ou macOS :

```bash
source .venv/bin/activate
```

Activation sous PowerShell :

```powershell
.venv\Scripts\Activate.ps1
```

Puis :

```bash
python -m pip install -r requirements-dev.txt
cd ../..
```

## Vérification locale

Depuis la racine :

```bash
python scripts/course.py verify
```

Cette commande exécute les tests Gradle et Pytest, puis Checkstyle et Ruff, puis
la politique de chaîne logicielle. Pour diagnostiquer une étape séparément,
utiliser `test`, `lint`, `test-java`, `test-python`, `lint-java`,
`lint-python` ou `supply-chain-policy`.

`supply-chain-policy` échoue si une action GitHub distante n'est pas référencée
par un SHA de commit complet, ou si une instruction `FROM` n'a pas de digest
`sha256`. Pour mettre à jour une référence, résoudre la nouvelle version puis
garder la version lisible en commentaire (`# v6.1.0`) ; Dependabot le fait
automatiquement.

## Intégration continue

Chaque pull request vers `main` déclenche huit contrôles lisibles :

- tests, qualité et construction de l'image pour le service Java ;
- tests, qualité et construction de l'image pour le service Python ;
- détection de secrets sur l'historique Git ;
- revue des dépendances modifiées (échec à partir de la sévérité `high`).

Les rapports de tests et de qualité sont conservés sept jours comme artefacts
GitHub Actions.

## Chaîne logicielle

Aucune image n'est publiée depuis une pull request. Sur `main`, après la
publication dans GHCR, chaque service enchaîne deux jobs qui ne désignent
l'image que par le digest fourni par Buildx :

1. `supply-chain` génère un SBOM SPDX JSON (artefact conservé sept jours),
   signe l'image avec Cosign sans clé, atteste sa provenance et son SBOM, puis
   vérifie lui-même la signature et la provenance ;
2. `scan` exécute Trivy sur ce même digest, seulement si la vérification a
   réussi.

La signature n'utilise aucune clé persistante : l'identité vérifiée est celle du
workflow, prouvée par le jeton OIDC de GitHub Actions.

## Exécution avec Docker Compose

```bash
python scripts/course.py compose-up
python scripts/course.py smoke
```

Endpoints utiles :

```text
GET  http://localhost:8080/health
GET  http://localhost:8080/cars
GET  http://localhost:8000/health
POST http://localhost:8000/quotes
GET  http://localhost:8000/docs
```

Arrêt :

```bash
python scripts/course.py compose-down
```

## Organisation

```text
apps/                 Services applicatifs
archive/              Notes historiques conservées
course/               Présentation Quarto et travaux pratiques
docs/                 État de référence et checkpoints
infra/                Future infrastructure de test
scripts/              Commandes portables du cours
tests/                Futures suites de tests système
.github/workflows/     Pipelines CI par service et sécurité du dépôt
```

## Limites intentionnelles du checkpoint

- stockage Java uniquement en mémoire ;
- aucune communication entre les services ;
- aucune base PostgreSQL ni migration ;
- aucun test de contrat ou test E2E ;
- aucun manifeste Kubernetes ou cluster Kind ;
- actions tierces non encore figées par empreinte SHA ;
- aucune nomenclature SBOM ni signature des images.

Voir [la fiche du checkpoint](docs/CHECKPOINT-01.md), le
[support de cours](course/slides/01-ci.qmd) et le [TP 01](course/labs/tp01.qmd).

Le point de départ étudiant reste disponible sous le tag
`checkpoint/00-starter`. L'état validé de cette étape est publié sous
`checkpoint/01-ci`.

L'état historique antérieur à la refonte reste disponible sous le tag
`legacy/v1-microservices`.
