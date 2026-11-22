# GitHub workflows de Snippet Searcher

Este repositorio define el CI y CD reutilizable. Cada servicio define sus disparadores en `.github/workflows/pipeline.yml` y fija la versión de los workflows que consume.

## Callers y eventos

| Caller | CI | CD |
| --- | --- | --- |
| [Snippets](https://github.com/JJT-INGSIS/snippets-service) | [Pipeline Kotlin](.github/workflows/kotlin-service-pipeline.yml) con [Gradle](.github/workflows/ci.yml) | El pipeline Kotlin llama a CD después del CI. |
| [Permissions](https://github.com/JJT-INGSIS/permissions-service) | Pipeline Kotlin | Igual que Snippets. |
| [PrintScript](https://github.com/JJT-INGSIS/printscript-service) | Pipeline Kotlin | Igual que Snippets. |
| [UI](https://github.com/JJT-INGSIS/snippet-searcher-ui) | [Frontend CI](.github/workflows/frontend-ci.yml) con npm, pruebas de contrato en el navegador y validación del contenedor en PR | El caller llama a CD después del CI. |

| Evento | Resultado |
| --- | --- |
| PR a `dev` o `main` | Ejecuta CI y confirma su resultado en el check requerido del caller. Sin publicación en GHCR ni despliegue. |
| Push a `dev` | Tras CI exitoso, construye y publica en GHCR. Con CD habilitado, despliega el digest publicado y registra evidencia si las comprobaciones pasan. |
| Push a `main` | Tras CI exitoso y con CD y PROD habilitados, promueve el digest verificado en DEV correspondiente al Git tree exacto. |
| Ejecución manual | Sigue pasando por CI. En DEV, los callers Kotlin pueden solicitar solo publicación y el caller de UI publica. En `main` permite reintentar una promoción habilitada. |

## Cómo se promueve una imagen

[CD](.github/workflows/cd.yml) tiene tres jobs. `publish` construye en DEV y devuelve el digest. `select` busca en `main` un recibo de un despliegue DEV verificado. `deploy` aplica el digest por SSH al manager de Swarm del ambiente. PROD reutiliza la imagen validada en DEV.

El recibo `sni25:verified` se registra en GitHub Deployments después de verificar el despliegue en DEV. Relaciona la imagen con el Git tree y la corrida que la construyó. PROD puede usar evidencia histórica aunque DEV haya avanzado. Si falta una coincidencia verificable o el CI de origen no fue exitoso, la promoción falla. Los tags de GHCR ayudan a localizar imágenes. La referencia desplegada se fija por digest.

## Variables, secretos y permisos

- **Variables del repositorio consumidor.** `CD_ENABLED=true` habilita el despliegue remoto. PROD requiere además `PROD_DEPLOY_ENABLED=true`. `DOCKER_PLATFORMS` usa `linux/amd64` por defecto, plataforma requerida por las VMs.
- **GitHub Environments.** Restringir `dev` a la rama `dev` y `prod` a `main`. Configurar `SSH_HOST`, `SSH_USER`, `SSH_PORT`, `SSH_PRIVATE_KEY` y `SSH_KNOWN_HOSTS` por ambiente. El job de despliegue verifica la clave del host y usa SSH sin interacción.
- **Build y publicación.** Los servicios Kotlin usan `GH_PACKAGES_USER` y `GH_PACKAGES_READ_TOKEN` para sus dependencias. En el build de la imagen se pasan como secretos de BuildKit. GitHub Actions usa su token automático para GHCR y Deployments. Las credenciales de ejecución de los servicios permanecen en Swarm.
- **Protección de PROD.** Exigir PR y checks en `main`, con la rama actualizada y sin bypass de pushes directos ni force push. El CD revalida en la VM, bajo el lock, que el HEAD esté vigente y provenga de una promoción autorizada de `dev` a `main`. Cada job recibe permisos para sus operaciones y los workflows anidados no pueden ampliarlos.

## Versionado y compatibilidad

Los callers fijan un tag de este repo y las llamadas internas con `$/` resuelven workflows de esa misma revisión. CD fija un commit revisado de Infra en `INFRA_REVISION`. Para actualizar herramientas de despliegue, integrá primero la revisión de Infra, comprobá su compatibilidad con el registro y los controles de versión de los callers, y publicá una versión nueva del workflow sin mover tags publicados. Los callers se actualizan explícitamente.

## Validación y recuperación

[Validate reusable workflows](.github/workflows/validate.yml) ejecuta el siguiente chequeo en PRs a `main` y pushes a `main`. Requiere Docker. El script usa una imagen de Actionlint fijada por digest y adapta `$/` solo en una copia temporal para validar los contratos entre workflows.

```bash
python3 scripts/lint_workflows.py
```

Si un despliegue pierde la conexión SSH, revisá el registro de la VM y reconciliá la operación antes de reintentar. Un rollback exitoso conserva el fallo de la candidata en GitHub y no revierte los datos. El [manual operativo de Infra](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-25-cd.md) describe el lock, la evidencia y la recuperación. La [guía de cortes de infraestructura](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-43-cd.md) cubre cambios al stack completo y compatibilidad de las herramientas.
