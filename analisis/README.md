# Análisis de Seguridad — aura-auth-service

## Resumen de Prioridades

| Prioridad | Item   | Descripción                                                 |
|-----------|--------|-------------------------------------------------------------|
| P0        | SEC-4  | DEBUG=True por defecto — crítico en producción              |
| P0        | SEC-1  | Sin rate limiting + lockout fields nunca escritos           |
| P0        | SEC-3  | Secretos con defaults inseguros conocidos                   |
| P1        | SEC-2  | JWT firmado con la misma key que Django sessions            |
| P1        | SEC-6  | Race condition en token rotation                            |
| P1        | SEC-5  | MAC client con X-User-Permissions: '*'                      |
| P1        | ARCH-2 | Falla silenciosa en save de clearance MAC                   |
| P1        | CODE-7 | Cero tests en el servicio de autenticación                  |
| P2        | ARCH-1 | DB query en cada /auth/validate — no escalable              |
| P2        | ARCH-3 | SQL directo sobre tablas del MAC service                    |
| P2        | SEC-8  | Refresh token sin IP/user-agent — robo indetectable         |
| P2        | SEC-9  | JWT sin iat — tokens pre-password-change válidos            |
| P3        | CODE-3 | Dependencias sin version pin                                |
| P3        | OPS-1  | Sin health check endpoint                                   |
| P3        | ARCH-4 | CustomGroup dead code                                       |

## Niveles de Prioridad

- **P0 — Crítico:** Debe resolverse antes de cualquier despliegue en producción.
- **P1 — Alto:** Introduce riesgo de seguridad o inestabilidad significativa; resolver en el corto plazo.
- **P2 — Medio:** Afecta escalabilidad o seguridad secundaria; resolver antes de carga real.
- **P3 — Bajo:** Deuda técnica y buenas prácticas; resolver en mantenimiento continuo.
