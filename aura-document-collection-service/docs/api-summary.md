# Visión general: qué hace la API y cómo encajan los datos

Este documento es una **lectura humana** del servicio: propósito, piezas principales del modelo de datos y flujos habituales. Para rutas HTTP exactas usa [endpoints.md](endpoints.md); para errores [errors-and-status-codes.md](errors-and-status-codes.md); para autenticación y permisos [permissions.md](permissions.md).

---

## 1. Propósito del servicio en el conjunto Aura

Este microservicio responde a una sola familia de preguntas, centralizada:

**¿Qué colecciones de documentos existen, bajo qué reglas de acceso obligatorio (*MAC*: Mandatory Access Control), y qué documentos están asociados a cada una? ¿Qué usuarios pueden verlas según su “techo” de clasificación y sus compartimentos?**

No sustituye al servicio donde se **suben o almacenan** ficheros físicos ni al gestor principal de usuarios identidad/JWT; aquí vive **el catálogo de clasificación/compartimento**, las **colecciones** que combinan esas reglas, los **enlaces** a filas de documento ya existentes, y el **perfil MAC por usuario** (clearance + compartimentos). Otros servicios consultan, por ejemplo, **`GET .../user-authorizations/{id}/accessible-collections/`** para saber con qué colecciones puede trabajar un usuario sin reimplementar la lógica de intersección.

---

## 2. MAC en lenguaje simple (sin jerga innecesaria)

- **Nivel de clasificación** (`classification_level`): es un peldaño de sensibilidad con un **nombre** y un **rank** numérico. Cuanto más “alto” el rank en el uso del producto, más restrictivo o dominante es ese nivel (el servicio compara ranks al decidir qué colecciones son alcanzables).
- **Compartimento** (`compartment`): es un eje de **necesidad de saber** (por programa, unidad, proyecto, etc.). Una colección puede exigir **varios** compartimentos a la vez. En la lógica actual de **colecciones accesibles**, el usuario debe estar dado de alta en **todos** los compartimentos que esa colección tenga asociados (intersección completa, no basta con uno solo).
- **Colección de documentos** (`document_collection`): agrupa trabajo bajo una **combinación obligatoria** de nivel + compartimentos. Tiene nombre, Auditoría típica y **borrado lógico**: no “desaparece” borrando el historial abruptamente.

En conjunto: *“Este bloque documental está etiquetado con este nivel y estos cofres”* más *“Este usuario sólo llega hasta este nivel y sólo tiene llave para estos cofres”* ⇒ se deriva quién puede listar tales colecciones.

---

## 3. ¿Quién hace qué? (roles de negocio, no tablas Django)

Aquí hablamos de **roles de producto**. En la práctica son cuentas o servicios con **permisos** concretos (strings como `CREATE_DOCUMENT_COLLECTION`); la lista completa está en [permissions.md](permissions.md).

| Rol conceptual | Ejemplos de acciones |
|----------------|---------------------|
| **Administrador del catálogo MAC** | Definir o ajustar **niveles de clasificación** y **compartimentos** (`classification-levels`, `compartments`). Suele hacerse pocas veces y con mucho cuidado. |
| **Administrador de colecciones** | Crear colecciones, asignarles nivel y lista de compartimentos **no vacía**, actualizarlas o darlas de baja (borrado lógico). Enlazar o desenlazar **documentos** a una colección. |
| **Administrador de autorizaciones sobre usuarios** | Asignar a un usuario un **clearance** (un solo nivel efectivo máximo por usuario en el modelo actual) y **dar o quitar** pertenencias a compartimentos (`user-authorizations/...`). |
| **Usuario / aplicación lectora** | En muchos casos no llama directamente a todo; un **otro microservicio** usa el token o el contexto del usuario y pregunta qué colecciones son accesibles o lista documentos dentro de una colección si ya tiene permiso. |
| **Integración entre servicios** | Consultar el resumen MAC de un usuario o las **colecciones accesibles** para enrutar trabajo o filtrar búsquedas en otros dominios. |

No hay “mesa de admins” dentro de esta API más allá del permiso: el mismo endpoint sirve si el llamador tiene el permiso adecuado.

---

## 4. Tablas (o equivalentes) y para qué existen

Todo es **gestionado desde Django pero `managed = False`** en los modelos: el esquema real lo define vuestra migración o base fuera del ORM habitual. Los nombres siguen la intención de negocio.

| Concepto | Tabla / idea | Propósito |
|----------|----------------|-----------|
| Nivel MAC | `classification_level` | Catálogo de etiquetas + `rank`. Los usuarios tienen clearance apuntando a **uno** de estos. |
| Cofres / compartimentos | `compartment` | Catálogo orthogonal al nivel (`name`, `description`). Colecciones y usuarios enlazan aquí vía pivotes o tablas puente. |
| Colección | `document_collection` | Grupo lógico con FK a `classification_level` y relación M:N con compartimentos. |
| Puente colección–compartimento | `document_collection_compartment` | Tabla intermedia: qué compartimentos exige cada colección. |
| Registro de documento | `document` | Metadatos mínimos del documento en este servicio (`name`, posible `deleted_at`). **No** es el almacenamiento del binario. |
| Enlace documento ↔ colección | `document_in_document_collection` | “Este `document_id` forma parte de esta colección”, con auditoría y borrado lógico acorde al resto del diseño. |
| Clearance de usuario | `user_clearance` | A qué **nivel** está acotado el usuario (un registro por usuario en la práctica del servicio). |
| Compartimentos del usuario | `user_compartment` | En qué compartimentos está dado de alta el usuario (N filas). |

Orden mental: **catálogos** (nivel, compartimento) → **colección** (elige nivel + varios compartimentos) → **documentos** enlazados → **perfil de usuario** (clearance + compartimentos) → **consulta de accesibles**.

---

## 5. Flujos típicos (de punta a punta)

### 5.1 Puesta en marcha del catálogo

1. Crear **niveles de clasificación** con `rank` coherentes (lo define el negocio legal/operativo).
2. Crear **compartimentos** que reflejen programas, unidades o franjas de necesidad de saber.

### 5.2 Un administrador crea una colección

1. Elige **nombre**, **classification_level_id** y una lista **no vacía** de **compartment_ids**.
2. El sistema valida que existan esos FKs y persiste la colección y las filas en `document_collection_compartment`.

### 5.3 Asociar documentos a la colección

1. En el dominio global ya existe un **documento** (fila en `document`) con `id` y `name` (el API expone un `title` derivado del nombre en las respuestas de enlace).
2. Con el permiso adecuado se hace **POST** al endpoint anidado `.../document-collections/{id}/documents/` con `document_id`.
3. Si el mismo documento ya está enlazado, la API responde conflicto (`duplicate_document_link`).

### 5.4 Perfil MAC de un usuario

1. Asignar **clearance**: `PUT .../user-authorizations/{user_id}/clearance/` con `classification_level_id`.
2. Asignar **compartimentos**: `POST .../user-authorizations/{user_id}/compartments/` con `compartment_id` (puede haber varios).
3. El **GET** `.../user-authorizations/{user_id}/` devuelve un **snapshot**: clearance (o nulo) + lista de compartimentos.

### 5.5 “¿A qué colecciones puede acceder este usuario?”

Llamada clave para otros servicios: **`GET .../user-authorizations/{user_id}/accessible-collections/`**.

Regla resumida en código (`list_accessible`): si el usuario **no tiene clearance**, o **no tiene ningún compartimento**, la lista es vacía. En caso contrario, una colección es accesible solo si (1) el **`rank`** de su nivel es **≤** el `rank` del nivel de clearance del usuario y (2) el usuario tiene asignación en **todos** los compartimentos que esa colección declara (no basta con cubrir un subconjunto). Otros servicios pueden apoyarse en este endpoint para no duplicar la lógica.

### 5.6 Usuario o front “ve documentos de una colección”

Típicamente: primero se sabe (por el flujo anterior o por permisos de negocio) que el usuario puede operar sobre esa colección; luego se lista **`.../document-collections/{id}/documents/`** para ver los enlaces y el snippet `id` + `title` de cada documento.

---

## 6. Qué **no** centraliza este servicio

- **Almacenamiento de archivos** o descarga de binarios.
- **Emisión de JWT** o sustitución del **servicio de autenticación** (`AUTHENTICATION_SERVICE_URL` valida el Bearer).
- **Listado global de todos los usuarios** del tenant: los endpoints de autorización operan sobre un **`user_id` concreto** en la ruta.

---

## 7. Lecturas recomendadas en este mismo directorio

| Documento | Para qué sirve |
|-----------|----------------|
| [api-overview.md](api-overview.md) | Prefijos, paginación, OpenAPI, health, CORS. |
| [endpoints.md](endpoints.md) | Mapa de rutas y cuerpos de petición. |
| [permissions.md](permissions.md) | Bearer, cabeceras internas si las usáis, y matriz permiso ↔ operación. |
| [errors-and-status-codes.md](errors-and-status-codes.md) | Códigos `error` y HTTP. |

Con esto deberías poder explicar en una reunión **qué problema resuelve** el servicio, **qué tablas representan** y **en qué orden** suelen tocarse las piezas sin abrir el código línea a línea.
