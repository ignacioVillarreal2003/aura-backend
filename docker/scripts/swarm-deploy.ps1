<#
.SYNOPSIS
    Despliega el entorno completo en Docker Swarm.

.DESCRIPTION
    Este script inicializa el Swarm (si no lo está), construye las imágenes,
    renderiza la configuración final de docker-compose y la despliega como un Stack.
#>

param (
    [switch]$Gpu
)

$ErrorActionPreference = "Stop"

$servicesFile = "docker-compose\docker-compose-services.yml"
if ($Gpu) {
    Write-Host "Modo GPU Activo: utilizando docker-compose-services.gpu.yml" -ForegroundColor Cyan
    $servicesFile = "docker-compose\docker-compose-services.gpu.yml"
}

# 1. Verificar si Swarm está activo
$swarmStatus = docker info --format '{{.Swarm.LocalNodeState}}'
if ($swarmStatus -ne "active") {
    Write-Host "Iniciando Docker Swarm..." -ForegroundColor Yellow
    docker swarm init
}

# Nos ubicamos en la carpeta docker
Push-Location "$PSScriptRoot\.."

Write-Host "Construyendo imágenes (esto puede tomar un momento)..." -ForegroundColor Yellow
docker compose -f docker-compose\docker-compose-infrastructure.yml -f $servicesFile -f docker-compose\docker-compose-observability.yml build

Write-Host "Renderizando configuración con variables de entorno..." -ForegroundColor Yellow
# El comando config resuelve todas las variables (incluyendo archivos .env.docker) y genera un único YAML válido
docker compose -f docker-compose\docker-compose-infrastructure.yml -f $servicesFile -f docker-compose\docker-compose-observability.yml config | Out-File -Encoding utf8 temp-stack.yml

Write-Host "Limpiando y aplicando overrides para Swarm..." -ForegroundColor Yellow
$pyScript = @"
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
"@
Set-Content -Path cleanup.py -Value $pyScript -Encoding utf8
python cleanup.py
Remove-Item cleanup.py
Remove-Item temp-stack.yml

Write-Host "Desplegando stack en Docker Swarm..." -ForegroundColor Yellow
docker stack deploy -c rendered-stack.yml aura-backend

Write-Host "Limpiando archivo temporal..." -ForegroundColor DarkGray
Remove-Item rendered-stack.yml

Pop-Location

Write-Host ""
Write-Host "✅ Despliegue iniciado correctamente." -ForegroundColor Green
Write-Host "Puedes ver el estado de los servicios con: docker service ls" -ForegroundColor Cyan
