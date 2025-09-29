from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class Utilizador(db.Model):
    __tablename__ = "utilizadores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # estudante, empresa, admin

    # Só se for estudante
    cv_principal = db.Column(db.String(200), nullable=True)

    # Só se for empresa
    nif = db.Column(db.String(20), nullable=True)
    nome_empresa = db.Column(db.String(200), nullable=True)
    codigo_postal = db.Column(db.String(20), nullable=True)
    distrito = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(50), nullable=True)
    logo_empresa = db.Column(db.String(200), nullable=True)

    # 🔹 Relacionamentos com CASCADE
    candidaturas = db.relationship("Candidatura", backref="estudante",
                                   cascade="all, delete-orphan", lazy=True)
    favoritos = db.relationship("Favorito", backref="estudante",
                                cascade="all, delete-orphan", lazy=True)
    vagas = db.relationship("Vaga", backref="empresa",
                            cascade="all, delete-orphan", lazy=True)
    publicacoes = db.relationship("Publicacao", backref="autor",
                                  cascade="all, delete-orphan", lazy=True)
    comentarios = db.relationship("Comentario", backref="autor",
                                  cascade="all, delete-orphan", lazy=True)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Vaga(db.Model):
    __tablename__ = "vagas"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(200), nullable=True)
    descricao = db.Column(db.Text, nullable=False)
    cidade = db.Column(db.String(100), nullable=True)
    horario = db.Column(db.String(50), nullable=True)
    tipo = db.Column(db.String(50), nullable=True)
    externa = db.Column(db.Boolean, default=False, nullable=False)
    link_externo = db.Column(db.String(500), nullable=True)
    imagem_externa = db.Column(db.String(500), nullable=True)   # ✅ novo campo
    empresa_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=True)

    candidaturas = db.relationship("Candidatura", backref="vaga",
                                   cascade="all, delete-orphan", lazy=True)
    favoritos = db.relationship("Favorito", backref="vaga",
                                cascade="all, delete-orphan", lazy=True)


class Candidatura(db.Model):
    __tablename__ = "candidaturas"
    id = db.Column(db.Integer, primary_key=True)
    estudante_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    vaga_id = db.Column(db.Integer, db.ForeignKey("vagas.id"), nullable=False)
    ficheiro_cv = db.Column(db.String(200), nullable=False)


class Favorito(db.Model):
    __tablename__ = "favoritos"
    id = db.Column(db.Integer, primary_key=True)
    estudante_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    vaga_id = db.Column(db.Integer, db.ForeignKey("vagas.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint('estudante_id', 'vaga_id',
                                          name='uq_favorito_estudante_vaga'),)


class Publicacao(db.Model):
    __tablename__ = "publicacoes"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    foto = db.Column(db.String(200), nullable=True)
    conteudo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20), default="noticia")  # noticia ou dica


class Comentario(db.Model):
    __tablename__ = "comentarios"
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    autor_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    publicacao_id = db.Column(db.Integer, db.ForeignKey("publicacoes.id"), nullable=False)