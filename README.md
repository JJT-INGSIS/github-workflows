# GitHub workflows

Automatización reutilizable para los tres servicios de Snippet Searcher. Cada servicio conserva sus triggers en `.github/workflows/pipeline.yml` y construye/publica únicamente su propia imagen.

## Estructura y responsabilidades

```text
.github/workflows/
├── kotlin-ci.yml
├── kotlin-service-pipeline.yml
└── cd.yml
```

- `kotlin-ci.yml`: ejecuta `bash ./gradlew build --no-daemon` en Ubuntu 24.04 con JDK 21. Las convenciones Gradle deciden tests, ktlint, detekt y JaCoCo.
- `kotlin-service-pipeline.yml`: ejecuta CI y llama a CD después de CI exitoso, si el consumidor solicita publicación y el evento la permite.
- `cd.yml`: construye y publica con un job `publish`. SNI-25 añadirá en este mismo archivo el job de despliegue por SSH. Publicar una imagen no demuestra que se haya desplegado ni validado en una VM.

Las llamadas internas usan `$/` para resolver los archivos del repo central en la misma revisión que invocó el consumidor. Los servicios llaman al punto de entrada mediante una versión concreta. El checkout de CI y de publicación corresponde al servicio consumidor, no a este repositorio.

## Eventos y contrato del pipeline

| Evento del servicio | CI | Publicación |
| --- | --- | --- |
| PR a `dev` o `main` | Sí | No |
| Push a `dev` | Sí | Después de CI exitoso |
| Push a `main` | Sí | No |
| Ejecución manual en `dev` o `main` | Sí | Solo si se selecciona `publish` |

CI fallido o cancelado no habilita CD. El pipeline y `cd.yml` comprueban el evento y la referencia: solicitar `publish: true` desde una PR u otra rama no publica. No hay filtro `back/**`: cada servicio tiene un repositorio y contexto raíz independientes.

| Input de `kotlin-service-pipeline.yml` | Default | Uso |
| --- | --- | --- |
| `publish` | `false` | Mantiene compatibles a los consumidores que solo usan CI |
| `image-name` | Vacío | Obligatorio al publicar; debe coincidir con `ghcr.io/<owner>/<repo>` del caller en minúsculas |
| `platforms` | `linux/amd64` | `linux/amd64`, `linux/arm64` o ambas separadas por comas, sin espacios |

Los callers leen la variable de repositorio `DOCKER_PLATFORMS`, con `linux/amd64` como fallback. Confirmar con Thiago la arquitectura de las VMs antes de cerrar SNI-23. Para ambas arquitecturas, definir `linux/amd64,linux/arm64`. QEMU se prepara solo cuando se solicita ARM64.

## Credenciales y permisos

Los secrets de dependencias son `GH_PACKAGES_USER` y `GH_PACKAGES_READ_TOKEN`. El usuario debe ser el dueño del PAT; el token necesita lectura de `gradle-conventions` y, para PrintScript, de la biblioteca publicada. Preferir secrets de organización con acceso a los tres servicios; al migrar, los secrets de repositorio con el mismo nombre tienen prioridad y deben retirarse después de comprobar los valores de organización.

Cada salto de workflows reenvía estos dos secrets explícitamente. Docker los recibe únicamente como secretos de BuildKit `github_actor` y `github_token`, compatibles con los Dockerfiles existentes. No se agregan como build args, variables persistidas en la imagen ni credenciales de runtime.

La autenticación de GHCR usa `secrets.GITHUB_TOKEN`, generado por Actions para el repositorio consumidor, con `github.actor` como usuario. No usa el PAT de lectura de dependencias ni requiere otro PAT para publicar.

El job del caller concede `contents: read` y `packages: write`; el job de CI reduce sus permisos a `contents: read`. Los workflows anidados no pueden aumentar los permisos del caller. Conservar los IDs `verify` y `build` mantiene el check actual `verify / verify / build`; confirmar el nombre exacto en GitHub antes de configurarlo como requerido.

## Imágenes, caché y trazabilidad

Paquetes independientes:

```text
ghcr.io/jjt-ingsis/snippets-service
ghcr.io/jjt-ingsis/permissions-service
ghcr.io/jjt-ingsis/printscript-service
```

Cada publicación recibe los tags `sha-<SHA completo>` y `run-<run_id>-<run_attempt>`. No se genera `latest`. El tag por SHA puede cambiar si se reconstruye el mismo commit; para desplegar o promover, usar siempre `imagen@sha256:...`.

Las labels guardan `org.opencontainers.image.source`, `org.opencontainers.image.revision`, `io.jjt.source-tree` e `io.jjt.actions-run`. El Git tree identifica el contenido completo del repositorio; permite reconocer contenido idéntico aunque el merge de promoción tenga otro SHA. No representa por sí solo evidencia de funcionamiento en dev.

El job y el pipeline exponen:

| Output | Contenido |
| --- | --- |
| `image` | Nombre del paquete |
| `digest` | Digest completo de la imagen o índice publicado |
| `image-ref` | `image@digest`, referencia exacta para el despliegue |
| `source-sha` | Commit construido |
| `source-tree` | Identificador Git del contenido construido |

Si no se solicita publicación, los outputs de publicación quedan vacíos. El resumen de Actions muestra estas referencias y las plataformas. Las labels permanecen en el registro junto con la imagen; no depender de artefactos temporales de Actions para reconstruir su origen.

Buildx usa caché de capas `type=gha` con API v2 y scope por servicio/plataformas. Esta caché no conserva automáticamente el contenido de los mounts `/root/.gradle` de los Dockerfiles entre runners. El Dockerfile sigue ejecutando `bootJar`; las verificaciones ya se ejecutaron en CI sobre el mismo commit.

Después de la primera publicación, comprobar que el paquete está vinculado al repositorio correcto y que el acceso de Actions funciona. GHCR crea inicialmente paquetes privados. La decisión del equipo es hacerlos públicos como los repos del TP; Thiago debe confirmar/configurar esa visibilidad. Una imagen pública permite pull sin credenciales de GHCR.

Para descargar e inspeccionar una publicación, reemplazar el digest por el mostrado en Actions:

```bash
docker pull ghcr.io/jjt-ingsis/snippets-service@sha256:<digest>
docker image inspect ghcr.io/jjt-ingsis/snippets-service@sha256:<digest> --format '{{json .Config.Labels}}'
```

## Branches y ambientes

Los tres servicios e infra usan `feature → dev → main`, con `dev` como default branch para que las PRs apunten inicialmente a la integración. Crear `dev` desde `main` actualizado; las ramas cortas por cambio nacen desde `dev` y vuelven mediante PR. Usar squash para feature → dev y merge commit para dev → main. Las promociones eligen `main` explícitamente. Si hay un cambio exclusivo en `main`, sincronizarlo a `dev` mediante una PR.

Proteger ambas ramas con PR, CI requerido, actualización con la base antes del merge y sin pushes directos habituales. Mantener deshabilitada la aprobación humana obligatoria. Hacer existir/pasar un check nuevo antes de exigirlo. No exigir el job de publicación como check de PR: en una PR se omite correctamente.

`github-workflows` y `gradle-conventions` mantienen `main` y versiones propias: sus branches no representan ambientes.

Crear GitHub Environments `dev` y `prod` en los tres servicios y en infra, con selected deployment branches: `dev` admite solo `dev`; `prod` admite solo `main`. No configurar revisores obligatorios. La publicación no necesita un environment ni SSH.

Configuración aplicada en GitHub durante SNI-23:

| Repositorios | Branches | Protecciones | Environments |
| --- | --- | --- | --- |
| Los tres servicios | `dev` creada desde `main`; default `dev` | PR y `verify / verify / build` requerido con rama actualizada en ambas; sin review obligatoria | `dev` solo desde `dev`; `prod` solo desde `main` |
| `snippet-searcher-infra` | `dev` creada desde `main`; default `dev` | PR en ambas; CI requerido y actualización pendientes de la primera ejecución verde del nuevo check | Mismas restricciones |

En infra, después de comprobar la primera ejecución, agregar `Validate infrastructure` como check requerido y activar la actualización con la rama base en las dos reglas. Los environments todavía no tienen datos de SSH; se cargan en SNI-25. Los workflows están integrados y publicados como `v0.3.1`; CI y publicación por push a dev pasaron en los tres consumidores. Quedan pendientes las verificaciones manuales y de arranque por digest.

Contrato para SNI-25, aún sin valores reales:

| Configuración del environment | Nombre |
| --- | --- |
| Variables | `SSH_HOST`, `SSH_USER`, `SSH_PORT` |
| Secrets | `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS` |

Thiago entrega los hosts, usuarios, puertos y claves públicas de host de las VMs. SNI-25 carga/verifica esos valores y decide las credenciales de lectura de GHCR si las imágenes siguen privadas. El job de despliegue resolverá su environment; pasar secrets por `workflow_call` no copia automáticamente los secrets de un environment.

El futuro recorrido de `cd.yml` será publicar → desplegar en dev, y seleccionar imagen comprobada en dev → desplegar en prod. El job de prod debe funcionar sin publicar ni reconstruir; las dependencias entre jobs deben contemplarlo. Cada despliegue actualiza solo la aplicación objetivo. SNI-24 crea el stack; SNI-25 verifica funcionamiento y registra el digest validado antes de promoverlo.

## Integración y versionado de SNI-23

El commit `73cc46862500f0cd19736f047d834ea7738d6021` pasó CI y publicación desde los tres servicios cuando los callers lo referenciaban por SHA. `v0.3.0` es un tag anotado al mismo commit, pero las ejecuciones por ese tag fallaron al resolver los workflows anidados. El error muestra `47bf4ee23975a7379767e73757a1e4ca72845af3`, el objeto del tag, en lugar del commit. Este comportamiento coincide con el [reporte de tags anotados y workflows anidados](https://github.com/orgs/community/discussions/206746).

Se publicó `v0.3.1` como tag liviano al mismo commit. Los tres consumidores pasaron CI y publicación con esa referencia. No cambia el código de CI/CD. Conservar `v0.3.0` y `v0.2.0`; no sobrescribir tags publicados. El resultado por SHA no sustituye la prueba por el tag final.

Orden de integración:

1. Subir la branch central `feat/sni-23-image-publication`. Obtener su SHA con `git rev-parse HEAD` después del commit.
2. Verificar las ramas `dev` ya creadas en GitHub desde `main` en los tres servicios e infra; traerlas con `git fetch origin` en otros clones.
3. Para futuros cambios, validar el candidato por SHA, conservando su rama hasta cerrar la prueba. Si se integra con squash, el commit integrado tiene otro SHA: comprobar su contenido y probar esa referencia antes de versionar.
4. Para esta corrección, crear un tag liviano al commit ya probado. Deshabilitar explícitamente la firma automática para que una configuración local no convierta el tag en anotado:

   ```bash
   git -c tag.gpgSign=false tag v0.3.1 73cc46862500f0cd19736f047d834ea7738d6021
   git cat-file -t v0.3.1
   git rev-parse 'v0.3.1^{commit}'
   git push origin v0.3.1
   ```

   Antes del push, `cat-file` debe devolver `commit` y `rev-parse` el SHA indicado. No usar `git tag -a`, `-s` ni `-m` para estas versiones de workflows. En el remoto, el objeto de `refs/tags/v0.3.1` también debe ser de tipo `commit` y tener ese SHA.

5. Abrir primero la PR de Snippets hacia `dev` con `@v0.3.1`. Comprobar CI en la PR y CI/publicación después del merge. Solo después de esa prueba, integrar los callers de Permissions y PrintScript y comprobar sus publicaciones. Si la prueba falla, investigar la anotación antes de extender el cambio; no presentar el tag como validado solo porque existe.
6. Integrar CI de infra, exigir su nuevo check una vez comprobado y promover las configuraciones de `dev` a `main` mediante PR. Verificar las rules y environments ya creadas.
7. La ejecución manual requiere que el caller con `workflow_dispatch` exista en la default branch, actualmente `dev` en los servicios e infra. Desde Actions → Pipeline → Run workflow, seleccionar `dev` o `main` y activar `publish` solo para bootstrap. Siempre ejecuta CI primero.

Los tags publicados son referencias estables y no se sobrescriben. El versionado de este repo es independiente de `gradle-conventions`; no necesita coincidir con su versión Maven.

## Comprobaciones para cerrar SNI-23

- CI pasa en PRs a dev/main y pushes a ambas; en infra se valida Compose y se prueban sus scripts existentes sin levantar aplicaciones.
- Una PR o CI fallido/cancelado no publica; un push válido a dev publica únicamente el servicio caller.
- Los tres paquetes tienen vinculación, visibilidad y arquitectura comprobadas; las imágenes se descargan por digest y arrancan con configuración externa.
- Los outputs, tags, labels y resumen corresponden al commit construido. Conservar el digest concreto para SNI-24.
- Ambas branches están protegidas con checks existentes y hay environments con las restricciones documentadas.
- El bootstrap manual funciona desde dev/main después de CI.

Las verificaciones locales de Gradle/Docker las ejecuta cada integrante. SNI-23 no configura VMs, Swarm, stack ni despliegue SSH. Si este repo se vuelve privado, habilitar en Actions el acceso de los consumidores.
