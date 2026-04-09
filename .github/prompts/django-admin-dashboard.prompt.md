---
name: Django Admin Dashboard Aura
description: "Diseñar dashboards en Django Admin para aura-auth-service con metricas de negocio, acceso y uso del chatbot IA"
argument-hint: "Describe objetivo, audiencia, metrica principal y si quieres MVP o version completa"
agent: agent
---
Crea una propuesta de dashboard para Django Admin enfocada en este monorepo, priorizando `aura-auth-service`.

Contexto del producto:
- Plataforma con chatbot IA consultado por usuarios.
- El panel de administracion debe ayudar a monitorear uso, acceso, calidad operativa y riesgo.
- Evita sugerencias genericas: aterriza en los modelos y apps reales del workspace.

Tu tarea (una sola salida integral):
1. Descubrir en el codigo de `aura-auth-service` los modelos y fuentes de datos relevantes para dashboard (usuarios, RBAC, documentos, notificaciones, auditoria).
2. Proponer un dashboard MVP dentro de Django Admin sin romper el admin actual.
3. Definir una ruta de evolucion por fases (MVP -> Operacion -> Inteligencia).
4. Evaluar opciones externas de dashboards Django solo como referencia, con recomendacion clara de adoptar o no adoptar.

Criterios de diseno:
- Mantener compatibilidad con la estructura modular del admin existente.
- Priorizar implementacion incremental y bajo riesgo de regresion.
- Incluir control de permisos por rol para cada bloque del dashboard.
- Incluir consultas eficientes (agregaciones, select_related/prefetch_related, cache cuando aplique).
- Explicar trade-offs entre: dashboard nativo en Django Admin vs plantilla externa completa.

Formato de salida obligatorio:
## 1) Dashboard MVP (2-4 semanas)
- Widgets/KPIs con formula exacta
- Graficos y tablas recomendadas
- Filtros requeridos
- Acciones admin utiles

## 2) Modelo de datos y consultas
- Modelos involucrados
- Campos/indices sugeridos
- Estrategia ORM/SQL para rendimiento

## 3) Plan tecnico de implementacion
- Archivos a crear o editar (rutas concretas)
- Orden de ejecucion por PRs pequenos
- Riesgos y mitigaciones

## 4) Seguridad y gobierno
- Quien ve que (super-admin vs admin)
- Auditoria y trazabilidad
- Manejo de datos sensibles

## 5) Evaluacion de opciones externas
- Compara brevemente con opciones tipo Django Rocket/AdminLTE/Datta/Soft UI/Berry
- Recomendacion final para ESTE proyecto y por que

## 6) Backlog accionable
- Lista priorizada de tareas tecnicas
- Criterios de aceptacion por tarea
- Estimacion rapida (S/M/L)

Si falta informacion critica, declara supuestos explicitos antes de proponer cambios.
