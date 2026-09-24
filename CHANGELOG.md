# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [0.2.1] - 2026-09-24

### Ajouté

- **registry** : MCP registry manifest and package ownership marker

## [0.2.0] - 2026-09-24

### Ajouté
- Annotations MCP (`readOnlyHint`, `idempotentHint`, `destructiveHint`) sur chaque outil.
- Tests de l'extraction d'identifiant YouTube (duplication volontaire avec pylips-mcp, documentée).
- Workflow de release sur tag `v*` : build du wheel, publication PyPI par Trusted Publishing, release GitHub.
- Démo enregistrée (GIF) et script de régénération.

### Modifié
- Migration vers `mcp` 2.

### Corrigé
- Le watcher de synchronisation n'est plus réécrit à chaque appel et s'arrête proprement.

## [0.1.0] - 2026-09-09

Première version publiée : configuration autonome, wheel installable avec point d'entrée, table des outils générée, tests et CI.
