# Ciclo Productivo del Cerdo

Dashboard estático (`index.html`) para llevar el ciclo de alimentación de lotes
de cerdos: registras la fecha de nacimiento y el sitio calcula automáticamente
en qué etapa está cada lote (Lactancia → Preiniciador → Iniciador →
Crecimiento → Desarrollo → Finalización → Rastro), su peso estimado y la
fecha de rastro. Los lotes se guardan en Supabase, y un flujo de GitHub
Actions recalcula todos los lotes cada mañana y registra un evento cuando
alguno cruza a una nueva etapa.

## Estructura

```
index.html                          → dashboard (estático, se sirve tal cual desde GitHub Pages)
supabase/migrations/0001_init.sql   → esquema de la base de datos
scripts/actualizar_ciclo.py         → script del cron diario
.github/workflows/actualizar-ciclo.yml → dispara el cron diario en GitHub Actions
requirements.txt                    → dependencias del script Python
```

## 1. Crear el repositorio en GitHub

Estos archivos están listos para subir, pero yo no tengo un conector de
GitHub disponible en esta conversación, así que el push lo haces tú:

```bash
cd ciclo-cerdo-repo
git init
git add .
git commit -m "Ciclo productivo del cerdo: dashboard + cron"
git branch -M main
git remote add origin https://github.com/Russali-ux/ciclo-cerdo.git
git push -u origin main
```

(Crea primero el repo vacío en github.com/new con el nombre que prefieras;
`ciclo-cerdo` es solo una sugerencia.)

## 2. Base de datos (Supabase)

Ya apliqué la migración `supabase/migrations/0001_init.sql` al proyecto
**Alessa-IPS** (`ngfooohbehmgtzlkbkoa`), que era el que elegiste. Crea dos
tablas:

- `cerdo_lotes` — un registro por lote, con la fecha de nacimiento y el
  estado calculado (etapa actual, peso estimado, fecha de rastro, etc.)
- `cerdo_lotes_eventos` — un registro cada vez que el cron detecta que un
  lote cruzó de etapa (`notified = false` hasta que algo lo procese)

Si en algún momento quieres volver a aplicar el SQL a mano (por ejemplo en
otro proyecto), el archivo está en `supabase/migrations/0001_init.sql`.

## 3. Conectar `index.html` a tu proyecto

`index.html` ya viene con la URL y la clave `anon` del proyecto Alessa-IPS
cargadas (`https://ngfooohbehmgtzlkbkoa.supabase.co`), así que no necesitas
tocar nada para empezar a usarlo. Si en el futuro migras a otro proyecto,
reemplaza estas dos líneas dentro del `<script>` con los nuevos valores
(Project Settings → API en el panel de Supabase):

```js
var SUPABASE_URL = "https://ngfooohbehmgtzlkbkoa.supabase.co";
var SUPABASE_ANON_KEY = "eyJhbGci...";
```

## 4. Publicar el sitio (GitHub Pages)

En el repo: **Settings → Pages → Source: rama `main`, carpeta `/ (root)`**.
GitHub te da una URL tipo `https://russali-ux.github.io/ciclo-cerdo/`.

## 5. Configurar el cron diario (GitHub Actions)

El workflow ya está en `.github/workflows/actualizar-ciclo.yml` y corre todos
los días a las 10:00 UTC (≈ 05:00 hora Lima). Solo falta darle credenciales:

En el repo: **Settings → Secrets and variables → Actions → New repository
secret**, y crea:

| Secret | Valor |
|---|---|
| `SUPABASE_URL` | `https://ngfooohbehmgtzlkbkoa.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | la clave `service_role` de Project Settings → API (⚠️ no la `anon`) |

El script usa la clave `service_role` porque necesita escribir en la base sin
depender de las políticas RLS pensadas para el navegador. Esa clave **nunca**
debe ir en `index.html` ni en el repositorio; solo vive como secreto de
GitHub Actions.

Puedes probarlo de inmediato sin esperar al cron: pestaña **Actions** →
"Actualizar ciclo de lotes" → **Run workflow**.

## Seguridad — léelo antes de hacer público el repo o el sitio

`index.html` es un sitio 100% estático: cualquiera que abra la página puede
ver la clave `anon` en el código fuente. Eso es normal en apps Supabase, pero
significa que la protección real depende de las políticas de RLS.

Tal como quedó configurado (`for all using (true) with check (true)`),
**cualquiera que tenga la URL del sitio puede leer, crear, editar o borrar
lotes** — no hay login. Es razonable para un panel de uso personal/interno,
pero si vas a compartir el enlace o el repo va a ser público, considera antes
alguna de estas opciones:

- Agregar autenticación de Supabase (correo/contraseña o Google, como en tus
  otros dashboards) y cambiar las políticas para exigir `auth.uid()`.
- Poner el sitio detrás de un proxy con contraseña, o mantenerlo privado
  (por ejemplo GitHub Pages con el repo en un plan que soporte Pages
  privadas, o alojarlo en Vercel con protección de contraseña).
- Como mínimo, no publicar la URL del sitio ni el repo si prefieres no
  invertir tiempo en autenticación todavía.

## Cómo se calcula el ciclo

Los valores de referencia (duración en días, peso al final de la etapa,
alimento consumido) siguen tu gráfico original:

| Etapa | Días | Peso final | Alimento |
|---|---|---|---|
| Lactancia | 0–21 | 5.5 kg | — |
| Preiniciador | 21–49 | 15 kg | 12 kg |
| Iniciador | 49–70 | 30 kg | 22 kg |
| Crecimiento | 70–98 | 50 kg | 49 kg |
| Desarrollo | 98–126 | 75 kg | 65 kg |
| Finalización | 126–154 | 100 kg | 84 kg |

Puedes ajustar estos valores por lote desde el panel "Duraciones y pesos por
etapa (avanzado)" del dashboard; quedan guardados en la columna
`stage_settings` de ese lote, y tanto el dashboard como el script del cron
los respetan.
