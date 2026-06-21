#!/bin/bash
set -e

LEAVE_SWARM=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --leave-swarm) LEAVE_SWARM=true; shift ;;
        *) echo "Parámetro desconocido: $1"; exit 1 ;;
    esac
done

echo -e "\e[33mEliminando stack aura-backend...\e[0m"
docker stack rm aura-backend

sleep 5

if [ "$LEAVE_SWARM" = true ]; then
    echo -e "\e[33mSaliendo del modo Swarm...\e[0m"
    docker swarm leave --force
fi

echo -e "\n\e[32m✅ Entorno eliminado correctamente.\e[0m"
