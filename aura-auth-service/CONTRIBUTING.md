# Guía de Contribución

Gracias por tu interés en contribuir a Aura Auth Service. Este documento proporciona directrices para mantener la calidad y consistencia del código.

## 📋 Antes de Empezar

1. Lee la [DOCUMENTATION.md](DOCUMENTATION.md) para entender la arquitectura
2. Revisa el [CHANGELOG.md](CHANGELOG.md) para cambios recientes
3. Instala las dependencias: `pip install -r requirements.txt`

## 🏗️ Estructura del Proyecto

```
app/
├── api/               # Controllers y rutas REST
├── application/       # Servicios y excepciones
├── configuration/     # Configuración de Django
├── domain/           # Modelos y serializers
└── infrastructure/   # Repositorios
```

## 📝 Estándares de Código

### Python
- Seguir [PEP 8](https://pep8.org/)
- Usar type hints cuando sea posible
- Máximo 100 caracteres por línea
- Docstrings en todas las funciones públicas

### Ejemplo de función bien documentada:

```python
def create_user(username: str, email: str, password: str, created_by_id: int) -> AuthUser:
    """
    Crea un nuevo usuario en el sistema.
    
    Args:
        username: Nombre de usuario único
        email: Correo electrónico único
        password: Contraseña en texto plano (será hasheada)
        created_by_id: ID del usuario que crea
        
    Returns:
        AuthUser: El usuario creado
        
    Raises:
        IntegrityException: Si hay un error de integridad
        
    Example:
        >>> user = create_user('jdoe', 'john@example.com', 'Pass123!', 1)
        >>> user.username
        'jdoe'
    """
    # Implementación...
```

### Modelos Django

Siempre usar:
- `managed = False` en Meta
- Nombres descriptivos en db_column
- Docstrings en la clase
- Método `__str__` para representación

```python
class AuthUser(models.Model):
    """
    Modelo que mapea la tabla auth_user existente.
    """
    # Campos...
    
    class Meta:
        db_table = 'auth_user'
        managed = False  # ← Obligatorio
        
    def __str__(self):
        return f"{self.username} ({self.email})"
```

### Serializers

- Validación clara y explícita
- Mensajes de error en español
- Documentación en los campos

```python
class UserCreateRequestSerializer(serializers.Serializer):
    """Serializer para crear usuario."""
    
    username = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Nombre de usuario único"
    )
    
    def validate_username(self, value):
        """Validación personalizada."""
        if AuthUser.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Este nombre de usuario ya está en uso."
            )
        return value
```

### Servicios

- Una clase por entidad
- Métodos @staticmethod para operaciones simples
- Logging en operaciones importantes
- Manejo explícito de excepciones

```python
class UserService:
    """Servicio de lógica de negocio para usuarios."""
    
    @staticmethod
    def create_user(username: str, email: str, password: str, 
                   created_by_id: int) -> AuthUser:
        """Crea un nuevo usuario."""
        logger.info(f"Creando usuario: {username}")
        try:
            # Lógica...
            logger.info(f"Usuario creado: ID {user.id}")
            return user
        except Exception as e:
            logger.error(f"Error creando usuario: {str(e)}", exc_info=True)
            raise
```

### Repositorios

- Interfaz consistente para acceso a datos
- Convertir excepciones de BD a excepciones de aplicación
- Sin lógica de negocio

```python
class UserRepository:
    """Repositorio para acceso a datos de usuarios."""
    
    @staticmethod
    def create(username: str, email: str, password_hash: str,
              created_by_id: int) -> AuthUser:
        """
        Crea un usuario.
        
        Raises:
            IntegrityException: Si hay error de integridad
        """
        try:
            return AuthUser.objects.create(
                username=username,
                email=email,
                password=password_hash,
                created_by_id=created_by_id,
                # Campos con defaults...
            )
        except IntegrityError as e:
            raise IntegrityException(detail=f"Error: {str(e)}")
```

## 🧪 Testing

### Estructura de tests

```
tests/
├── unit/
│   ├── test_user_service.py
│   └── test_role_service.py
├── integration/
│   ├── test_user_repository.py
│   └── test_role_repository.py
└── e2e/
    ├── test_user_api.py
    └── test_role_api.py
```

### Escribir tests

```python
import pytest
from application.services.services import UserService
from application.exceptions.exceptions import IntegrityException

class TestUserService:
    """Tests para UserService."""
    
    def test_create_user_success(self):
        """Verifica que se puede crear un usuario."""
        user = UserService.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            created_by_id=1
        )
        
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.status == 'active'
        assert user.enabled is True
    
    def test_create_user_duplicate_username(self):
        """Verifica que no se puede crear usuario con username duplicado."""
        UserService.create_user(
            username='testuser',
            email='test1@example.com',
            password='TestPass123!',
            created_by_id=1
        )
        
        with pytest.raises(IntegrityException):
            UserService.create_user(
                username='testuser',
                email='test2@example.com',
                password='TestPass123!',
                created_by_id=1
            )
```

## 🐛 Reporting de Bugs

1. Verifica que el bug no está ya reportado en Issues
2. Crea un issue describiendo:
   - Comportamiento esperado
   - Comportamiento actual
   - Pasos para reproducir
   - Entorno (Python, Django, OS)
3. Adjunta logs relevantes

### Template de issue:

```
## Descripción del bug
[Describe qué pasó]

## Comportamiento esperado
[Qué debería pasar]

## Pasos para reproducir
1. ...
2. ...
3. ...

## Información del entorno
- Python: [versión]
- Django: [versión]
- OS: [sistema operativo]

## Logs
```

## ✨ Solicitando Features

1. Abre un issue con label `enhancement`
2. Describe:
   - Qué problema resuelve
   - Casos de uso
   - Solución propuesta
   - Alternativas consideradas

## 🔄 Pull Requests

### Antes de enviar un PR:

1. **Fork** el repositorio
2. **Crea una rama** con nombre descriptivo:
   ```bash
   git checkout -b feature/agregar-login
   git checkout -b bugfix/corregir-validacion
   ```
3. **Escribe código** siguiendo estándares de este documento
4. **Agrega tests** para nuevas funcionalidades
5. **Actualiza documentación** si es necesario
6. **Verifica que los tests pasan**:
   ```bash
   pytest tests/
   ```

### Mensaje de commit

```
[feat] Agregar soporte para JWT

- Implementar endpoint de login
- Agregar generación de tokens
- Documentar uso de JWT

Closes #123
```

**Prefijos válidos:**
- `[feat]` - Nueva funcionalidad
- `[fix]` - Corrección de bug
- `[docs]` - Cambios en documentación
- `[refactor]` - Cambios en código sin funcionalidad nueva
- `[test]` - Agregar o mejorar tests
- `[perf]` - Mejoras de rendimiento

### Descripción del PR

```markdown
## Descripción
[Qué hace este PR]

## Tipo de cambio
- [ ] Feature nueva
- [ ] Bugfix
- [ ] Cambio de documentación

## Cambios
- Cambio 1
- Cambio 2

## Cómo probar
1. ...
2. ...

## Checklist
- [ ] Código sigue estándares de este proyecto
- [ ] Tests agregados/actualizados
- [ ] Documentación actualizada
- [ ] No hay cambios que rompan compatibilidad
```

## 📖 Documentación

Mantener actualizada:
- [DOCUMENTATION.md](DOCUMENTATION.md) - Cambios en arquitectura
- [CHANGELOG.md](CHANGELOG.md) - Cambios notables
- [README.md](README.md) - Cambios públicos
- Docstrings en funciones públicas

## 🔐 Seguridad

### Nunca:
- Commitear credenciales o secrets
- Commitear `.env` (solo `.env.example`)
- Guardar contraseñas en texto plano
- Exponer errores internos en respuestas

### Siempre:
- Validar entrada del usuario
- Usar hashing para contraseñas
- Registrar operaciones sensibles
- Revisar dependencias por vulnerabilidades

```bash
# Verificar dependencias
pip check
```

## 📚 Recursos Útiles

- [Django Documentation](https://docs.djangoproject.com/)
- [DRF Documentation](https://www.django-rest-framework.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PEP 8 Style Guide](https://pep8.org/)

## ❓ Preguntas

- Revisa los issues existentes
- Crea una nueva issue con `label: question`
- Comunícate en los canales del proyecto

---

¡Gracias por contribuir a mejorar Aura Auth Service! 🚀
