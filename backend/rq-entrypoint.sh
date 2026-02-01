#!/bin/bash
set -e

# Run Django migrations
python manage.py migrate

# Run 1 worker for each queue
python manage.py rqworker internal ai email imports --with-scheduler
