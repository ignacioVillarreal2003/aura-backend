<#
.SYNOPSIS
    Elimina el stack desplegado en Docker Swarm.

.DESCRIPTION
    Este script elimina el stack `aura-backend`. Opcionalmente puede apagar el
    modo Swarm de Docker.
#>

param (
    [switch]$LeaveSwarm
)

$ErrorActionPreference = "Stop"

Write-Host "Eliminando stack aura-backend..." -ForegroundColor Yellow
docker stack rm aura-backend

# Esperamos a que la red se libere
Start-Sleep -Seconds 5

if ($LeaveSwarm) {
    Write-Host "Saliendo del modo Swarm..." -ForegroundColor Yellow
    docker swarm leave --force
}

Write-Host ""
Write-Host "✅ Entorno eliminado correctamente." -ForegroundColor Green
