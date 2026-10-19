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
Entre jobs se pasa un único descriptor JSON `artifact`: referencia por digest,
commit y árbol de origen, run e intento de construcción. Es un output interno;
los callers no necesitan outputs del workflow. No se suben ni descargan archivos
de Actions para transportar estos datos. El resumen de construcción lo genera
la Action de Docker y el de despliegue se obtiene del recibo remoto.

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
credenciales y pruebas reales. `v0.4.0` ya está publicada y los servicios la usan.
Esta simplificación fija `INFRA_REVISION` al commit de infra integrado y validado
`d86ab1e4928a3e51ef11676bcdbe2da28ffaf9b3` (PR #13). Incluye los seis comandos
del runner; los callers no pueden elegir otra revisión de los scripts.

La [guía de integración SNI-25](docs/sni-25-integration.md) explica el orden de
integración, versionado, configuración, pruebas y protecciones. El
[manual operativo de infra](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-25-cd.md)
documenta lock, journal, reconciliación SSH y rollback.

## Versionado y antecedente SNI-23

CI/publicación v0.3.1 se verificó en los tres servicios al commit
`73cc46862500f0cd19736f047d834ea7738d6021`. v0.3.0 era un tag anotado al mismo
commit y las llamadas anidadas resolvieron el objeto del tag en lugar del commit;
v0.3.1 es liviano. Se conservan las versiones publicadas, sin sobrescribirlas.

SNI-25 original está publicado en **v0.4.0**, al commit
`49014e0df8df8a634a78dabb85e4ff5adb1d992c`. La versión simplificada **v0.5.0**
elimina outputs públicos que no usan los servicios y cambia
el contrato interno con infra. Primero probar por SHA central y conservar su
referencia; después comprobar el commit integrado y el tag final antes de extenderlo
a los tres servicios. Para crear el tag liviano cuando se autorice la publicación:

```bash
git -c tag.gpgSign=false tag v0.5.0 <SHA-central-integrado-y-probado>
git cat-file -t v0.5.0
git rev-parse 'v0.5.0^{commit}'
```

`cat-file` debe devolver `commit`; confirmar también el SHA y tipo en el remoto
después de publicarlo. No usar `-a`, `-s` ni `-m`. El versionado es independiente
de gradle-conventions. Si estos repos públicos se privatizan, configurar acceso
para llamadas y checkouts antes de habilitar CD.

### Corrección de rollback v0.5.1

Mantiene el contrato público de v0.5.0 y fija infra al commit
`c2180b28abc1b44b9aecfdf855ff7af544339523`. La prueba real en dev detectó
que el verificador rechazaba `rollback_started` incluso cuando Swarm ya estaba
recuperando el digest anterior esperado. Ahora espera su convergencia y los 60
segundos de estabilidad, conservando el rechazo de otro digest y de un rollback
pausado. La Action de una candidata fallida continúa en rojo.

No sobrescribir v0.5.0. Antes de cerrar SNI-25, repetir el rollback real con
v0.5.1 y verificar el registro `recovered` sin operaciones pendientes.

## Validación local

```bash
python3 scripts/lint_workflows.py
```

Requiere Docker. El wrapper adapta `$/` solo en una copia temporal porque la versión
actual de actionlint no reconoce ese prefijo; los workflows oficiales lo conservan.
No se omiten los checks de contratos, expresiones ni ShellCheck. Las pruebas reales
de Actions, secrets y VMs siguen pendientes y están enumeradas en la guía SNI-25.
