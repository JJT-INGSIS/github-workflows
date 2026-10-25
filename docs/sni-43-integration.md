# SNI-43 — Integración del CD con inventario ampliado

## Alcance

Rama local `feat/sni-43-expanded-stack-cd`. Versión propuesta v0.6.0, no publicada.
Infra integrada por PR #19, revisión `27e060dee43b92896d6b57ee3ed0d17bed8e92a4`,
con CI completo aprobado. La publicación central espera validación del candidato.
El YAML mantiene `publish`, `select`, `deploy`; CI Kotlin y `Resultado requerido`
no cambian. Scripts, selección de evidencia, SSH, actualización independiente,
lock, reconciliación y recuperación siguen en infra. No hay un cuarto job ni un
segundo orquestador. Main conserva promoción del digest verificado, sin rebuild.

Inventario, registro, controles de migración y recuperación se definen en la
[guía operativa de infra](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-43-cd.md).

## Contrato

`cd.yml` conserva inputs `image-name`, `platforms`, `publish`, `deploy` y su output
interno de artefacto. La lista de repositorios/paquetes/servicios autorizados se
resuelve en los scripts revisados, nunca mediante un servicio arbitrario del caller.

Las credenciales `GH_PACKAGES_USER`/`GH_PACKAGES_READ_TOKEN` pasan a ser opcionales
**sólo en cd.yml**, para permitir un futuro build de UI sin dependencias Maven.
El wrapper Kotlin y kotlin-ci.yml siguen exigiéndolas. La publicación GHCR sigue
usando github.token; no se envían credenciales de build a las VMs. SNI-42 debe
implementar Dockerfile, runtime config y caller propio dependiente de frontend-ci.yml.
Ese CI reutiliza los checks previos de UI, incluido Cypress, y comprueba la imagen
en PR. La evidencia requiere su job Frontend CI realmente exitoso en el intento
original y frontend-ci.yml/cd.yml de la misma revisión. CI fallido/omitido no cuenta.

v0.5.1 y v0.6.0 pueden coexistir sólo sobre el stack anterior. Actualizar todos los
callers/manuales antes del corte; el registro nuevo bloquea herramientas antiguas.

## Integración ordenada

1. Revisar e integrar `feat/sni-43-expanded-stack` de infra a dev. Obtener el SHA
   definitivo integrado; no usar el SHA previo de la rama si el merge lo cambia.
2. Fijar cd.yml al SHA integrado de 40 caracteres. Esta revisión usa el SHA de
   PR #19 indicado arriba; los callers no eligen la revisión de scripts.
3. Ejecutar Actionlint y pruebas de contrato de infra. Probar el candidato central
   por SHA desde Snippets mientras el stack sigue sin ampliar, conservando esa
   revisión accesible hasta terminar la prueba.
4. Integrar central y publicar tag **liviano** v0.6.0 al commit final validado.
   Comprobar tipo y resolución local/remota. No mover ni sobrescribir tags previos.
5. Integrar callers `ci/sni-43-workflows-v0.6.0` gradualmente a dev. Confirmar CI/CD
   sobre el stack anterior; promover también el caller a main por PR antes del
   corte de prod. No desactivar protección de main ni cambiar checks a ciegas.
6. Seguir el corte por ambiente de la guía de infra: plugin Compose, herramientas
   manuales actualizadas, drenaje/reconciliación y candidato desde el registro real.
   La aceptación remota integrada se registra en SNI-44.

Una VM apagada sigue produciendo un fallo claro; este ticket no automatiza Azure.
No reejecutar runs históricos como procedimiento de recuperación: después del
corte sus scripts quedan bloqueados por el formato de registro nuevo.

## Verificación y límites

```bash
python3 -B scripts/lint_workflows.py
```

La guía de infra contiene las pruebas Linux, renders y aceptación local NGINX/Asset;
no sustituyen el recorrido remoto. El candidato central y el caller UI se prueban
por SHA antes de versionar. Las pruebas de Actions/VMs deben registrarse aparte.
