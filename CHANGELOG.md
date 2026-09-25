# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [0.3.0] - 2026-09-25

### Modifié

- The code now lives in a `catt_mcp` package (`catt_mcp.server`, `catt_mcp.sync_watcher`). The wheel used to install top-level `server` and `sync_watcher` modules, which overwrote each other with other MCP servers (denon-mcp, pylips-mcp) installed in the same environment. `python server.py` from a clone still works (thin launcher), and `python -m catt_mcp` is new.
- The sync watcher is started as a module (`python -m catt_mcp.sync_watcher`) instead of by file path.

### Corrigé

- `catt-mcp --help` and `--version` answer without any configuration (they used to start the server).

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
