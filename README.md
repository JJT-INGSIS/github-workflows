# GitHub workflows

Workflows reutilizables para Snippet Searcher. Los consumidores de esta implementación utilizan **v0.2.0**; publicar esta versión antes de incorporar sus cambios en los servicios o infra.

| Workflow | Responsabilidad |
| --- | --- |
| `kotlin-service-pipeline.yml` | Coordina CI, publicación y tags según el evento del servicio |
| `kotlin-ci.yml` | Ejecuta `./gradlew build --no-daemon` con JDK 21 |
| `publish-service.yml` | Publica en GHCR por commit y notifica al repo de infra |
| `tag-service.yml` | Agrega una versión a la imagen existente, sin rebuild |
| `swarm-deploy.yml` | Conecta por SSH verificado al manager del Environment y ejecuta los scripts de infra |

## Flujo

- Pull request: sólo CI.
- Push a main: CI → imagen `sha-<commit>` → notificación a dev con su digest.
- Push de tag Git `vX.Y.Z`: CI → alias de la imagen publicada para ese commit. No despliega prod.
- Infra invoca CD para updates automáticos de dev y releases completos manuales de dev/prod.

Las llamadas internas conservan `$/`: [GitHub documenta esta referencia al propio repositorio](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), incluso cuando un workflow es llamado desde otro repo. actionlint 1.7.12 todavía no la reconoce; la validación ignora únicamente ese diagnóstico y conserva el resto de las comprobaciones.

## Contrato de publicación

Secretos: `GH_PACKAGES_USER`, `GH_PACKAGES_READ_TOKEN`; opcional `INFRA_DISPATCH_TOKEN`. Este último notifica `service-published` a `JJT-INGSIS/snippet-searcher-infra` mediante `repository_dispatch` con `{service, digest}`. Sin el token se publica pero no se dispara CD, permitiendo el bootstrap manual.

El caller debe habilitar `contents:read` y `packages:write`. Las credenciales de Gradle se pasan como secretos de BuildKit, no como variables del contenedor final. GHCR usa `GITHUB_TOKEN`. La imagen de un commit ya publicado no se reconstruye en un reintento. Para versiones, una imagen ausente o un tag existente con otro digest falla explícitamente.

## Contrato de CD

Inputs: `environment` (`dev|prod`), `mode` (`full|update`), `service` y `digest` para updates; `snippets_version`, `permissions_version`, `printscript_version` para releases completos.

El caller es infra y debe contener `swarm/stack.yaml` y los scripts de administración. El checkout obtiene el repo caller. Los secretos SSH y de lectura de GHCR pertenecen al **Environment del repo infra** que el job selecciona, no al repo compartido. SSH exige identidad de host conocida; el registry login se guarda temporalmente y se transmite a Swarm con `--with-registry-auth`.

Infra mantiene la selección y validación de versiones, el bloqueo por ambiente, los checks y el registro del release. Ver la [guía de puesta en marcha](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/main/docs/swarm-deployment.md) para VMs y secretos.

## Validación y publicación de la versión compartida

```bash
python3 -m pip install PyYAML==6.0.2
python3 -B -m unittest discover -s tests -v
```

Validate workflows ejecuta actionlint y las pruebas contra un registry simulado. La prueba de release comprueba digest idéntico, falta de publicación, inmutabilidad del tag e idempotencia; no publica imágenes reales.

Orden de incorporación: publicar estos cambios y su tag **v0.2.0**, luego los consumidores de servicios, luego infra. Habilitar acceso a los workflows privados desde los cuatro repos consumidores. No mover tags de versiones ya publicados.
