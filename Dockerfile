# Usa a imagem oficial do Python como base
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo requirements.txt para o container
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Expõe a porta que o Flask/Gunicorn irá usar
EXPOSE 8000

# Comando para iniciar o servidor Gunicorn (servidor de produção)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "wsgi:app"]