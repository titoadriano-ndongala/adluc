from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ======================
# Utilizador
# ======================
class Utilizador(db.Model):
    __tablename__ = "utilizadores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # estudante, empresa, admin

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

# ======================
# Vaga
# ======================
class Vaga(db.Model):
    __tablename__ = "vagas"
    id = db.Column(db.Integer, primary_key=True)

    # Título obrigatório
    titulo = db.Column(db.String(200), nullable=False)

    # ✅ Campos tornam-se opcionais (feeds podem não trazer isto)
    categoria = db.Column(db.String(200), nullable=True)
    descricao = db.Column(db.Text, nullable=False)

    cidade = db.Column(db.String(100), nullable=True)
    horario = db.Column(db.String(50), nullable=True)      # full-time, part-time, remoto
    tipo = db.Column(db.String(50), nullable=True)         # emprego, estagio, bolsa

    # Externas
    externa = db.Column(db.Boolean, default=False, nullable=False)
    link_externo = db.Column(db.String(500), nullable=True)

    # Autor (empresa) – opcional
    empresa_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=True)
    empresa = db.relationship("Utilizador", backref="vagas", lazy=True)

    # Candidaturas (cascade)
    candidaturas = db.relationship("Candidatura", backref="vaga", cascade="all, delete-orphan")

# ======================
# Candidatura
# ======================
class Candidatura(db.Model):
    __tablename__ = "candidaturas"
    id = db.Column(db.Integer, primary_key=True)

    estudante_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    vaga_id = db.Column(db.Integer, db.ForeignKey("vagas.id"), nullable=False)

    ficheiro_cv = db.Column(db.String(200), nullable=False)

    estudante = db.relationship("Utilizador", backref="candidaturas", lazy=True)
