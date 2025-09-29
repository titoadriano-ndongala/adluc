# Usa uma versão estável de Python (3.10 ou 3.11)
FROM python:3.11-slim

# Define diretório de trabalho dentro do container
WORKDIR /app

# Copia os ficheiros do projeto
COPY . /app

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta usada pelo Flask
EXPOSE 8080

# Comando para iniciar a aplicação com gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
