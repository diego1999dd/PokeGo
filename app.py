from flask import Flask, request, jsonify, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash 
import os
import requests
import json
import time

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
auth_bp = Blueprint('auth', __name__)
api_bp = Blueprint('api', __name__)

# --- 1. MODELOS DE DADOS (SQLite/SQLAlchemy) ---

class Usuario(db.Model):
    __tablename__ = 'usuario'
    IDUsuario = db.Column(db.Integer, primary_key=True) 
    Nome = db.Column(db.String(100)) 
    Login = db.Column(db.String(50), unique=True)
    Email = db.Column(db.String(100), unique=True)
    Senha = db.Column(db.String(255))
    IsAdmin = db.Column(db.Boolean, default=False)
    Dtinclusao = db.Column(db.DateTime, default=datetime.utcnow) 
    DtAlteracao = db.Column(db.DateTime, onupdate=datetime.utcnow) 
    pokemons = db.relationship('PokemonUsuario', backref='usuario', lazy=True)
    def set_password(self, password): self.Senha = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.Senha, password)

class TipoPokemon(db.Model):
    __tablename__ = 'tipo_pokemon'
    IDTipoPokemon = db.Column(db.Integer, primary_key=True)
    Descricao = db.Column(db.String(50), unique=True)

class PokemonUsuario(db.Model):
    __tablename__ = 'pokemon_usuario'
    IDPokemonUsuario = db.Column(db.Integer, primary_key=True)
    IDUsuario = db.Column(db.Integer, db.ForeignKey('usuario.IDUsuario'))
    IDTipoPokemon = db.Column(db.Integer, db.ForeignKey('tipo_pokemon.IDTipoPokemon'), nullable=True) 
    Codigo = db.Column(db.String(10)) 
    Nome = db.Column(db.String(100)) 
    ImagemUrI = db.Column(db.String(255))
    GrupoBatalha = db.Column(db.Boolean, default=False)
    Favorito = db.Column(db.Boolean, default=False)

# --- 2. ROTAS DE AUTENTICAÇÃO (JWT) ---

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('Login') or not data.get('Senha') or not data.get('Email'): return jsonify({"msg": "Campos obrigatórios ausentes."}), 400
    if Usuario.query.filter_by(Login=data['Login']).first() or Usuario.query.filter_by(Email=data['Email']).first(): return jsonify({"msg": "Login ou Email já cadastrado."}), 409
    
    is_admin = Usuario.query.count() == 0
    new_user = Usuario(Nome=data.get('Nome', 'Novo Usuário'), Login=data['Login'], Email=data['Email'], IsAdmin=is_admin)
    
    new_user.set_password(data['Senha'])
    try: db.session.add(new_user); db.session.commit(); return jsonify({"msg": "Usuário criado com sucesso!"}), 201
    except Exception as e: db.session.rollback(); return jsonify({"msg": "Erro ao registrar usuário", "error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('Login') or not data.get('Senha'): return jsonify({"msg": "Login e Senha são obrigatórios."}), 400
    user = Usuario.query.filter_by(Login=data['Login']).first()
    if user and user.check_password(data['Senha']):
        access_token = create_access_token(identity=str(user.IDUsuario)) 
        return jsonify(access_token=access_token, is_admin=user.IsAdmin), 200
    return jsonify({"msg": "Credenciais inválidas"}), 401

@auth_bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    login_or_email = data.get('loginOrEmail')
    if not login_or_email: return jsonify({"msg": "Login ou Email são obrigatórios."}), 400
    user = Usuario.query.filter((Usuario.Login == login_or_email) | (Usuario.Email == login_or_email)).first()
    if not user: return jsonify({"msg": "Instruções de redefinição de senha enviadas."}), 200 
    try:
        temp_password = "defaultpassword123" 
        user.set_password(temp_password)
        db.session.commit()
        return jsonify({"msg": f"Instruções enviadas. Senha temporária: {temp_password}"}), 200 
    except Exception:
        db.session.rollback()
        return jsonify({"msg": "Instruções de redefinição de senha enviadas."}), 200

# --- 3. ROTAS DE INTEGRAÇÃO E NEGÓCIO (POKÉAPI) ---

@api_bp.route('/protected', methods=['GET'])
@jwt_required()
def protected(): return jsonify(logged_in_as=get_jwt_identity()), 200

@api_bp.route('/profile/change_password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    old_password = data.get('oldPassword')
    new_password = data.get('newPassword')
    if not old_password or not new_password or len(new_password) < 6: return jsonify({"msg": "Senha atual e nova senha (mín. 6 caracteres) são obrigatórias."}), 400
    user = Usuario.query.get(user_id)
    if not user: return jsonify({"msg": "Usuário não encontrado."}), 404
    if not user.check_password(old_password): return jsonify({"msg": "Senha atual incorreta."}), 401
    try:
        user.set_password(new_password)
        db.session.commit()
        return jsonify({"msg": "Senha alterada com sucesso!"}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"msg": "Erro interno ao atualizar senha."}), 500

# FUNÇÃO AUXILIAR PARA VERIFICAR SE O USUÁRIO É ADMIN
def admin_required():
    user_id = int(get_jwt_identity())
    user = Usuario.query.get(user_id)
    if not user or not user.IsAdmin:
        return jsonify({"msg": "Acesso negado. Requer privilégios de administrador."}), 403
    return None

# FUNÇÃO CORRIGIDA PARA PEGAR OS STATS
def fetch_pokemon_data(pokemon_id):
    API_BASE = "https://pokeapi.co/api/v2/pokemon/"
    for attempt in range(3):
        try:
            response = requests.get(f"{API_BASE}{pokemon_id}", timeout=5)
            response.raise_for_status() 
            data = response.json()
            stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
            return {
                "codigo": str(data['id']), "nome": data['name'].capitalize(), 
                "imagem_url": data['sprites']['front_default'], "tipos": [t['type']['name'] for t in data['types']],
                "hp": stats.get('hp', 0), "attack": stats.get('attack', 0), "defense": stats.get('defense', 0)
            }
        except requests.exceptions.RequestException:
            if attempt < 2: time.sleep(2 ** attempt)
    return None

@api_bp.route('/list_pokemon', methods=['GET'])
@jwt_required()
def list_pokemon():
    user_id = int(get_jwt_identity())
    pokemon_list = []
    for i in range(1, 7):
        poke_data = fetch_pokemon_data(i)
        if poke_data:
            status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=poke_data['codigo']).first()
            pokemon_list.append({
                "codigo": poke_data['codigo'], "nome": poke_data['nome'], "imagem_url": poke_data['imagem_url'],
                "tipos": poke_data['tipos'], "hp": poke_data['hp'], "attack": poke_data['attack'], "defense": poke_data['defense'],
                "favorito": status.Favorito if status else False, "grupo_batalha": status.GrupoBatalha if status else False,
            })
    return jsonify(pokemon_list), 200

@api_bp.route('/favorite', methods=['POST'])
@jwt_required()
def toggle_favorite():
    user_id = int(get_jwt_identity()); data = request.get_json(); pokemon_code = data.get('codigo')
    if not pokemon_code: return jsonify({"msg": "Código do Pokémon é obrigatório."}), 400
    pokemon_status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=pokemon_code).first()
    if pokemon_status:
        pokemon_status.Favorito = not pokemon_status.Favorito
        action = "removido dos" if not pokemon_status.Favorito else "adicionado aos"
    else:
        poke_data = fetch_pokemon_data(pokemon_code)
        if not poke_data: return jsonify({"msg": "Pokémon não encontrado na PokéAPI."}), 404
        pokemon_status = PokemonUsuario(IDUsuario=user_id, Codigo=poke_data['codigo'], Nome=poke_data['nome'], ImagemUrI=poke_data['imagem_url'], Favorito=True, GrupoBatalha=False)
        db.session.add(pokemon_status); action = "adicionado aos"
    try:
        db.session.commit(); return jsonify({"msg": f"Pokémon {pokemon_code} {action} Favoritos.", "favorito": pokemon_status.Favorito}), 200
    except Exception as e: db.session.rollback(); return jsonify({"msg": "Erro ao atualizar favoritos", "error": str(e)}), 500

@api_bp.route('/team', methods=['POST'])
@jwt_required()
def toggle_team():
    user_id = int(get_jwt_identity()); data = request.get_json(); pokemon_code = data.get('codigo')
    if not pokemon_code: return jsonify({"msg": "Código do Pokémon é obrigatório."}), 400
    pokemon_status = PokemonUsuario.query.filter_by(IDUsuario=user_id, Codigo=pokemon_code).first()
    if not pokemon_status:
        poke_data = fetch_pokemon_data(pokemon_code)
        if not poke_data: return jsonify({"msg": "Pokémon não encontrado na PokéAPI."}), 404
        pokemon_status = PokemonUsuario(IDUsuario=user_id, Codigo=poke_data['codigo'], Nome=poke_data['nome'], ImagemUrI=poke_data['imagem_url'], Favorito=False, GrupoBatalha=False)
        db.session.add(pokemon_status)
    if pokemon_status.GrupoBatalha:
        pokemon_status.GrupoBatalha = False; action = "removido do"
    else:
        current_team_count = db.session.query(PokemonUsuario).filter(PokemonUsuario.IDUsuario == user_id, PokemonUsuario.GrupoBatalha == True).count()
        if current_team_count >= 6:
            return jsonify({"msg": "Limite de 6 Pokémon no Grupo de Batalha atingido.", "grupo_batalha": pokemon_status.GrupoBatalha}), 403
        pokemon_status.GrupoBatalha = True; action = "adicionado ao"
    try:
        db.session.commit(); return jsonify({"msg": f"Pokémon {pokemon_code} {action} Grupo de Batalha.", "grupo_batalha": pokemon_status.GrupoBatalha}), 200
    except Exception as e: db.session.rollback(); return jsonify({"msg": "Erro ao atualizar Grupo de Batalha", "error": str(e)}), 500

# --- ROTAS DE ADMINISTRAÇÃO ---

# ROTA NOVO: Promove ou Despromove um usuário (Diferencial)
@api_bp.route('/admin/set_admin', methods=['POST'])
@jwt_required()
def admin_set_admin_status():
    admin_check = admin_required()
    if admin_check: return admin_check

    data = request.get_json()
    user_id = data.get('IDUsuario')
    is_admin = data.get('IsAdmin') # True/False

    if user_id is None or is_admin is None:
        return jsonify({"msg": "IDUsuario e IsAdmin são obrigatórios."}), 400

    user = Usuario.query.get(user_id)
    if not user:
        return jsonify({"msg": "Usuário não encontrado."}), 404
    
    # Previne que o Admin despromova a si mesmo (segurança)
    current_admin_id = int(get_jwt_identity())
    if user.IDUsuario == current_admin_id and is_admin == False:
        return jsonify({"msg": "Você não pode remover seu próprio status de administrador."}), 403

    try:
        user.IsAdmin = is_admin
        db.session.commit()
        return jsonify({"msg": f"Status de Admin de {user.Nome} alterado para {'SIM' if is_admin else 'NÃO'}."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"msg": "Erro ao atualizar status."}), 500


@api_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_get_users():
    admin_check = admin_required()
    if admin_check: return admin_check
    users = Usuario.query.all()
    user_list = [{'IDUsuario': user.IDUsuario, 'Nome': user.Nome, 'Email': user.Email, 'IsAdmin': user.IsAdmin} for user in users]
    return jsonify(user_list), 200

@api_bp.route('/admin/reset_password', methods=['POST'])
@jwt_required()
def admin_reset_password():
    admin_check = admin_required()
    if admin_check: return admin_check
    data = request.get_json()
    user_id = data.get('IDUsuario')
    new_password = data.get('newPassword')
    if not user_id or not new_password: return jsonify({"msg": "IDUsuario e nova senha são obrigatórios."}), 400
    user = Usuario.query.get(user_id)
    if not user: return jsonify({"msg": "Usuário não encontrado."}), 404
    try:
        user.set_password(new_password)
        db.session.commit()
        return jsonify({"msg": f"Senha do usuário {user.Nome} (ID: {user_id}) resetada com sucesso."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"msg": "Erro interno ao atualizar senha."}), 500

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:4200"}}, supports_credentials=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "sua_chave_secreta_default")
    
    db.init_app(app)
    jwt.init_app(app)
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # Note: db.create_all() deve ser chamado com o contexto da app.
    with app.app_context():
        db.create_all()

    return app