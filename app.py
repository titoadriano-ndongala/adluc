import os
import re
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from modelos.modelos import db, Utilizador, Vaga, Candidatura

# Feeds / HTTP / Scheduler
import requests
from requests.adapters import HTTPAdapter, Retry
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "segredo_adluc"

# ======================
# Config BD / Uploads
# ======================
caminho_bd = os.path.join(os.path.dirname(__file__), "baseDados", "adluc.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho_bd}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

# Upload – extensões permitidas
EXTENSOES_CV = {"pdf", "doc", "docx"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in EXTENSOES_CV

db.init_app(app)
with app.app_context():
    db.create_all()

# ======================
# Utils
# ======================
def strip_html(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

# ======================
# FEEDS EXTERNOS
# ======================
FEEDS_EXTERNOS = [
    # Empregos PT (Expresso Emprego)
    "http://www.expressoemprego.pt/rss/ultimas-ofertas",
    "http://www.expressoemprego.pt/rss/informatica",
    "http://www.expressoemprego.pt/rss/lisboa",

    # Agregador (HUORK)
    "https://www.huork.com/rss/all/",

    # Investigação (EURAXESS)
    "https://euraxess.ec.europa.eu/job-feed",

    # FCT (Notícias/Agenda/Ciência)
    "https://www.fct.pt/media/noticias/feed/",
    "https://www.fct.pt/media/noticias/feed/?type=calendar_event",
    "https://www.fct.pt/media/noticias/feed/?type=science_in_focus",
]

def _http_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AdLucBot/1.0 (+https://adluc.local)"
    })
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def _parse_feed(url: str):
    try:
        sess = _http_session()
        resp = sess.get(url, timeout=12)
        if resp.status_code != 200 or not resp.content:
            print(f"⚠️ Feed falhou HTTP {resp.status_code}: {url}")
            return []
        parsed = feedparser.parse(resp.content)
        entradas = getattr(parsed, "entries", []) or []
        print(f"🔎 {url} → {len(entradas)} entradas")
        return entradas
    except Exception as e:
        print(f"❌ Erro no feed {url}: {e}")
        return []

SEMENTE_EXTERNAS = [
    {
        "titulo": "Estágio Júnior em Análise de Dados (Remoto) — Externo",
        "descricao": "Programa de estágio com mentoria. Python/SQL. Duração 6 meses.",
        "link": "https://exemplo-empregos.pt/anuncio/estagio-analise-dados",
        "categoria": "Emprego (RSS)",
        "tipo": "emprego",
    },
    {
        "titulo": "Bolsa de Investigação — IA aplicada à Saúde — Externo",
        "descricao": "Bolsa para Mestrandos/Doutorandos. Projeto de 12 meses.",
        "link": "https://exemplo-bolsas.pt/bolsa/ia-saude-2025",
        "categoria": "Bolsas/Notícias (RSS)",
        "tipo": "bolsa",
    }
]

def _inferir_defaults_por_url(url: str):
    u = url.lower()
    if "expressoemprego.pt" in u or "huork.com" in u:
        return "Emprego (RSS)", "emprego"
    if "euraxess" in u:
        return "Investigação (RSS)", "emprego"
    if "fct.pt" in u:
        return "Bolsas/Notícias (RSS)", "bolsa"
    return "Emprego/Notícias (RSS)", "emprego"

def importar_vagas_externas():
    insercoes = 0
    total_entradas = 0

    for url in FEEDS_EXTERNOS:
        categoria_def, tipo_def = _inferir_defaults_por_url(url)
        entradas = _parse_feed(url)
        total_entradas += len(entradas)

        for entry in entradas[:8]:
            titulo = strip_html(entry.get("title") or "")
            descricao = strip_html(entry.get("summary") or entry.get("description") or titulo)
            link = (entry.get("link") or "").strip()

            if not link or not titulo:
                continue

            if not Vaga.query.filter_by(link_externo=link).first():
                vaga = Vaga(
                    titulo=titulo[:200],
                    descricao=(descricao or titulo)[:2000],
                    categoria=categoria_def,
                    tipo=tipo_def,
                    cidade=None,
                    horario=None,
                    externa=True,
                    link_externo=link
                )
                db.session.add(vaga)
                insercoes += 1

    if total_entradas == 0:
        print("ℹ️ Sem entradas reais dos feeds — a semear externas de fallback.")
        for item in SEMENTE_EXTERNAS:
            if not Vaga.query.filter_by(link_externo=item["link"]).first():
                vaga = Vaga(
                    titulo=item["titulo"][:200],
                    descricao=item["descricao"][:2000],
                    categoria=item["categoria"],
                    tipo=item["tipo"],
                    externa=True,
                    link_externo=item["link"]
                )
                db.session.add(vaga)
                insercoes += 1

    if insercoes:
        db.session.commit()
        print(f"✅ Inseridas {insercoes} vagas externas (inclui fallback se necessário).")
    else:
        print("ℹ️ Nenhuma vaga externa nova para inserir.")

# ======================
# Scheduler (30 min)
# ======================
scheduler = BackgroundScheduler()
def tarefa_atualizar_vagas():
    with app.app_context():
        importar_vagas_externas()
scheduler.add_job(tarefa_atualizar_vagas, "interval", minutes=30)
scheduler.start()

# ======================
# Rotas
# ======================
@app.route("/")
def pagina_inicial():
    importar_vagas_externas()
    vagas_internas = Vaga.query.filter_by(externa=False).order_by(Vaga.id.desc()).limit(3).all()
    vagas_externas = Vaga.query.filter_by(externa=True).order_by(Vaga.id.desc()).limit(3).all()
    return render_template("index.html",
                           vagas_internas=vagas_internas,
                           vagas_externas=vagas_externas)

# --- Login
from werkzeug.security import check_password_hash
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

# --- Registo
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

# --- Vagas (listagem + pesquisa + paginação)
@app.route("/vagas")
def pagina_vagas():
    # filtros
    texto = request.args.get("q", "", type=str).strip()
    cidade = request.args.get("cidade", "", type=str).strip()
    categoria = request.args.get("categoria", "", type=str).strip()
    horario = request.args.get("horario", "", type=str).strip()
    tipo = request.args.get("tipo", "", type=str).strip()

    # paginação
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 9

    query = Vaga.query.order_by(Vaga.id.desc())

    if texto:
        like = f"%{texto}%"
        query = query.filter(
            (Vaga.titulo.ilike(like)) | (Vaga.descricao.ilike(like))
        )
    if cidade:
        query = query.filter(Vaga.cidade.ilike(f"%{cidade}%"))
    if categoria:
        query = query.filter(Vaga.categoria.ilike(f"%{categoria}%"))
    if horario:
        query = query.filter(Vaga.horario == horario)
    if tipo:
        query = query.filter(Vaga.tipo == tipo)

    total = query.count()
    vagas = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()

    # dados para paginação simples
    tem_prev = pagina > 1
    tem_next = (pagina * por_pagina) < total

    return render_template(
        "vagas.html",
        vagas=vagas,
        total=total,
        pagina=pagina,
        tem_prev=tem_prev,
        tem_next=tem_next,
        filtros={"q": texto, "cidade": cidade, "categoria": categoria, "horario": horario, "tipo": tipo}
    )

# --- Detalhes + candidatura (upload CV)
@app.route("/vaga/<int:vaga_id>", methods=["GET", "POST"])
def detalhes_vaga(vaga_id):
    vaga = Vaga.query.get_or_404(vaga_id)
    erro_upload = None
    sucesso = False

    if request.method == "POST":
        if session.get("tipo") != "estudante":
            return redirect(url_for("pagina_login"))
        ficheiro = request.files.get("cv")
        if not ficheiro or ficheiro.filename == "":
            erro_upload = "Seleciona um ficheiro."
        elif not allowed_file(ficheiro.filename):
            erro_upload = "Formato inválido. Aceitamos: PDF, DOC, DOCX."
        else:
            nome_seguro = secure_filename(ficheiro.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_seguro)
            ficheiro.save(caminho)
            cand = Candidatura(
                estudante_id=session["utilizador_id"],
                vaga_id=vaga.id,
                ficheiro_cv=nome_seguro
            )
            db.session.add(cand)
            db.session.commit()
            sucesso = True

    return render_template("detalhes_vaga.html", vaga=vaga, erro_upload=erro_upload, sucesso=sucesso)

# --- Minhas candidaturas (estudante)
@app.route("/candidaturas")
def minhas_candidaturas():
    if session.get("tipo") != "estudante":
        return redirect(url_for("pagina_login"))
    candidaturas = Candidatura.query.filter_by(estudante_id=session["utilizador_id"]).all()
    return render_template("candidaturas.html", candidaturas=candidaturas)

# --- Empresa
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
        vaga = Vaga(
            titulo=request.form.get("titulo"),
            categoria=request.form.get("categoria") or None,
            descricao=request.form.get("descricao"),
            cidade=request.form.get("cidade") or None,
            horario=request.form.get("horario") or None,
            tipo=request.form.get("tipo") or None,
            externa=False,
            empresa_id=session.get("utilizador_id")
        )
        db.session.add(vaga)
        db.session.commit()
        return redirect(url_for("minhas_vagas"))
    return render_template("publicar_vaga.html")

@app.route("/minhas_vagas")
def minhas_vagas():
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    vagas = Vaga.query.filter_by(empresa_id=session["utilizador_id"]).order_by(Vaga.id.desc()).all()
    return render_template("minhas_vagas.html", vagas=vagas)

@app.route("/editar_vaga/<int:vaga_id>", methods=["GET", "POST"])
def editar_vaga(vaga_id):
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    vaga = Vaga.query.get_or_404(vaga_id)
    if vaga.empresa_id != session["utilizador_id"]:
        return redirect(url_for("minhas_vagas"))
    if request.method == "POST":
        vaga.titulo = request.form.get("titulo")
        vaga.categoria = request.form.get("categoria") or None
        vaga.descricao = request.form.get("descricao")
        vaga.cidade = request.form.get("cidade") or None
        vaga.horario = request.form.get("horario") or None
        vaga.tipo = request.form.get("tipo") or None
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
    # remove ficheiros CV ligados à vaga
    for cand in vaga.candidaturas:
        if cand.ficheiro_cv:
            caminho_cv = os.path.join(app.config["UPLOAD_FOLDER"], cand.ficheiro_cv)
            if os.path.exists(caminho_cv):
                os.remove(caminho_cv)
    db.session.delete(vaga)
    db.session.commit()
    return redirect(url_for("minhas_vagas"))

@app.route("/gerir_candidaturas")
def gerir_candidaturas():
    if session.get("tipo") != "empresa":
        return redirect(url_for("pagina_login"))
    candidaturas = Candidatura.query.join(Vaga).filter(Vaga.empresa_id == session["utilizador_id"]).all()
    return render_template("gerir_candidaturas.html", candidaturas=candidaturas)

@app.route("/uploads/<filename>")
def download_cv(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/admin")
def pagina_admin():
    if session.get("tipo") != "admin":
        return redirect(url_for("pagina_login"))
    return render_template("admin.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("pagina_inicial"))

if __name__ == "__main__":
    app.run(debug=True)
