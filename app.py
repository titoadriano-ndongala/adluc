from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from modelos.modelos import db, Utilizador, Vaga, Candidatura
import os
from werkzeug.utils import secure_filename
import feedparser

app = Flask(__name__)
app.secret_key = "segredo_adluc"

# Configuração da BD SQLite
caminho_bd = os.path.join(os.path.dirname(__file__), "baseDados", "adluc.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho_bd}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configuração uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

db.init_app(app)

with app.app_context():
    db.create_all()


# =====================
# IMPORTAÇÃO DE RSS
# =====================
RSS_URL = "http://www.net-empregos.com/rss.asp"

def importar_vagas_netempregos():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:10]:  # limita às 10 mais recentes
        titulo = entry.get("title", "")
        descricao = entry.get("summary", "")
        link = entry.get("link", "")

        if not Vaga.query.filter_by(link_externo=link).first():
            vaga = Vaga(
                titulo=titulo,
                descricao=descricao,
                externa=True,
                link_externo=link
            )
            db.session.add(vaga)
    db.session.commit()







# Página inicial
@app.route("/")
def pagina_inicial():
    return render_template("index.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def pagina_login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        utilizador = Utilizador.query.filter_by(email=email).first()
        if utilizador and utilizador.verificar_senha(senha):
            session["utilizador_id"] = utilizador.id
            session["nome"] = utilizador.nome
            session["tipo"] = utilizador.tipo
            if utilizador.tipo == "empresa":
                return redirect(url_for("pagina_empresa"))
            elif utilizador.tipo == "admin":
                return redirect(url_for("pagina_admin"))
            else:
                return redirect(url_for("pagina_vagas"))
        return render_template("login.html", erro="Credenciais inválidas")
    return render_template("login.html")

# Registo
@app.route("/registo", methods=["GET", "POST"])
def pagina_registo():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        tipo = request.form.get("tipo")

        if Utilizador.query.filter_by(email=email).first():
            return render_template("registo.html", erro="Email já registado")

        novo = Utilizador(nome=nome, email=email, tipo=tipo)
        novo.definir_senha(senha)
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for("pagina_login"))

    return render_template("registo.html")

# Vagas (listagem geral)
@app.route("/vagas")
def pagina_vagas():
    vagas = Vaga.query.all()
    return render_template("vagas.html", vagas=vagas)

# Detalhes da vaga + candidatura com upload
@app.route("/vaga/<int:vaga_id>", methods=["GET", "POST"])
def detalhes_vaga(vaga_id):
    vaga = Vaga.query.get_or_404(vaga_id)

    if request.method == "POST":
        if session.get("tipo") != "estudante":
            return redirect(url_for("pagina_login"))

        ficheiro = request.files["cv"]
        if ficheiro:
            nome_seguro = secure_filename(ficheiro.filename)
            caminho_ficheiro = os.path.join(app.config["UPLOAD_FOLDER"], nome_seguro)
            ficheiro.save(caminho_ficheiro)

            nova_cand = Candidatura(
                estudante_id=session["utilizador_id"],
                vaga_id=vaga.id,
                ficheiro_cv=nome_seguro
            )
            db.session.add(nova_cand)
            db.session.commit()
            return redirect(url_for("minhas_candidaturas"))

    return render_template("detalhes_vaga.html", vaga=vaga)

# Minhas candidaturas (para estudantes)
@app.route("/candidaturas")
def minhas_candidaturas():
    if session.get("tipo") != "estudante":
        return redirect(url_for("pagina_login"))
    candidaturas = Candidatura.query.filter_by(estudante_id=session["utilizador_id"]).all()
    return render_template("candidaturas.html", candidaturas=candidaturas)

# Empresa
@app.route("/empresa")
def pagina_empresa():
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    return render_template("empresa.html")




@app.route("/publicar", methods=["GET", "POST"])
def publicar_vaga():
    if session.get("tipo") not in ["empresa", "admin"]:
        return redirect(url_for("pagina_login"))

    if request.method == "POST":
        nova_vaga = Vaga(
            titulo=request.form.get("titulo"),
            categoria=request.form.get("categoria"),
            descricao=request.form.get("descricao"),
            cidade=request.form.get("cidade"),
            horario=request.form.get("horario"),
            tipo=request.form.get("tipo"),
            externa=False,
            empresa_id=session.get("utilizador_id")  # 🔹 guarda quem publicou
        )
        db.session.add(nova_vaga)
        db.session.commit()
        return redirect(url_for("minhas_vagas"))

    return render_template("publicar_vaga.html")



@app.route("/minhas_vagas")
def minhas_vagas():
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    vagas = Vaga.query.filter_by(empresa_id=session["utilizador_id"]).all()
    return render_template("minhas_vagas.html", vagas=vagas)





# Gerir candidaturas (empresa)
@app.route("/gerir_candidaturas")
def gerir_candidaturas():
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    candidaturas = Candidatura.query.all()  # simplificado (ideal: só das vagas da empresa)
    return render_template("gerir_candidaturas.html", candidaturas=candidaturas)

# Download CV
@app.route("/uploads/<filename>")
def download_cv(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

# Administração
@app.route("/admin")
def pagina_admin():
    if session.get("tipo") != "admin":
        return redirect(url_for("pagina_login"))
    return render_template("admin.html")



@app.route("/editar_vaga/<int:vaga_id>", methods=["GET", "POST"])
def editar_vaga(vaga_id):
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))

    vaga = Vaga.query.get_or_404(vaga_id)

    # Garante que a vaga pertence à empresa logada
    if vaga.empresa_id != session["utilizador_id"]:
        return redirect(url_for("minhas_vagas"))

    if request.method == "POST":
        vaga.titulo = request.form.get("titulo")
        vaga.categoria = request.form.get("categoria")
        vaga.descricao = request.form.get("descricao")
        vaga.cidade = request.form.get("cidade")
        vaga.horario = request.form.get("horario")
        vaga.tipo = request.form.get("tipo")
        db.session.commit()
        return redirect(url_for("minhas_vagas"))

    return render_template("editar_vaga.html", vaga=vaga)



@app.route("/remover_vaga/<int:vaga_id>", methods=["POST"])
def remover_vaga(vaga_id):
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))

    vaga = Vaga.query.get_or_404(vaga_id)

    if vaga.empresa_id != session["utilizador_id"]:
        return redirect(url_for("minhas_vagas"))

    # 🔹 Antes de apagar, remover os ficheiros CV das candidaturas desta vaga
    for cand in vaga.candidaturas:
        if cand.ficheiro_cv:  # garantir que existe
            caminho_cv = os.path.join(app.config["UPLOAD_FOLDER"], cand.ficheiro_cv)
            if os.path.exists(caminho_cv):
                os.remove(caminho_cv)

    # 🔹 Apaga a vaga (cascata remove as candidaturas do BD)
    db.session.delete(vaga)
    db.session.commit()

    return redirect(url_for("minhas_vagas"))







# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("pagina_inicial"))

if __name__ == "__main__":
    app.run(debug=True)
