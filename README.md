# GitHub workflows

Automatización reutilizable para los tres servicios de Snippet Searcher. Cada
servicio conserva sus triggers en `.github/workflows/pipeline.yml`; el central
coordina CI, publicación y despliegue independiente.

## Estructura y responsabilidades

- `kotlin-ci.yml`: `bash ./gradlew build --no-daemon`, Ubuntu 24.04 y JDK 21.
  Gradle controla tests, ktlint, detekt y JaCoCo.
- `kotlin-service-pipeline.yml`: CI requerido, agregador de PR y CD tras CI exitoso.
- `cd.yml`: jobs `publish` (dev), `select` (main) y `deploy` (ambiente correspondiente).
- `validate.yml`: valida YAML, expresiones y scripts mediante actionlint fijado por digest.
- `scripts/lint_workflows.py`: misma validación local, incluyendo contratos reutilizables.

Las llamadas internas usan `$/` para resolver archivos de este repo en la misma
revisión invocada por el consumidor. Los checkouts de CI/build son del servicio;
las herramientas de despliegue provienen de un commit fijo y revisado de infra.

## Eventos

| Evento | CI | Publicación y despliegue |
| --- | --- | --- |
| PR dev/main | Completo + Resultado requerido | Ninguno |
| Push dev | Completo | Publicar; con CD habilitado, desplegar, verificar y registrar evidencia |
| Push main | Completo | Con CD habilitado y prod autorizado, promover el digest verificado en dev; sin build |
| Manual dev | Completo | Publicación opcional; CD habilitado incluye publicación/verificación |
| Manual main | Completo | Reintento de promoción; pedir publicación falla |

CI fallido o cancelado impide CD. El agregador `Resultado requerido` no ejecuta
Gradle nuevamente y exige `verify.result == success`. Conservar el check anterior
`verify / verify / build` hasta comprobar el nombre y funcionamiento del nuevo.
No exigir jobs de CD como checks de PR: se omiten correctamente.

## Contrato y permisos

| Input | Default | Uso |
| --- | --- | --- |
| `publish` | `false` | Publicar desde dev después de CI |
| `deploy` | `false` | Publicar/desplegar dev o seleccionar/desplegar prod |
| `image-name` | Vacío | Paquete exacto `ghcr.io/<owner>/<repo>` del caller en minúsculas |
| `platforms` | `linux/amd64` | Plataformas separadas por comas, sin espacios |

Los callers leen `DOCKER_PLATFORMS`. Las dos VMs son x64, por lo que CD requiere
linux/amd64. QEMU se prepara solo al incluir ARM64.

Secrets: `GH_PACKAGES_USER`, `GH_PACKAGES_READ_TOKEN` para descargar convenciones
y biblioteca; `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS` opcionales para CI/publicación,
obligatorios al desplegar. Cada salto los reenvía explícitamente. El job final de
CD declara el environment que resuelve sus secretos y variables de SSH.

El PAT de dependencias llega al build como secretos BuildKit `github_actor` y
`github_token`, nunca como ARG/ENV persistidos. Preferir secrets de organización;
los de repo del mismo nombre tienen prioridad y deben retirarse después de verificar
la migración. GHCR y Deployments usan el token automático de Actions, sin otro PAT.

El caller concede `contents: read`, `actions: read`, `pull-requests: read`,
`packages: write` y `deployments: write`; los jobs reducen sus permisos según sus operaciones.
Los workflows anidados no pueden aumentar los permisos del caller.

## Imágenes y evidencia

Paquetes públicos independientes:

```text
ghcr.io/jjt-ingsis/snippets-service
ghcr.io/jjt-ingsis/permissions-service
ghcr.io/jjt-ingsis/printscript-service
```

Tags `sha-<SHA completo>` y `run-<run_id>-<run_attempt>`, sin `latest`.
**Desplegar por digest**: reconstruir un commit puede cambiar sus tags.
Las etiquetas incluyen repositorio, commit, Git tree y run/attempt de construcción.
Los outputs `image`, `digest`, `image-ref`, `source-sha`, `source-tree` identifican
la imagen publicada en dev o seleccionada para prod; quedan vacíos sin CD.

Buildx usa caché `type=gha` API v2 por servicio/plataformas. Esta caché no conserva
automáticamente los mounts Gradle entre runners. El Dockerfile empaqueta con
`bootJar`; CI ya comprobó el mismo commit con `build`.

Publicación no equivale a verificación. El Deployment explícito `sni25:verified`
guarda un recibo tras checks de la VM. Prod exige evidencia confiable, Git tree
exacto y el mismo digest. Dev puede haber avanzado: se recupera evidencia histórica
sin depender de logs/artefactos ni de su VM encendida. Sin coincidencia, falla.

## Branches, environments y habilitación

Servicios e infra: ramas cortas → PR a dev → PR dev a main. Dev es default;
squash para cambios individuales y merge commit para promociones. Workflows y
Gradle conventions conservan main y versiones propias.

Environments de cada servicio: dev solo desde dev, prod solo desde main, sin segundo
approval. Variables `SSH_HOST`, `SSH_USER`, `SSH_PORT` y secrets SSH. Runtime y
contraseñas de DB permanecen en Swarm; los environments no activan perfiles Spring.

Variables **de repositorio**:

- `CD_ENABLED=true`: habilita despliegue remoto; sin ella, solo CI/publicación.
- `PROD_DEPLOY_ENABLED=true`: permiso adicional después de verificar protección
  detallada de main, aplicada a administradores y sin bypass de pushes directos.

La API administrativa devolvió 403. Desde el navegador se activó y se verificó
el 13/10/2026 `Do not allow bypassing the above settings` en main de los tres
servicios: PR, CI y base actualizada se exigen también a administradores, sin
bypass específico de PR ni force push. Producción no se habilitó; todavía requiere
credenciales, integración y pruebas reales. El CD contiene un placeholder que
exige fijar primero el commit de infra integrado. No integrar los callers al
futuro v0.4.0 hasta publicarlo.

La [guía de integración SNI-25](docs/sni-25-integration.md) explica el orden de
integración, versionado, configuración, pruebas y protecciones. El
[manual operativo de infra](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-25-cd.md)
documenta lock, journal, reconciliación SSH y rollback.

## Versionado y antecedente SNI-23

CI/publicación v0.3.1 se verificó en los tres servicios al commit
`73cc46862500f0cd19736f047d834ea7738d6021`. v0.3.0 era un tag anotado al mismo
commit y las llamadas anidadas resolvieron el objeto del tag en lugar del commit;
v0.3.1 es liviano. Se conservan las versiones publicadas, sin sobrescribirlas.

SNI-25 propone **v0.4.0, todavía no publicada por estos cambios**. Primero probar
por SHA central y conservar su referencia, comprobar el commit integrado y luego
probar el tag final antes de extenderlo a los tres servicios. Para crear el tag
liviano cuando se autorice la publicación:

```bash
git -c tag.gpgSign=false tag v0.4.0 <SHA-central-integrado-y-probado>
git cat-file -t v0.4.0
git rev-parse 'v0.4.0^{commit}'
```

`cat-file` debe devolver `commit`; confirmar también el SHA y tipo en el remoto
después de publicarlo. No usar `-a`, `-s` ni `-m`. El versionado es independiente
de gradle-conventions. Si estos repos públicos se privatizan, configurar acceso
para llamadas y checkouts antes de habilitar CD.

## Validación local

```bash
python3 scripts/lint_workflows.py
```

Requiere Docker. El wrapper adapta `$/` solo en una copia temporal porque la versión
actual de actionlint no reconoce ese prefijo; los workflows oficiales lo conservan.
No se omiten los checks de contratos, expresiones ni ShellCheck. Las pruebas reales
de Actions, secrets y VMs siguen pendientes y están enumeradas en la guía SNI-25.
