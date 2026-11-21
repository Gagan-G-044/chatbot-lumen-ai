"""
Gunicorn configuration for Lumen AI production deployment on Render.
"""
import os

# Render dynamically sets PORT; default to 10000
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Concurrency and thread settings
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
threads = int(os.environ.get("PYTHON_MAX_THREADS", 4))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
keepalive = 5

# Logging configuration
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
