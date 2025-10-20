# POKEGO-API: DESAFIO TÉCNICO FULLSTACK (KOGUI)

## Visão Geral

Este projeto é a implementação do desafio técnico Fullstack, desenvolvendo um Backend em **Python (Flask)**. A API se integra à **PokéAPI** e utiliza **SQLite** com **SQLAlchemy** para gerenciar dados de usuário, favoritos e a equipe de batalha. A autenticação é realizada via **Token JWT**.

O projeto foi totalmente containerizado com **Docker**, cumprindo o requisito diferencial opcional e garantindo que a aplicação seja executada de forma idêntica em qualquer ambiente.

### Tecnologias Principais

- **Backend:** Python (Flask)
- **Banco de Dados:** SQLite e SQLAlchemy
- **Servidor de Produção:** Gunicorn
- **Containerização:** Docker e Docker Compose
- **Front-End Compatível:** Angular (configurado para `http://localhost:8000`)

---

## 1. Configuração de Ambiente (`.env` - Obrigatório)

A chave secreta para a geração e validação do Token JWT deve ser definida em um arquivo de ambiente.

1.  **Criação do Arquivo:** Crie um arquivo chamado **`.env`** na raiz do projeto.
2.  **Gere a Chave Secreta:** Para garantir a segurança, use o módulo `secrets` do Python para gerar uma chave longa e aleatória. Execute este comando no seu terminal:
    ```bash
    python -c 'import secrets; print(secrets.token_hex(32))'
    ```
3.  **Adicione ao `.env`:** Adicione a chave gerada ao arquivo `.env`:
    ```
    # Variável de chave secreta para geração e validação do JWT
    JWT_SECRET_KEY=cole_a_chave_gerada_aqui
    ```

---

## 2. Inicialização da API Backend

A API está configurada para rodar na porta **8000** em ambos os métodos de execução.

### 2.1. Método Docker (Recomendado)

Requer apenas o Docker Desktop (ou Engine) instalado. É a forma mais rápida e confiável de iniciar.

1.  **Pré-requisito:** Instalar e iniciar o **Docker Desktop**.
2.  **Construir e Iniciar:** Na raiz do projeto (onde está o `docker-compose.yml`), execute:
    ```bash
    docker-compose up --build
    ```
    O Docker irá construir a imagem, mapear a porta `8000` e iniciar o servidor Gunicorn via `wsgi:app`.

### 2.2. Método Local (Alternativo)

Requer Python 3.10+ e as dependências instaladas.

1.  **Instalação de Dependências:**

    ```bash
    # 1. Crie e ative o ambiente virtual
    python -m venv venv
    source venv/bin/activate  # macOS/Linux (ou use a versão do Windows)

    # 2. Instale as dependências (incluindo o Gunicorn)
    pip install -r requirements.txt
    ```

2.  **Executar a API (Garantindo a Porta 8000):**
    Para rodar na porta correta, utilize o Gunicorn (que foi configurado como servidor de produção no Docker):
    ```bash
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
    ```

---

## 3. Teste e Uso da API

A API estará acessível em: `http://localhost:8000/api/v1/`

### Endpoints Principais

| Funcionalidade             | Endpoint (URL Completa)                      | Método |
| :------------------------- | :------------------------------------------- | :----- |
| **Registro**               | `http://localhost:8000/api/v1/auth/register` | `POST` |
| **Login**                  | `http://localhost:8000/api/v1/auth/login`    | `POST` |
| **Listar Pokémon**         | `http://localhost:8000/api/v1/list_pokemon`  | `GET`  |
| **Favoritar/Desfavoritar** | `http://localhost:8000/api/v1/favorite`      | `POST` |

### Integração Front-End

Se quiser testar a API já em um Front-End pronto, é só clonar o meu respositório em Angular: https://github.com/diego1999dd/PokeGo-Front

O Front-End Angular deve ser configurado para usar a URL base `http://localhost:8000/api/v1` para todas as requisições. A configuração de CORS no Backend já permite requisições da origem padrão do Angular (`http://localhost:4200`).
