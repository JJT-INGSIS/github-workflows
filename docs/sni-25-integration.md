# SNI-25 — Integración y habilitación gradual

## Flujo

| Evento | Resultado |
| --- | --- |
| PR dev/main | CI completo; sin publicación ni despliegue |
| Push dev | CI → publicar una imagen → desplegar ese digest → verificar → registrar evidencia |
| Push main | CI → seleccionar evidencia dev del Git tree exacto → desplegar el mismo digest en prod |
| Manual dev | CI; publicación opcional o solicitada por CD habilitado; nunca evita la verificación |
| Manual main | CI y, con CD habilitado, reintento de promoción; solicitar publicación falla |

`kotlin-service-pipeline.yml` mantiene el check anterior y agrega `Resultado requerido`
solo para PRs. Este agregador compara `needs.verify.result` con `success`; fallo,
cancelación u omisión no cuentan como éxito. No vuelve a ejecutar Gradle.

`cd.yml` mantiene jobs separados: `publish` en dev, `select` en main y `deploy` tras
el job correspondiente exitoso. La condición de deploy contempla que el otro job
esté omitido. `main` no construye imágenes. Los outputs `image`, `digest`, `image-ref`,
`source-sha` y `source-tree` corresponden tanto a publicación como a selección.

Publicar solo es compatible con SNI-23 (`publish=true`, `deploy=false`). La evidencia
para prod requiere además CD verificado. Los paquetes anteriores, sin la etiqueta
de intento de construcción ni evidencia SNI-25, no son promoción válida por sí solos.

## Orden de integración (sin desplegar todavía)

1. Revisar e integrar primero `snippet-searcher-infra`, rama
   `feat/sni-25-service-deployment`, con tests y validación de stack verdes.
2. Infra integrada y fijada en `cd.yml` mediante `INFRA_REVISION`:
   `7f91f1cc800d9059cdfcfe005a330dccbdb4196b` (PR #12).
   Es una constante revisada, no un input de los callers ni una rama móvil;
   los scripts corren con privilegios en las VMs.
3. Revisar la rama central `feat/sni-25-swarm-cd`. Validar los workflows localmente
   y subir un candidato por SHA cuando el equipo autorice los commits/push.
4. Probar Snippets usando temporalmente **ese SHA central** y conservando la rama.
   Primero PR/CI y publicación sin despliegue; después probar environment y dev
   con la configuración siguiente. El lint local no sustituye la ejecución de Actions.
5. Integrar el central en main, comprobar el SHA definitivo y repetir su prueba
   si el merge cambió la revisión. Crear un tag **liviano** `v0.4.0` al commit
   probado; verificar local y remoto que el objeto sea `commit`. No sobrescribir tags.
6. Probar el tag final primero en Snippets; recién entonces integrar los callers
   de Permissions y PrintScript preparados con `@v0.4.0` y comprobarlos.
7. Cuando aparezca y pase el agregador nuevo, elegir su nombre completo en las
   protecciones. Conservar el check previo durante la transición.

Los cambios locales no publican esa versión. Mantener `CD_ENABLED` y
`PROD_DEPLOY_ENABLED` deshabilitados hasta completar la preparación y las pruebas
del ambiente correspondiente. Fijar infra no habilita por sí solo los despliegues.
No integrar los callers al tag inexistente antes del paso 5.

## Habilitar dev por servicio

En el repositorio **del servicio consumidor**, GitHub Environment dev admite solo
la branch dev. Cargar:

| Tipo | Valores |
| --- | --- |
| Variables del environment | `SSH_HOST`, `SSH_USER=azureuser`, `SSH_PORT=22` |
| Secrets del environment | `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS` |
| Variable de repositorio | `CD_ENABLED=true` después de preparar la VM y credenciales |

Thiago entrega las claves públicas de host verificadas y autoriza una clave
dedicada a CD. No obtener `known_hosts` de la red sin verificar su identidad.
El job final declara `environment: dev/prod`; los jobs que llaman workflows
reutilizables no lo declaran. Los secretos SSH opcionales se reenvían explícitamente
por la cadena, y los del environment se resuelven en el ejecutor final. La prueba
real debe comprobarlo sin imprimir valores. SSH exige host keys, modo no interactivo
y `sudo -n`; si faltan secretos, no actualiza Swarm.

El caller solicita despliegue solo cuando `CD_ENABLED` vale exactamente `true`.
Sin ese valor se mantiene CI/publicación en dev, sin SSH. `DOCKER_PLATFORMS` debe
incluir linux/amd64 para las dos VMs x64; el default ya lo incluye.

Permisos: `contents: read`, `actions: read`, `pull-requests: read`, `packages: write`,
`deployments: write`. Lectura de PR permite comprobar el merge que autoriza prod,
según el [contrato de la API](https://docs.github.com/en/rest/commits/commits#list-pull-requests-associated-with-a-commit).
CI reduce permisos a lectura; select consulta Actions/Deployments y deploy registra
evidencia con el token automático. Los repos de workflows e infra son públicos;
si se privatizan, preparar acceso para sus checkouts antes de habilitar CD.
Los secretos de Packages siguen siendo exclusivos de Gradle/BuildKit.

## Condición previa obligatoria para producción

**No configurar `PROD_DEPLOY_ENABLED=true` hasta verificar las reglas de main.**
La API administrativa devolvió 403. El 13/10/2026 se activó el bloqueo de bypass
de main desde GitHub y se reabrió cada regla para comprobar su persistencia:

| Servicio | PR + CI + base actualizada | Bypass de PR específico / force push | Do not allow bypassing the above settings |
| --- | --- | --- | --- |
| snippets-service | Exigidos | Deshabilitados | Activado y guardado |
| permissions-service | Exigidos | Deshabilitados | Activado y guardado |
| printscript-service | Exigidos | Deshabilitados | Activado y guardado |

Las reglas se aplican también a administradores y roles con permiso de bypass.
No se habilitó despliegue automático a producción: todavía faltan integración,
credenciales y pruebas. Conservar esta protección y volver a comprobarla si
cambian las reglas o los roles antes de habilitar prod.

Comprobar en cada servicio: PR obligatorio, CI requerido, rama actualizada,
reglas aplicadas también a administradores, sin actores con bypass de push ni
force push. No se agrega otra aprobación de environment: el merge dev → main
es la decisión humana. Confirmar también prod restringido a main y sus variables
y secretos SSH apuntando **a la VM de prod**.

Después de registrar esa comprobación, definir la variable **de repositorio**
`PROD_DEPLOY_ENABLED=true`. Select y prepare fallan si falta. Dentro del lock remoto
se comprueba main protegida, HEAD vigente, Git tree exacto y PR dev → main del
mismo repo con ese merge SHA. La marca `protected` no permite deducir las excepciones;
la revisión detallada de reglas sigue siendo obligatoria.

Sin coincidencia exacta y evidencia confiable, no se modifica prod. Modificar un
README al promover también cambia el árbol: llevar ese contenido a dev y verificarlo
antes. El digest sigue siendo la identidad del artefacto, sin reconstrucción en main.

## Diagnóstico, recuperación y cierre

El [manual operativo de infra](https://github.com/JJT-INGSIS/snippet-searcher-infra/blob/dev/docs/sni-25-cd.md)
explica journal, bloqueo compartido, recibos históricos, recuperación e intervención.
Una desconexión SSH no determina si Docker aceptó la actualización; se reconcilia
desde el estado persistido. Un rollback exitoso mantiene la Action roja. Reejecutar
los jobs fallidos conserva los outputs de publicación original, incluyendo su
run/attempt, y puede confirmar el mismo digest sin otra actualización.

El registro persistente usa Deployments `sni25:verified`, payload explícito y run
original exitoso con los workflows centrales. No depende de logs, artefactos ni
estados históricos con retención limitada. Si faltan metadata del run o imagen,
se rechaza la promoción. El modelo de confianza presupone ramas y workflows revisados;
no pretende ser una firma criptográfica del payload.

Mantener compatibles esquema de DB y contratos HTTP para las versiones coexistentes.
Rollback de imagen no revierte datos. Una VM apagada falla sin encendido automático.
CD no crea Swarm, bases, secretos, redes ni otros recursos.

Validaciones locales:

```bash
python3 scripts/lint_workflows.py
```

El wrapper usa una imagen de actionlint fijada por digest. Su versión todavía no
reconoce `$/`, soportado por GitHub y usado por los workflows actuales. Adapta ese
prefijo únicamente en una copia temporal para validar los contratos locales; no
modifica los YAML oficiales ni omite los checks de expresiones, inputs o ShellCheck.
Solo se suprime SC2016 en los formatos printf que muestran backticks literales de Markdown.

Para cerrar el ticket hace falta evidencia real: PR sin CD; dev con publicación,
deploy y checks; prod con el mismo digest; rechazo sin evidencia; rollback
controlado y corte SSH en dev; evidencia histórica con dev avanzado. Esto queda
pendiente de integración, credenciales y VMs encendidas.
