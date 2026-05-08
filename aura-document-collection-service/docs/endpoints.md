# Endpoints — Aura Document Collection Service

La API vive principalmente bajo **`/api/v1/`**. Salvo rutas públicas muy concretas, cada llamada llega después del middleware de autenticación: si tus credenciales están en orden, aquí encontrás el mapa para armar filtros (`query params`), orden (`ordering`) y cuerpos JSON sin sorpresas.

---

## Salud — el pulso del servicio

Ideal para probes de Kubernetes, uptime checks o ese “¿sigue vivo?” rápido antes de un deploy. No cuenta para rate limits agresivos de negocio; tampoco pide token.

| Método | Ruta               | Permisos | Descripción |
|--------|--------------------|----------|-------------|
| `GET`  | `/api/v1/health`   | Ninguno | Devuelve `{"status": "ok"}` cuando el proceso responde. Simple, efectivo. |

---

## Document collections — el corazón del agrupador

Aquí definís **grupos lógicos** de documentos con un nivel de clasificación MAC y uno o más compartimentos. Pensalo como la “carpeta con etiquetas de seguridad”: el nombre es tuyo, las reglas vienen del nivel y los compartimentos.

Prefijo base: **`/api/v1/document-collections/`**

| Método   | Ruta                                              | Permiso | Descripción |
|----------|---------------------------------------------------|---------|-------------|
| `GET`    | `/api/v1/document-collections/`                   | `LIST_DOCUMENT_COLLECTIONS` | Volcá todas las colecciones visibles para tu cuenta (paginado). Perfecto para UIs tipo explorer o dashboards. |
| `POST`   | `/api/v1/document-collections/`                 | `CREATE_DOCUMENT_COLLECTION` | Armá una colección nueva: nombre, nivel y al menos un compartimento obligatorio desde el día uno. |
| `GET`    | `/api/v1/document-collections/{id}/`            | `GET_DOCUMENT_COLLECTION` | Traé el JSON completo con nivel y compartimentos anidados. El `{id}` es entero positivo. |
| `PATCH`  | `/api/v1/document-collections/{id}/`            | `UPDATE_DOCUMENT_COLLECTION` | Actualización quirúrgica: solo cambiás lo que mandás en el body. No hay `PUT` de reemplazo total en este viewset — el parche es la filosofía acá. |
| `DELETE` | `/api/v1/document-collections/{id}/`            | `DELETE_DOCUMENT_COLLECTION` | Baja la colección con **soft delete** en persistencia (no revienta el histórico de un golpe). |

**Ordenamiento** (`ordering`): podés ordenar por `id`, `name`, `created_at`, `updated_at`. Por defecto verás las más recientes primero (`-created_at`).

**Filtros — recortá el mundo sin hacer malabares en el cliente:**

| Query param      | Para qué sirve |
|------------------|----------------|
| `name`           | Búsqueda relajada: coincidente por substring en el nombre (case-insensitive). |
| `created_by`     | Filá por quién creó la colección (ID numérico). |
| `created_after`  | Solo colecciones creadas desde este instante ISO hacia adelante. |
| `created_before` | El reverso: techo temporal en ISO. |

**Cuerpo `POST`** (`CreateDocumentCollectionRequest`):

- `name`: cómo querés llamarla; obligatorio; tras trim debe quedar dentro de 255 caracteres y no puede ser solo espacios.
- `classification_level_id`: qué nivel MAC le aplica (entero ≥ 1).
- `compartment_ids`: lista de IDs de compartimento (cada uno ≥ 1); **tiene que traer al menos uno** — una colección “sin cofre” no se admite en la creación.

**Cuerpo `PATCH`** (`PatchDocumentCollectionRequest`): mandá **al menos uno** de:

- `name`
- `classification_level_id`
- `compartment_ids` (si lo tocás, otra vez lista **no vacía**)

Si el body llega `{}`, el serializer lo rechaza con un “tenés que decirme qué cambiar” implícito.

**Respuesta** (forma útil mental): `id`, `name`, objeto `classification_level`, array `compartments`, `created_by`, marcas `created_at` / `updated_at`.

---

## Documentos dentro de una colección — rutas anidadas

Este bloque es el **puente** entre “la colección” y “los documentos reales”: no sube blobs acá (eso vive en otro servicio), sí registra **qué documento** está enlazado y con qué metadatos mínimos se expone.

Prefijo padre: **`/api/v1/document-collections/{document_collection_id}/documents/`**

| Método   | Ruta | Permiso | Descripción |
|----------|------|---------|-------------|
| `GET`    | `.../documents/` | `LIST_DOCUMENT_COLLECTION_DOCUMENTS` | Inventario paginado de membresías: quién enlazó, cuándo, y una miniatura del documento (`id` + título visible). |
| `POST`   | `.../documents/` | `ADD_DOCUMENT_COLLECTION_DOCUMENT` | “Meté este documento en la colección.” Si ya estaba, preparate para un 409 elegante (`duplicate_document_link`). |
| `DELETE` | `.../documents/{id}/` | `REMOVE_DOCUMENT_COLLECTION_DOCUMENT` | Cortá el vínculo por el **id del enlace**, no por el document_id del mundo exterior — evitá borrar la colección entera por error. |

**Ordenamiento**: `id`, `created_at`, `document_id`. Default tranquilo por `id`.

**Filtros — encontrá la aguja:**

| Query param     | Para qué sirve |
|-----------------|----------------|
| `document_id`   | Poné el ID exacto del documento y olvidate del resto. |
| `document_name` | Búsqueda parcial sobre el nombre almacenado del documento (se expone al cliente como `title` en la respuesta). |

**Cuerpo `POST`**: solo `document_id` (positivo y acotado al rango práctico de un entero de 63 bits positivo).

**Respuesta por ítem**: `id`, `created_by`, `created_at`, y `document: { id, title }` donde `title` refleja el nombre persistido del documento.

---

## Classification levels — el escalafón MAC

Son los **peldaños de sensibilidad**: nombre legible para humanos más un `rank` numérico que ordena políticas. Alta y baja de niveles tiene efectos en cascada (no podés borrar uno que sigue referenciado en colecciones).

Base: **`/api/v1/classification-levels/`**

| Método   | Ruta | Permiso | Descripción |
|----------|------|---------|-------------|
| `GET`    | `/api/v1/classification-levels/` | `LIST_CLASSIFICATION_LEVELS` | Catálogo completo o filtrado; idealmente ordenás por `rank` y ya tenés el “semáforo” de clasificación. |
| `POST`   | `/api/v1/classification-levels/` | `CREATE_CLASSIFICATION_LEVEL` | Agregás un nivel nuevo; ojo con duplicados de nombre/rango — ahí aparece conflicto controlado (409). |
| `GET`    | `/api/v1/classification-levels/{id}/` | `GET_CLASSIFICATION_LEVEL` | Una fila para formularios o validaciones antes de crear colecciones. |
| `PATCH`  | `/api/v1/classification-levels/{id}/` | `UPDATE_CLASSIFICATION_LEVEL` | Ajustás nombre o rank sin pisar todo el recurso con `PUT`. |
| `DELETE` | `/api/v1/classification-levels/{id}/` | `DELETE_CLASSIFICATION_LEVEL` | Eliminar nivel; si algo lo usa, la API va a frenarte con causa (no es un DELETE silencioso que rompa integridad mágica). |

**Ordenamiento**: `id`, `name`, `rank` — por defecto ascendente por **`rank`** (tiene sentido semántico para MAC).

**Filtros**: `name` (substring), `rank_gte`, `rank_lte` para recortar el espectro de sensibilidad.

**Cuerpo `POST`**: `name` (≤100, no vacío post-trim), `rank` entre 1 y 32767.

**Cuerpo `PATCH`**: al menos un campo (`name` o `rank`). Siempre mové algo si tocás PATCH.

**Respuesta**: `id`, `name`, `rank`.

---

## Compartments — cajones etiquetados

Los compartimentos son **dimensiones ortogonales al nivel**: podés tener el mismo nivel de clasificación pero compartimento distinto, y así modelar necesidad-de-saber. La descripción opcional sirve para operadores sin meter ruido en el nombre corto.

Base: **`/api/v1/compartments/`**

| Método   | Ruta | Permiso | Descripción |
|----------|------|---------|-------------|
| `GET`    | `/api/v1/compartments/` | `LIST_COMPARTMENTS` | Listado establecido ordenado por nombre por defecto — entra rápido a un `<select>` o typeahead. |
| `POST`   | `/api/v1/compartments/` | `CREATE_COMPARTMENT` | Nuevo cofre etiquetado; duplicidad de nombre se traduce en conflicto. |
| `GET`    | `/api/v1/compartments/{id}/` | `GET_COMPARTMENT` | Traé texto largo corto más descripción extendida si la cargaste. |
| `PATCH`  | `/api/v1/compartments/{id}/` | `UPDATE_COMPARTMENT` | Renombrar o ajustar descripción puntualmente. |
| `DELETE` | `/api/v1/compartments/{id}/` | `DELETE_COMPARTMENT` | Eliminar cofre si la vida del dato lo permite; si algo lo usa, la API cuenta la historia en 409. |

**Ordenamiento**: `id`, `name` (default alfabetizado por **`name`**).

**Filtros**: `name` como búsqueda parcial icontains.

**Cuerpo `POST`**: `name` (≤100, no vacío), `description` opcional (vacío está permitido — silencioso pero válido).

**Cuerpo `PATCH`**: mínimo un campo tocado (`name`, `description` o ambos).

**Respuesta**: `id`, `name`, `description`.

---

## User authorizations — quién puede ver qué

Acá configurás **el mapa MAC por persona**: clearance (qué nivel alcanza) y memberships de compartimentos. También existe el endpoint “**última respuesta ante el usuario de turno en otro microservicio**”: las colecciones accesibles con las reglas ya resueltas.

No hay **`GET`** listando todos los usuarios del mundo: las rutas cuelgan de **`/{user_id}`** — es intencional: operás sobre una identidad concreta.

| Método   | Ruta | Permiso | Descripción |
|----------|------|---------|-------------|
| `GET`    | `/api/v1/user-authorizations/{user_id}/` | `GET_USER_AUTHORIZATION` | Foto polaroid del usuario ante MAC: nivel actual (si tiene) más la lista anidada de compartimentos. |
| `PUT`    | `/api/v1/user-authorizations/{user_id}/clearance/` | `SET_USER_CLEARANCE` | Poné (o pisá) la etiqueta máxima de clasificación autorizada para ese user. Explícito, idempotente en espíritu. |
| `DELETE` | `/api/v1/user-authorizations/{user_id}/clearance/` | `DELETE_USER_CLEARANCE` | Sacá el clearance; si ya no había nada para borrar, el 404 cuenta la verdad sobre el estado esperado vs real. |
| `GET`    | `/api/v1/user-authorizations/{user_id}/compartments/` | `LIST_USER_COMPARTMENTS` | Paginás las pertenencias a cofres; viene la metadata de auditoría típica (`created_by`, `created_at`). |
| `POST`   | `/api/v1/user-authorizations/{user_id}/compartments/` | `ADD_USER_COMPARTMENT` | Sumá otro cofre sin reescribir toda la matriz manualmente — duplicado genera conflicto ordenado (409). |
| `DELETE` | `/api/v1/user-authorizations/{user_id}/compartments/{compartment_id}/` | `REMOVE_USER_COMPARTMENT` | Quitá ese compartimento puntual; el path lo deja clarísimo qué entrada basureás. |
| `GET`    | `/api/v1/user-authorizations/{user_id}/accessible-collections/` | `GET_USER_ACCESSIBLE_COLLECTIONS` | Lista las **colecciones de documentos** que este usuario puede tocar vista la suma nivel + cofres — el endpoint que otros servicios pueden cachear antes de rutear trabajo pesado de documentos. |

**`PUT .../clearance/`**: `{ "classification_level_id": ≥ 1 }`.

**`POST .../compartments/`**: `{ "compartment_id": ≥ 1 }`.

**Respuesta del resumen (`GET .../{user_id}/`)**: `user_id`, objeto `clearance` o `null`, y lista `compartments` donde cada entrada trae `compartment` resuelto.

**Colecciones accesibles**: mismo sabor JSON que **`DocumentCollectionResponse`** en colección paginada — podés reusar parsers del cliente ya armados para “colecciones”.

---

## Notas de diseño — para cerrar la vuelta

- **MAC de extremo a extremo**: `accessible-collections` es tu atajo para no reimplementar en cada servicio la combinatoria nivel + compartimento + colección.
- **Sin `PUT` nostalgia**: los CRUD grandes se actualizan con **`PATCH`**, lo que fuerza payloads pequeños y merge mental más simple.
- **IDs en URL**: tienen que ser enteros positivos; **`0`** queda fuera del club por configuración regex de los viewsets.
