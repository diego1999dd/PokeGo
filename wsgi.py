# wsgi.py
from app import create_app

# O Gunicorn vai procurar por esta variável 'app'
# E esta linha garante que sua fábrica seja chamada UMA VEZ para criar a aplicação.
app = create_app()