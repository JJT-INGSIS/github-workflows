# GitHub workflows

Workflows reutilizables para los servicios de Snippet Searcher:

- `kotlin-service-pipeline.yml`: punto de entrada compartido. Por ahora solo llama a CI.
- `kotlin-ci.yml`: ejecuta `./gradlew build --no-daemon` en Ubuntu 24.04 con JDK 21.

Cada servicio conserva sus propios triggers en `.github/workflows/pipeline.yml` e invoca el pipeline central versionado. Una vez validados los workflows se publicará `v1.0.0` y se mantendrá `v1` como referencia estable de la línea 1.x.

Los repositorios de los servicios necesitan dos secrets para resolver el plugin de convención publicado en GitHub Packages:

- `GH_PACKAGES_USER`: usuario dueño del token.
- `GH_PACKAGES_READ_TOKEN`: token con acceso de lectura al paquete de `gradle-conventions`.

Si este repositorio es privado, habilitar en sus ajustes de Actions el acceso desde los tres repositorios consumidores.
