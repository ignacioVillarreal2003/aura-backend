#!/bin/bash
set -e

# Procesar argumentos de línea de comandos
USE_GPU=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --gpu) USE_GPU=true; shift ;;
        *) echo "Parámetro desconocido: $1"; exit 1 ;;
    esac
done

SERVICES_FILE="docker-compose/docker-compose-services.yml"
if [ "$USE_GPU" = true ]; then
    echo -e "\e[36mModo GPU Activo: utilizando docker-compose-services.gpu.yml\e[0m"
    SERVICES_FILE="docker-compose/docker-compose-services.gpu.yml"
fi

# 1. Verificar si Swarm está activo
SWARM_STATUS=$(docker info --format '{{.Swarm.LocalNodeState}}')
if [ "$SWARM_STATUS" != "active" ]; then
    echo -e "\e[33mIniciando Docker Swarm...\e[0m"
    docker swarm init
fi

# Nos ubicamos en la carpeta docker
cd "$(dirname "$0")/.."

echo -e "\e[33mConstruyendo imágenes (esto puede tomar un momento)...\e[0m"
docker compose -f docker-compose/docker-compose-infrastructure.yml -f "$SERVICES_FILE" -f docker-compose/docker-compose-observability.yml build

echo -e "\e[33mRenderizando configuración con variables de entorno...\e[0m"
# El comando config resuelve todas las variables (incluyendo archivos .env.docker) y genera un único YAML válido
docker compose -f docker-compose/docker-compose-infrastructure.yml -f "$SERVICES_FILE" -f docker-compose/docker-compose-observability.yml config > temp-stack.yml

echo -e "\e[33mLimpiando y aplicando overrides para Swarm...\e[0m"
cat << 'EOF' > cleanup.py
import yaml
with open('temp-stack.yml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

try:
    with open('docker-compose/docker-compose.swarm.yml', 'r', encoding='utf-8') as sf:
        swarm_data = yaml.safe_load(sf)
except Exception:
    swarm_data = {}

if 'name' in data:
    del data['name']

for srv_name, srv in data.get('services', {}).items():
    if 'image' not in srv:
        srv['image'] = f"docker-compose-{srv_name}"
    if 'depends_on' in srv:
        del srv['depends_on']
    if 'container_name' in srv:
        del srv['container_name']
    
    # Aplicar réplicas y configuraciones deploy específicas de Swarm
    swarm_srv = swarm_data.get('services', {}).get(srv_name, {})
    if 'deploy' in swarm_srv:
        if 'deploy' not in srv:
            srv['deploy'] = {}
        srv['deploy'].update(swarm_srv['deploy'])

    if 'ports' in srv:
        for p in srv['ports']:
            if 'published' in p and isinstance(p['published'], str):
                try: p['published'] = int(p['published'])
                except: pass

with open('rendered-stack.yml', 'w', encoding='utf-8') as f:
    yaml.dump(data, f, sort_keys=False)
EOF

python cleanup.py
rm cleanup.py temp-stack.yml

echo -e "\e[33mDesplegando stack en Docker Swarm...\e[0m"
docker stack deploy -c rendered-stack.yml aura-backend

echo -e "\e[90mLimpiando archivo temporal...\e[0m"
rm rendered-stack.yml

echo -e "\n\e[32m✅ Despliegue iniciado correctamente.\e[0m"
echo -e "\e[36mPuedes ver el estado de los servicios con: docker service ls\e[0m"
