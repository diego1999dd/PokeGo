# app.py (ARQUIVO PRINCIPAL NA RAIZ DO PROJETO)
# Contém Modelos, Configurações e Rotas em um único arquivo para resolver problemas de importação.

from flask import Flask, request, jsonify, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash 
import os
import requests
import json
import time

# Carrega as variáveis de ambiente
load_dotenv()

# Inicializa as extensões
db = SQLAlchemy()
jwt = JWTManager()
auth_bp = Blueprint('auth', __name__)
api_bp = Blueprint('api', __name__)

# --- 1. MODELOS DE DADOS (SQLite/SQLAlchemy) ---

class Usuario(db.Model):
    # Tabela com Usuários cadastrados para acesso do sistema
    __tablename__ = 'usuario'
    
    IDUsuario = db.Column(db.Integer, primary_key=True) 
    Nome = db.Column(db.String(100)) 
    Login = db.Column(db.String(50), unique=True)
    Email = db.Column(db.String(100), unique=True)
    Senha = db.Column(db.String(255)) # Armazena hash
    Dtinclusao = db.Column(db.DateTime, default=datetime.utcnow) 
    DtAlteracao = db.Column(db.DateTime, onupdate=datetime.utcnow) 
    
    pokemons = db.relationship('PokemonUsuario', backref='usuario', lazy=True)

    def set_password(self, password):
        # Gera o hash da senha
        self.Senha = generate_password_hash(password)

    def check_password(self, password):
        # Verifica se a senha corresponde ao hash
        return check_password_hash(self.Senha, password)

class TipoPokemon(db.Model):
    # Tipos de Pokémon: Fogo, Água, Grama, Voador etc...
    __tablename__ = 'tipo_pokemon'
    
    IDTipoPokemon = db.Column(db.Integer, primary_key=True)
    Descricao = db.Column(db.String(50), unique=True)

class PokemonUsuario(db.Model):
    # Pokémon que estará listado como Pertencente ao Grupo de Batalha ou na listagem de favoritos.
    __tablename__ = 'pokemon_usuario'

    IDPokemonUsuario = db.Column(db.Integer, primary_key=True)
    
    IDUsuario = db.Column(db.Integer, db.ForeignKey('usuario.IDUsuario'))
    IDTipoPokemon = db.Column(db.Integer, db.ForeignKey('tipo_pokemon.IDTipoPokemon'), nullable=True) 
    
    Codigo = db.Column(db.String(10)) # ID ou nome do Pokémon na PokéAPI
    Nome = db.Column(db.String(100)) 
    ImagemUrI = db.Column(db.String(255))
    
    GrupoBatalha = db.Column(db.Boolean, default=False) # BIT
    Favorito = db.Column(db.Boolean, default=False) # BIT

# --- 2. ROTAS DE AUTENTICAÇÃO (JWT) ---

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('Login') or not data.get('Senha') or not data.get('Email'):
        return jsonify({"msg": "Campos obrigatórios ausentes."}), 400

    if Usuario.query.filter_by(Login=data['Login']).first() or Usuario.query.filter_by(Email=data['Email']).first():
        return jsonify({"msg": "Login ou Email já cadastrado."}), 409

    new_user = Usuario(Nome=data.get('Nome', 'Novo Usuário'), Login=data['Login'], Email=data['Email'])
    new_user.set_password(data['Senha'])

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"msg": "Usuário criado com sucesso!"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Erro ao registrar usuário", "error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('Login') or not data.get('Senha'):
        return jsonify({"msg": "Login e Senha são obrigatórios."}), 400

    user = Usuario.query.filter_by(Login=data['Login']).first()

    if user and user.check_password(data['Senha']):
        # Converte o IDUsuario (Integer) para STR antes de criar o token (Evita 422 UNPROCESSABLE ENTITY)
        access_token = create_access_token(identity=str(user.IDUsuario)) 
        return jsonify(access_token=access_token), 200
    
    return jsonify({"msg": "Credenciais inválidas"}), 401

# --- 3. ROTAS DE INTEGRAÇÃO E NEGÓCIO (POKÉAPI) ---

# Rota de teste protegida por JWT
@api_bp.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity() 
    return jsonify(logged_in_as=current_user_id), 200

# Função auxiliar para chamar a PokéAPI (Requisito 4: Backend centraliza a API)
def fetch_pokemon_data(pokemon_id):
    API_BASE = "https://pokeapi.co/api/v2/pokemon/"
    # Lógica simples de Exponential Backoff para resiliência (melhoria)
    for attempt in range(3):
        try:
            response = requests.get(f"{API_BASE}{pokemon_id}", timeout=5)
            response.raise_for_status() 
            data = response.json()
            
            # Extrai os dados relevantes:
            return {
                "codigo": str(data['id']),
                "nome": data['name'].capitalize(),
                "imagem_url": data['sprites']['front_default'],
                "tipos": [t['type']['name'] for t in data['types']]
            }
        except requests.exceptions.RequestException:
            # Tenta novamente em caso de falha de conexão ou timeout
            if attempt < 2:
                time.sleep(2 ** attempt) # 1s, 2s
    return None

@api_bp.route('/list_pokemon', methods=['GET'])
@jwt_required()
def list_pokemon():
    user_id = int(get_jwt_identity())
    
    # Simula a busca dos 10 primeiros Pokémon (pode ser expandido com filtros)
    pokemon_list = []
    
    for i in range(1, 7): 
        poke_data = fetch_pokemon_data(i)
        if poke_data:
            # Busca o status deste Pokémon para o usuário
            status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=poke_data['codigo']).first()
            
            pokemon_list.append({
                "codigo": poke_data['codigo'],
                "nome": poke_data['nome'],
                "imagem_url": poke_data['imagem_url'],
                "tipos": poke_data['tipos'],
                "favorito": status.Favorito if status else False,
                "grupo_batalha": status.GrupoBatalha if status else False,
            })
            
    return jsonify(pokemon_list), 200

@api_bp.route('/favorite', methods=['POST'])
@jwt_required()
def toggle_favorite():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    pokemon_code = data.get('codigo')
    
    if not pokemon_code:
        return jsonify({"msg": "Código do Pokémon é obrigatório."}), 400

    pokemon_status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=pokemon_code).first()

    if pokemon_status:
        pokemon_status.Favorito = not pokemon_status.Favorito
        action = "removido dos" if not pokemon_status.Favorito else "adicionado aos"
    else:
        poke_data = fetch_pokemon_data(pokemon_code)
        if not poke_data:
            return jsonify({"msg": "Pokémon não encontrado na PokéAPI."}), 404

        pokemon_status = PokemonUsuario(
            IDUsuario=user_id,
            Codigo=poke_data['codigo'],
            Nome=poke_data['nome'],
            ImagemUrI=poke_data['imagem_url'],
            Favorito=True,
            GrupoBatalha=False
        )
        db.session.add(pokemon_status)
        action = "adicionado aos"

    try:
        db.session.commit()
        return jsonify({
            "msg": f"Pokémon {pokemon_code} {action} Favoritos.",
            "favorito": pokemon_status.Favorito
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Erro ao atualizar favoritos", "error": str(e)}), 500

# ROTA CORRIGIDA: Adicionar/Remover do Grupo de Batalha (Regra de 6 Garantida)
@api_bp.route('/team', methods=['POST'])
@jwt_required()
def toggle_team():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    pokemon_code = data.get('codigo')
    
    if not pokemon_code:
        return jsonify({"msg": "Código do Pokémon é obrigatório."}), 400

    pokemon_status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=pokemon_code).first()
    
    # 1. Se não existir, busca e cria o registro
    if not pokemon_status:
        poke_data = fetch_pokemon_data(pokemon_code)
        if not poke_data:
            return jsonify({"msg": "Pokémon não encontrado na PokéAPI."}), 404
        
        pokemon_status = PokemonUsuario(
            IDUsuario=user_id,
            Codigo=poke_data['codigo'],
            Nome=poke_data['nome'],
            ImagemUrI=poke_data['imagem_url'],
            Favorito=False,
            GrupoBatalha=False
        )
        db.session.add(pokemon_status)
        # Não commita aqui, commita no final para ser uma transação única
        
    # 2. Lógica de Adicionar/Remover
    if pokemon_status.GrupoBatalha:
        # REMOVER DO GRUPO
        pokemon_status.GrupoBatalha = False
        action = "removido do"
    else:
        # ADICIONAR AO GRUPO
        
        # OTIMIZAÇÃO: Garante que a contagem é feita no momento exato (Somente os que já estão no time)
        current_team_count = db.session.query(PokemonUsuario).filter(
            PokemonUsuario.IDUsuario == user_id, 
            PokemonUsuario.GrupoBatalha == True
        ).count()

        # Verifica a regra de limite (Máximo de 6)
        if current_team_count >= 6:
            return jsonify({
                "msg": "Limite de 6 Pokémon no Grupo de Batalha atingido.",
                "grupo_batalha": pokemon_status.GrupoBatalha # Retorna o status anterior (False)
            }), 403 # FORBIDDEN (Erro esperado)
        
        pokemon_status.GrupoBatalha = True
        action = "adicionado ao"

    try:
        db.session.commit()
        return jsonify({
            "msg": f"Pokémon {pokemon_code} {action} Grupo de Batalha.",
            "grupo_batalha": pokemon_status.GrupoBatalha
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Erro ao atualizar Grupo de Batalha", "error": str(e)}), 500


def create_app():
    app = Flask(__name__)
    
    # 1. Configuração do Banco de Dados
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 2. Configuração do JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "sua_chave_secreta_default") 
    
    db.init_app(app)
    jwt.init_app(app)
    
    # Registra os Blueprints (Prefixos /api/v1/auth/ e /api/v1/ )
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    with app.app_context():
        # Cria as tabelas do BD
        db.create_all()

    return app

if __name__ == '__main__':
    # EXECUÇÃO DIRETA DE PYTHON (A MAIS SEGURA PARA SEU AMBIENTE)
    app = create_app()
    app.run(debug=True)
