#!/bin/bash
# Development commands for Aura Auth Service (Linux/macOS)
# Usage: ./run.sh [command]

set -e

show_help() {
    echo ""
    echo "Aura Authentication Service - Development Commands"
    echo "===================================================="
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  help              - Show this help message"
    echo "  install           - Install dependencies from requirements.txt"
    echo "  makemigrations    - Create database migrations"
    echo "  migrate           - Apply database migrations"
    echo "  setup             - Run full database setup (migrations + seed + superuser)"
    echo "  shell             - Open Django shell"
    echo "  runserver         - Start development server (http://localhost:8000)"
    echo "  createsuperuser   - Create a new superuser"
    echo "  check             - Check project configuration"
    echo "  clean             - Clean Python cache files"
    echo ""
}

if [ -z "$1" ]; then
    show_help
    exit 0
fi

case "$1" in
    help)
        show_help
        ;;
    install)
        echo "Installing dependencies..."
        pip install -r requirements.txt
        ;;
    makemigrations)
        echo "Creating migrations..."
        python manage.py makemigrations accounts
        ;;
    migrate)
        echo "Applying migrations..."
        python manage.py migrate
        ;;
    setup)
        echo "Running full database setup..."
        python scripts/setup_db.py
        ;;
    shell)
        echo "Opening Django shell..."
        python manage.py shell
        ;;
    runserver)
        echo "Starting development server..."
        echo "Open http://localhost:8000/admin/ in your browser"
        python manage.py runserver
        ;;
    createsuperuser)
        echo "Creating superuser..."
        python manage.py createsuperuser
        ;;
    check)
        echo "Checking project setup..."
        python manage.py check
        ;;
    clean)
        echo "Cleaning Python cache..."
        find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete
        echo "Cache cleaned!"
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
