#!/usr/bin/env python
"""
Script de verificación de la estructura del proyecto.
Valida que todos los archivos necesarios existan.
"""
import os
import sys

def check_file_exists(path):
    """Verifica que un archivo existe."""
    exists = os.path.exists(path)
    status = "✓" if exists else "✗"
    print(f"  {status} {path}")
    return exists

def main():
    base_path = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_path, 'app')
    
    print("\n=== Verificación de Estructura del Proyecto ===\n")
    
    all_good = True
    
    # Verificar archivos raíz
    print("📁 Archivos raíz:")
    files_to_check = [
        'requirements.txt',
        '.env.example',
        'README.md',
        'DOCUMENTATION.md',
        'QUICKSTART.md',
        'Dockerfile',
        'init_db.py',
        'manage.py',
        'test.http',
    ]
    
    for file in files_to_check:
        path = os.path.join(base_path, file)
        if not check_file_exists(path):
            all_good = False
    
    # Verificar estructura app
    print("\n📁 Estructura de aplicación:")
    structure = [
        'app/__init__.py',
        'app/manage.py',
        
        'app/api/__init__.py',
        'app/api/apps.py',
        'app/api/urls.py',
        'app/api/controllers/__init__.py',
        'app/api/controllers/controllers.py',
        
        'app/configuration/__init__.py',
        'app/configuration/apps.py',
        'app/configuration/settings.py',
        'app/configuration/environment_variables.py',
        'app/configuration/logging_configuration.py',
        'app/configuration/exception_handler.py',
        'app/configuration/urls.py',
        'app/configuration/wsgi.py',
        
        'app/domain/__init__.py',
        'app/domain/apps.py',
        'app/domain/models/__init__.py',
        'app/domain/models/models.py',
        'app/domain/dtos/__init__.py',
        'app/domain/dtos/serializers.py',
        
        'app/application/__init__.py',
        'app/application/apps.py',
        'app/application/exceptions/__init__.py',
        'app/application/exceptions/exceptions.py',
        'app/application/services/__init__.py',
        'app/application/services/services.py',
        
        'app/infrastructure/__init__.py',
        'app/infrastructure/apps.py',
        'app/infrastructure/persistence/__init__.py',
        'app/infrastructure/persistence/repositories/__init__.py',
        'app/infrastructure/persistence/repositories/repositories.py',
    ]
    
    for file in structure:
        path = os.path.join(base_path, file)
        if not check_file_exists(path):
            all_good = False
    
    # Verificar contenido de algunos archivos críticos
    print("\n🔍 Verificación de contenido:")
    
    files_to_verify = {
        'app/configuration/settings.py': ['INSTALLED_APPS', 'DATABASES'],
        'app/domain/models/models.py': ['class AuthUser', 'managed = False'],
        'app/api/controllers/controllers.py': ['class UserViewSet', 'class RoleViewSet'],
        'app/application/services/services.py': ['class UserService', 'class RoleService'],
    }
    
    for file_path, patterns in files_to_verify.items():
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in patterns:
                    if pattern in content:
                        print(f"  ✓ {file_path}: '{pattern}' encontrado")
                    else:
                        print(f"  ✗ {file_path}: '{pattern}' NO encontrado")
                        all_good = False
        else:
            print(f"  ✗ {file_path}: archivo no existe")
            all_good = False
    
    # Resultado final
    print("\n" + "="*50)
    if all_good:
        print("✅ Todas las verificaciones pasaron correctamente")
        print("\nProximos pasos:")
        print("1. Leer QUICKSTART.md para instrucciones de inicio")
        print("2. Activar virtual environment")
        print("3. Instalar dependencias: pip install -r requirements.txt")
        print("4. Ejecutar init_db.py para inicializar base de datos")
        print("5. Ejecutar servidor: python app/manage.py runserver")
        return 0
    else:
        print("❌ Algunas verificaciones fallaron")
        print("\nPor favor, revisa los archivos marcados con ✗")
        return 1

if __name__ == '__main__':
    sys.exit(main())
