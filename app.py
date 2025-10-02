import os
import re
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from modelos.modelos import db, Utilizador, Vaga, Candidatura, Favorito, Publicacao, Comentario


# RSS / HTTP / Scheduler
import requests
from requests.adapters import HTTPAdapter, Retry
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "segredo_adluc"

# ===== Base de dados / uploads =====
BASE_DIR = os.path.dirname(__file__)
os.makedirs(os.path.join(BASE_DIR, "baseDados"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR,'baseDados','adluc.db')}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

# Configuração do e-mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'titoadriano.aryan@gmail.com'
app.config['MAIL_PASSWORD'] = 'Ndongala931217420.'
app.config['MAIL_DEFAULT_SENDER'] = ('adluc Notificações', 'titoadriano.aryan@gmail.com')

mail = Mail(app)

db.init_app(app)
with app.app_context():
    db.create_all()

# ===== Utils =====
EXTENSOES_CV = {"pdf", "doc", "docx"}
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in EXTENSOES_CV

def strip_html(txt: str) -> str:
    if not txt: return ""
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

def ids_favoritos_do_estudante():
    if session.get("tipo") != "estudante":
        return set()
    favs = Favorito.query.filter_by(estudante_id=session["utilizador_id"]).all()
    return {f.vaga_id for f in favs}

# ===== FEEDS EXTERNOS =====
FEEDS_EXTERNOS = [
    "http://www.expressoemprego.pt/rss/ultimas-ofertas",
    "http://www.expressoemprego.pt/rss/informatica",
    "http://www.expressoemprego.pt/rss/lisboa",
    "https://www.huork.com/rss/all/",
    "https://euraxess.ec.europa.eu/job-feed",
    "https://www.fct.pt/media/noticias/feed/",
    "https://www.fct.pt/media/noticias/feed/?type=calendar_event",
    "https://www.fct.pt/media/noticias/feed/?type=science_in_focus",
]

def _http_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 AdLucBot/1.0"})
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def _parse_feed(url: str):
    try:
        resp = _http_session().get(url, timeout=12)
        if resp.status_code != 200 or not resp.content:
            print(f"feed HTTP {resp.status_code}: {url}")
            return []
        parsed = feedparser.parse(resp.content)
        return getattr(parsed, "entries", []) or []
    except Exception as e:
        print(f"feed erro {url}: {e}")
        return []

def _inferir_defaults_por_url(url: str):
    u = url.lower()
    if "expressoemprego" in u or "huork" in u: return "Emprego (RSS)", "emprego"
    if "euraxess" in u: return "Investigação (RSS)", "emprego"
    if "fct.pt" in u: return "Bolsas/Notícias (RSS)", "bolsa"
    return "Emprego/Notícias (RSS)", "emprego"

SEMENTE_EXTERNAS = [
    {"titulo":"Estágio Júnior em Dados — Externo",
     "descricao":"Programa de estágio remoto 6 meses.",
     "link":"https://exemplo-empregos.pt/estagio-dados","categoria":"Emprego (RSS)","tipo":"emprego"}
]

def importar_vagas_externas():
    insercoes, total_entradas = 0, 0
    for url in FEEDS_EXTERNOS:
        categoria_def, tipo_def = _inferir_defaults_por_url(url)
        entries = _parse_feed(url); total_entradas += len(entries)
        for e in entries[:8]:
            titulo = strip_html(e.get("title") or "")
            descricao = strip_html(e.get("summary") or e.get("description") or titulo)
            link = (e.get("link") or "").strip()
            if not link or not titulo:
                continue

            # Tentar buscar imagem
            imagem = None
            if "media_content" in e and e.media_content:
                imagem = e.media_content[0].get("url")
            elif "enclosures" in e and e.enclosures:
                imagem = e.enclosures[0].get("href")

            if not Vaga.query.filter_by(link_externo=link).first():
                db.session.add(Vaga(
                    titulo=titulo[:200],
                    descricao=(descricao or titulo)[:2000],
                    categoria=categoria_def,
                    tipo=tipo_def,
                    externa=True,
                    link_externo=link,
                    imagem_externa=imagem  # guarda se houver
                ))
                insercoes += 1
    if total_entradas == 0:
        for it in SEMENTE_EXTERNAS:
            if not Vaga.query.filter_by(link_externo=it["link"]).first():
                db.session.add(Vaga(
                    titulo=it["titulo"][:200], descricao=it["descricao"][:2000],
                    categoria=it["categoria"], tipo=it["tipo"],
                    externa=True, link_externo=it["link"],
                    imagem_externa=None
                ))
                insercoes += 1
    if insercoes:
        db.session.commit()

# ===== Scheduler (30 min) =====
scheduler = BackgroundScheduler()
def tarefa_atualizar_vagas():
    with app.app_context():
        importar_vagas_externas()
scheduler.add_job(tarefa_atualizar_vagas, "interval", minutes=30)
scheduler.start()

# ===== Rotas =====
@app.route("/", endpoint="pagina_inicial")
def pagina_inicial():
    importar_vagas_externas()

    vagas_internas = Vaga.query.filter_by(externa=False).order_by(Vaga.id.desc()).limit(3).all()
    vagas_externas = Vaga.query.filter_by(externa=True).order_by(Vaga.id.desc()).limit(3).all()

    noticias = Publicacao.query.filter_by(tipo="noticia").order_by(Publicacao.data_hora.desc()).limit(3).all()
    dicas = Publicacao.query.filter_by(tipo="dica").order_by(Publicacao.data_hora.desc()).limit(3).all()

    return render_template("index.html",
                           vagas_internas=vagas_internas,
                           vagas_externas=vagas_externas,
                           noticias=noticias,
                           dicas=dicas,
                           fav_ids=ids_favoritos_do_estudante())

# LOGIN
@app.route("/login", methods=["GET","POST"], endpoint="login")
def login_view():
    if request.method == "POST":
        email = request.form.get("email"); senha = request.form.get("senha")
        u = Utilizador.query.filter_by(email=email).first()
        if u and u.verificar_senha(senha):
            session.update({"utilizador_id":u.id,"nome":u.nome,"tipo":u.tipo})
            if u.tipo=="empresa": return redirect(url_for("pagina_empresa"))
            if u.tipo=="admin": return redirect(url_for("pagina_admin"))
            return redirect(url_for("pagina_vagas"))
        return render_template("login.html", erro="Credenciais inválidas")
    return render_template("login.html")

# REGISTO
@app.route("/registo", methods=["GET","POST"], endpoint="registo")
def registo():
    erro = None
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        tipo = request.form.get("tipo")

        # Verifica se email já existe
        if Utilizador.query.filter_by(email=email).first():
            erro = "Já existe conta com este email."
        else:
            senha_hash = generate_password_hash(senha)

            novo = Utilizador(nome=nome, email=email, senha_hash=senha_hash, tipo=tipo)

            if tipo == "empresa":
                nif = request.form.get("nif")
                if not nif or not nif.startswith("5"):
                    erro = "NIF inválido. Empresas em Portugal começam com 5."
                else:
                    novo.nif = nif
                    novo.nome_empresa = request.form.get("nome_empresa")
                    novo.codigo_postal = request.form.get("codigo_postal")
                    novo.distrito = request.form.get("distrito")
                    novo.telefone = request.form.get("telefone")

                    # email_empresa pode ser usado no lugar do email principal
                    email_empresa = request.form.get("email_empresa")
                    if email_empresa:
                        novo.email = email_empresa

                    # Upload do logo
                    ficheiro = request.files.get("logo_empresa")
                    if ficheiro and ficheiro.filename != "":
                        from werkzeug.utils import secure_filename
                        filename = secure_filename(ficheiro.filename)
                        caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                        ficheiro.save(caminho)
                        novo.logo_empresa = filename

            if not erro:
                db.session.add(novo)
                db.session.commit()
                return redirect(url_for("login"))

    return render_template("registo.html", erro=erro)

# LISTA VAGAS (com filtros simples e paginação)
@app.route("/vagas", endpoint="pagina_vagas")
def pagina_vagas():
    q = request.args.get("q", "").strip()
    cidade = request.args.get("cidade", "").strip()
    categoria = request.args.get("categoria", "").strip()
    horario = request.args.get("horario", "").strip()
    tipo = request.args.get("tipo", "").strip()
    empresa_nome = request.args.get("empresa", "").strip()
    natureza = request.args.get("natureza", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 9

    query = Vaga.query.order_by(Vaga.id.desc())

    # filtros
    if q:
        query = query.filter((Vaga.titulo.ilike(f"%{q}%")) | (Vaga.descricao.ilike(f"%{q}%")))
    if cidade:
        query = query.filter(Vaga.cidade.ilike(f"%{cidade}%"))
    if categoria:
        query = query.filter(Vaga.categoria == categoria)
    if horario:
        query = query.filter(Vaga.horario == horario)
    if tipo:
        query = query.filter(Vaga.tipo == tipo)
    if empresa_nome:
        query = query.join(Utilizador, Vaga.empresa_id == Utilizador.id).filter(
            Utilizador.nome_empresa.ilike(f"%{empresa_nome}%")
        )
    if natureza == "interna":
        query = query.filter(Vaga.externa == False)
    elif natureza == "externa":
        query = query.filter(Vaga.externa == True)

    total = query.count()
    vagas = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()

    # Distritos fixos (Portugal)
    distritos = [
        "Aveiro","Beja","Braga","Bragança","Castelo Branco","Coimbra","Évora","Faro",
        "Guarda","Leiria","Lisboa","Portalegre","Porto","Santarém","Setúbal",
        "Viana do Castelo","Vila Real","Viseu",
        "Região Autónoma dos Açores","Região Autónoma da Madeira"
    ]

    # Categorias fixas (SRS)
    categorias = [
        "Administração / Secretariado","Agricultura / Florestas / Pescas","Arquitectura / Design",
        "Artes / Entretenimento / Media","Banca / Seguros / Serviços Financeiros","Beleza / Moda / Bem Estar",
        "Call Center / Help Desk","Comercial / Vendas","Comunicação Social / Media","Conservação / Manutenção / Técnica",
        "Construção Civil","Contabilidade / Finanças","Desporto / Ginásios","Direito / Justiça",
        "Educação / Formação","Engenharia (Ambiente)","Engenharia (Civil)","Engenharia (Eletrotécnica)",
        "Engenharia (Mecânica)","Engenharia (Química / Biologia)","Farmácia / Biotecnologia",
        "Gestão de Empresas / Economia","Gestão RH","Hotelaria / Turismo","Imobiliário",
        "Indústria / Produção","Informática (Análise de Sistemas)","Informática (Formação)",
        "Informática (Gestão de Redes)","Informática (Internet)","Informática (Multimédia)",
        "Informática (Programação)","Informática (Técnico de Hardware)","Informática (Comercial / Gestor de Conta)",
        "Limpezas / Domésticas","Lojas / Comércio / Balcão","Publicidade / Marketing","Relações Públicas",
        "Restauração / Bares / Pastelarias","Saúde / Medicina / Enfermagem","Serviços Sociais",
        "Serviços Técnicos","Telecomunicações","Transportes / Logística"
    ]

    # Empresas da BD
    empresas = [e.nome_empresa for e in Utilizador.query.filter_by(tipo="empresa").all() if e.nome_empresa]

    return render_template(
        "vagas.html",
        vagas=vagas,
        total=total,
        pagina=pagina,
        tem_prev=pagina > 1,
        tem_next=(pagina * por_pagina) < total,
        filtros={
            "q": q,
            "cidade": cidade,
            "categoria": categoria,
            "horario": horario,
            "tipo": tipo,
            "empresa": empresa_nome,
            "natureza": natureza,
        },
        cidades=distritos,
        categorias=categorias,
        empresas=empresas,
        fav_ids=ids_favoritos_do_estudante(),
    )

# DETALHES + candidatura (internas)
@app.route("/vaga/<int:vaga_id>", methods=["GET","POST"], endpoint="detalhes_vaga")
def detalhes_vaga(vaga_id):
    vaga = Vaga.query.get_or_404(vaga_id)
    erro, sucesso, aviso = None, False, None

    if request.method == "POST":
        if session.get("tipo") != "estudante":
            return redirect(url_for("login"))

        # Verifica se já existe candidatura para esta vaga
        ja = Candidatura.query.filter_by(
            estudante_id=session["utilizador_id"], vaga_id=vaga.id
        ).first()
        if ja:
            aviso = f"{session['nome']}, já tens uma candidatura feita nessa vaga. Volte a tentar noutra e apenas aguarda o feedback do RH da empresa. Obrigado!"
        else:
            ficheiro = request.files.get("cv")
            if not ficheiro or ficheiro.filename == "":
                erro = "Seleciona um ficheiro."
            elif not allowed_file(ficheiro.filename):
                erro = "Aceites: PDF/DOC/DOCX."
            else:
                nome = secure_filename(ficheiro.filename)
                caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome)
                ficheiro.save(caminho)
                db.session.add(Candidatura(
                    estudante_id=session["utilizador_id"],
                    vaga_id=vaga.id,
                    ficheiro_cv=nome
                ))
                db.session.commit()
                sucesso = True

    return render_template(
        "detalhes_vaga.html",
        vaga=vaga,
        erro_upload=erro,
        sucesso=sucesso,
        aviso=aviso,
        fav_ids=ids_favoritos_do_estudante()
    )

# FAVORITOS
@app.route("/favoritar/<int:vaga_id>", methods=["POST"], endpoint="favoritar")
def favoritar(vaga_id):
    if session.get("tipo")!="estudante": return redirect(url_for("login"))
    vaga=Vaga.query.get_or_404(vaga_id)
    f=Favorito.query.filter_by(estudante_id=session["utilizador_id"], vaga_id=vaga.id).first()
    if f: db.session.delete(f)
    else: db.session.add(Favorito(estudante_id=session["utilizador_id"], vaga_id=vaga.id))
    db.session.commit()
    return redirect(request.referrer or url_for("pagina_vagas"))

@app.route("/favoritos", endpoint="pagina_favoritos")
def pagina_favoritos():
    if session.get("tipo")!="estudante": return redirect(url_for("login"))
    favoritos=(Favorito.query.filter_by(estudante_id=session["utilizador_id"])
               .join(Vaga, Favorito.vaga_id==Vaga.id).order_by(Favorito.id.desc()).all())
    return render_template("favoritos.html", favoritos=favoritos)

@app.route("/candidaturas", endpoint="minhas_candidaturas")
def minhas_candidaturas():
    if session.get("tipo")!="estudante": return redirect(url_for("login"))
    cands=Candidatura.query.filter_by(estudante_id=session["utilizador_id"]).all()
    return render_template("candidaturas.html", candidaturas=cands)

# EMPRESA
@app.route("/empresa", endpoint="pagina_empresa")
def pagina_empresa():
    if session.get("tipo")!="empresa": return redirect(url_for("login"))
    return render_template("empresa.html")


@app.route("/publicar", methods=["GET","POST"], endpoint="publicar_vaga")
def publicar_vaga():
    if session.get("tipo") not in ["empresa","admin"]: return redirect(url_for("login"))
    if request.method=="POST":
        vaga=Vaga(
            titulo=request.form.get("titulo"), categoria=request.form.get("categoria") or None,
            descricao=request.form.get("descricao"), cidade=request.form.get("cidade") or None,
            horario=request.form.get("horario") or None, tipo=request.form.get("tipo") or None,
            externa=False, empresa_id=session.get("utilizador_id")
        )
        db.session.add(vaga); db.session.commit()
        return redirect(url_for("minhas_vagas"))
    return render_template("publicar_vaga.html")

@app.route("/minhas_vagas", endpoint="minhas_vagas")
def minhas_vagas():
    if session.get("tipo")!="empresa": return redirect(url_for("login"))
    vagas=Vaga.query.filter_by(empresa_id=session["utilizador_id"]).order_by(Vaga.id.desc()).all()
    return render_template("minhas_vagas.html", vagas=vagas)

@app.route("/editar_vaga/<int:vaga_id>", methods=["GET","POST"], endpoint="editar_vaga")
def editar_vaga(vaga_id):
    if session.get("tipo")!="empresa": return redirect(url_for("login"))
    vaga=Vaga.query.get_or_404(vaga_id)
    if vaga.empresa_id!=session["utilizador_id"]: return redirect(url_for("minhas_vagas"))
    if request.method=="POST":
        vaga.titulo=request.form.get("titulo")
        vaga.categoria=request.form.get("categoria") or None
        vaga.descricao=request.form.get("descricao")
        vaga.cidade=request.form.get("cidade") or None
        vaga.horario=request.form.get("horario") or None
        vaga.tipo=request.form.get("tipo") or None
        db.session.commit(); return redirect(url_for("minhas_vagas"))
    return render_template("editar_vaga.html", vaga=vaga)

@app.route("/remover_vaga/<int:vaga_id>", methods=["POST"], endpoint="remover_vaga")
def remover_vaga(vaga_id):
    if session.get("tipo")!="empresa": return redirect(url_for("login"))
    vaga=Vaga.query.get_or_404(vaga_id)
    if vaga.empresa_id!=session["utilizador_id"]: return redirect(url_for("minhas_vagas"))
    for c in vaga.candidaturas:
        if c.ficheiro_cv:
            caminho=os.path.join(app.config["UPLOAD_FOLDER"], c.ficheiro_cv)
            if os.path.exists(caminho): os.remove(caminho)
    db.session.delete(vaga); db.session.commit()
    return redirect(url_for("minhas_vagas"))

@app.route("/gerir_candidaturas", endpoint="gerir_candidaturas")
def gerir_candidaturas():
    if session.get("tipo")!="empresa": return redirect(url_for("login"))
    cands=Candidatura.query.join(Vaga).filter(Vaga.empresa_id==session["utilizador_id"]).all()
    return render_template("gerir_candidaturas.html", candidaturas=cands)

# ADMIN (placeholder)
@app.route("/admin", endpoint="pagina_admin")
def pagina_admin():
    if session.get("tipo")!="admin": return redirect(url_for("login"))
    return render_template("admin.html")

# DOWNLOAD CV
@app.route("/uploads/<filename>", endpoint="download_cv")
def download_cv(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

# LOGOUT
@app.route("/logout", endpoint="logout")
def logout():
    session.clear()
    return redirect(url_for("pagina_inicial"))

@app.route("/estudante", endpoint="pagina_estudante")
def pagina_estudante():
    if session.get("tipo") != "estudante":
        return redirect(url_for("login"))
    return render_template("estudante.html")


@app.route("/perfil", methods=["GET", "POST"], endpoint="pagina_perfil")
def pagina_perfil():
    if session.get("tipo") != "estudante":
        return redirect(url_for("login"))

    estudante = Utilizador.query.get_or_404(session["utilizador_id"])
    erro, sucesso = None, False

    if request.method == "POST":
        estudante.nome = request.form.get("nome")
        estudante.email = request.form.get("email")

        # upload do CV principal
        ficheiro = request.files.get("cv_principal")
        if ficheiro and ficheiro.filename != "":
            from werkzeug.utils import secure_filename
            filename = secure_filename(ficheiro.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            ficheiro.save(caminho)
            estudante.cv_principal = filename

        db.session.commit()
        sucesso = True

    return render_template("perfil.html", estudante=estudante, erro=erro, sucesso=sucesso)

@app.route("/perfil_empresa", methods=["GET", "POST"], endpoint="pagina_perfil_empresa")
def pagina_perfil_empresa():
    if session.get("tipo") != "empresa":
        return redirect(url_for("login"))

    empresa = Utilizador.query.get_or_404(session["utilizador_id"])
    erro, sucesso = None, False

    if request.method == "POST":
        empresa.nome = request.form.get("nome")
        empresa.email = request.form.get("email")

        # upload de logotipo
        ficheiro = request.files.get("logo_empresa")
        if ficheiro and ficheiro.filename != "":
            from werkzeug.utils import secure_filename
            filename = secure_filename(ficheiro.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            ficheiro.save(caminho)
            empresa.logo_empresa = filename

        db.session.commit()
        sucesso = True

    return render_template("perfil_empresa.html", empresa=empresa, erro=erro, sucesso=sucesso)

@app.route("/perfil_admin", methods=["GET", "POST"], endpoint="pagina_perfil_admin")
def pagina_perfil_admin():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    admin = Utilizador.query.get_or_404(session["utilizador_id"])
    sucesso = False

    if request.method == "POST":
        admin.nome = request.form.get("nome")
        admin.email = request.form.get("email")
        admin.notas = request.form.get("notas")
        db.session.commit()
        sucesso = True

    return render_template("perfil_admin.html", admin=admin, sucesso=sucesso)

#----------------------------Gestão de Publicações (CRUD)
@app.route("/admin/publicacoes", endpoint="gestao_publicacoes")
def gestao_publicacoes():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))
    pubs = Publicacao.query.order_by(Publicacao.data_hora.desc()).all()
    return render_template("gestao_publicacoes.html", publicacoes=pubs)

@app.route("/admin/publicar", methods=["GET","POST"], endpoint="publicar_conteudo")
def publicar_conteudo():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        from werkzeug.utils import secure_filename
        titulo = request.form.get("titulo")
        tipo = request.form.get("tipo")
        conteudo = request.form.get("conteudo")
        foto = None

        ficheiro = request.files.get("foto")
        if ficheiro and ficheiro.filename != "":
            filename = secure_filename(ficheiro.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            ficheiro.save(caminho)
            foto = filename

        pub = Publicacao(
            titulo=titulo,
            autor_id=session["utilizador_id"],
            conteudo=conteudo,
            tipo=tipo,
            foto=foto
        )
        db.session.add(pub)
        db.session.commit()
        return redirect(url_for("gestao_publicacoes"))

    return render_template("publicar_conteudo.html")

@app.route("/admin/publicacao/<int:pub_id>/editar", methods=["GET","POST"], endpoint="editar_publicacao")
def editar_publicacao(pub_id):
    pub = Publicacao.query.get_or_404(pub_id)
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        pub.titulo = request.form.get("titulo")
        pub.tipo = request.form.get("tipo")
        pub.conteudo = request.form.get("conteudo")

        ficheiro = request.files.get("foto")
        if ficheiro and ficheiro.filename != "":
            from werkzeug.utils import secure_filename
            filename = secure_filename(ficheiro.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            ficheiro.save(caminho)
            pub.foto = filename

        db.session.commit()
        return redirect(url_for("gestao_publicacoes"))

    return render_template("editar_publicacao.html", pub=pub)

@app.route("/admin/publicacao/<int:pub_id>/remover", methods=["POST"], endpoint="remover_publicacao")
def remover_publicacao(pub_id):
    pub = Publicacao.query.get_or_404(pub_id)
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))
    db.session.delete(pub)
    db.session.commit()
    return redirect(url_for("gestao_publicacoes"))

@app.route("/noticias", endpoint="pagina_noticias")
def pagina_noticias():
    pubs = Publicacao.query.filter_by(tipo="noticia").order_by(Publicacao.data_hora.desc()).all()
    return render_template("pagina_noticias.html", publicacoes=pubs)

@app.route("/dicas", endpoint="pagina_dicas")
def pagina_dicas():
    pubs = Publicacao.query.filter_by(tipo="dica").order_by(Publicacao.data_hora.desc()).all()
    return render_template("pagina_dicas.html", publicacoes=pubs)

@app.route("/publicacao/<int:pub_id>", endpoint="detalhe_publicacao")
def detalhe_publicacao(pub_id):
    pub = Publicacao.query.get_or_404(pub_id)
    return render_template("detalhe_publicacao.html", pub=pub)


@app.route("/conteudos", endpoint="pagina_conteudos")
def pagina_conteudos():
    noticias = Publicacao.query.filter_by(tipo="noticia").order_by(Publicacao.data_hora.desc()).limit(5).all()
    dicas = Publicacao.query.filter_by(tipo="dica").order_by(Publicacao.data_hora.desc()).limit(5).all()
    mais_lidas = Publicacao.query.order_by(Publicacao.data_hora.asc()).limit(5).all()  # aqui poderíamos adicionar lógica de contagem de visualizações depois

    return render_template("pagina_conteudos.html", noticias=noticias, dicas=dicas, mais_lidas=mais_lidas)

@app.context_processor
def inject_publicacoes_recentes():
    from modelos.modelos import Publicacao
    recentes = Publicacao.query.order_by(Publicacao.data_hora.desc()).limit(3).all()
    return dict(publicacoes_recentes=recentes)

@app.route("/publicacao/<int:pub_id>/comentar", methods=["POST"], endpoint="comentar_publicacao")
def comentar_publicacao(pub_id):
    if session.get("tipo") != "estudante":
        return redirect(url_for("login"))

    conteudo = request.form.get("conteudo")
    if conteudo and conteudo.strip():
        comentario = Comentario(
            conteudo=conteudo.strip(),
            autor_id=session["utilizador_id"],
            publicacao_id=pub_id
        )
        db.session.add(comentario)
        db.session.commit()

        # Enviar e-mail para o admin
        pub = Publicacao.query.get_or_404(pub_id)
        autor = Utilizador.query.get(session["utilizador_id"]) #Utilizador.query.filter_by(tipo="admin").all()

        link = url_for("detalhe_publicacao", pub_id=pub_id, _external=True)

        msg = Message(
            subject=f"Novo comentário em: {pub.titulo}",
            recipients=["admin@adluc.pt"],  # <-- troca pelo e-mail real do admin
            body=f"""
Olá Admin,

O estudante {autor.nome} comentou na publicação "{pub.titulo}".

Comentário:
{conteudo[:200]}...

Veja em: {link}

--
Sistema adluc
"""
        )
        try:
            mail.send(msg)
            print("Notificação enviada para o admin")
        except Exception as e:
            print("Erro ao enviar e-mail:", e)

    return redirect(url_for("detalhe_publicacao", pub_id=pub_id))

@app.route("/api/empresas")
def api_empresas():
    termo = request.args.get("q", "").lower()
    empresas = Utilizador.query.filter_by(tipo="empresa").all()
    resultados = []

    for e in empresas:
        if termo in e.nome_empresa.lower():
            resultados.append({"id": e.id, "nome": e.nome_empresa})

    return jsonify(resultados)

@app.route("/api/vagas")
def api_vagas():
    q = request.args.get("q", "").lower()
    cidade = request.args.get("cidade", "").lower()
    categoria = request.args.get("categoria", "")
    horario = request.args.get("horario", "")
    tipo = request.args.get("tipo", "")
    empresa_nome = request.args.get("empresa", "").lower()
    natureza = request.args.get("natureza", "").lower()  # <-- novo filtro

    query = Vaga.query

    # filtros
    if q:
        query = query.filter(Vaga.titulo.ilike(f"%{q}%") | Vaga.descricao.ilike(f"%{q}%"))
    if cidade:
        query = query.filter(Vaga.cidade.ilike(f"%{cidade}%"))
    if categoria:
        query = query.filter(Vaga.categoria == categoria)
    if horario:
        query = query.filter(Vaga.horario == horario)
    if tipo:
        query = query.filter(Vaga.tipo == tipo)
    if empresa_nome:
        query = query.join(Utilizador, Vaga.empresa_id == Utilizador.id).filter(Utilizador.nome_empresa.ilike(f"%{empresa_nome}%"))
    if natureza == "interna":
        query = query.filter(Vaga.externa == False)
    elif natureza == "externa":
        query = query.filter(Vaga.externa == True)

    vagas = query.order_by(Vaga.id.desc()).limit(50).all()

    resultados = []
    for v in vagas:
        resultados.append({
            "id": v.id,
            "titulo": v.titulo,
            "descricao": (v.descricao[:120] + "...") if v.descricao else "",
            "categoria": v.categoria,
            "cidade": v.cidade,
            "horario": v.horario,
            "tipo": v.tipo,
            "externa": v.externa,
            "link": v.link_externo if v.externa else url_for("detalhes_vaga", vaga_id=v.id),
            "imagem": (
                url_for("static", filename="imagens/fallback_vaga.png")
                if v.externa else (
                    url_for("download_cv", filename=v.empresa.logo_empresa)
                    if v.empresa and v.empresa.logo_empresa else url_for("static", filename="imagens/fallback_vaga.png")
                )
            )
        })
    return jsonify(resultados)

@app.route("/sobre", endpoint="pagina_sobre")
def pagina_sobre():
    return render_template("sobre.html")

@app.route("/termos", endpoint="pagina_termos")
def pagina_termos():
    return render_template("termos.html")

@app.route("/contactos", endpoint="pagina_contactos")
def pagina_contactos():
    return render_template("contactos.html")

@app.route("/razoes", endpoint="pagina_razoes")
def pagina_razoes():
    return render_template("razoes.html")

@app.route("/precos", endpoint="pagina_precos")
def pagina_precos():
    return render_template("precos.html")

#postgresql://adluc_db_user:gEjfLb67nwshZr0j4dLHnjNyXP2FIKwH@dpg-d3cpfnqdbo4c73edafd0-a.oregon-postgres.render.com/adluc_db
#postgresql://adluc_db_user:gEjfLb67nwshZr0j4dLHnjNyXP2FIKwH@dpg-d3cpfnqdbo4c73edafd0-a/adluc_db
#psql postgresql://adluc_db_user:gEjfLb67nwshZr0j4dLHnjNyXP2FIKwH@dpg-d3cpfnqdbo4c73edafd0-a/adluc_db


# GERIR UTILIZADORES
@app.route("/admin/utilizadores", endpoint="gerir_utilizadores")
def gerir_utilizadores():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))
    utilizadores = Utilizador.query.order_by(Utilizador.id.desc()).all()
    return render_template("gerir_utilizadores.html", utilizadores=utilizadores)

@app.route("/admin/utilizador/<int:utilizador_id>/editar", methods=["GET","POST"], endpoint="editar_utilizador")
def editar_utilizador(utilizador_id):
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    u = Utilizador.query.get_or_404(utilizador_id)
    erro, sucesso = None, False

    if request.method == "POST":
        try:
            u.nome = request.form.get("nome")
            u.email = request.form.get("email")
            u.tipo = request.form.get("tipo")
            db.session.commit()
            sucesso = True
        except Exception as e:
            erro = f"Ocorreu um erro: {e}"

    return render_template("editar_utilizador.html", utilizador=u, erro=erro, sucesso=sucesso)

@app.route("/admin/utilizador/<int:utilizador_id>/remover", methods=["POST"], endpoint="remover_utilizador")
def remover_utilizador(utilizador_id):
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))
    u = Utilizador.query.get_or_404(utilizador_id)
    db.session.delete(u)
    db.session.commit()
    return redirect(url_for("gerir_utilizadores"))

@app.route("/admin/relatorios", endpoint="relatorios")
def relatorios():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    total_utilizadores = Utilizador.query.count()
    total_estudantes = Utilizador.query.filter_by(tipo="estudante").count()
    total_empresas = Utilizador.query.filter_by(tipo="empresa").count()
    total_admins = Utilizador.query.filter_by(tipo="admin").count()

    total_vagas = Vaga.query.count()
    vagas_internas = Vaga.query.filter_by(externa=False).count()
    vagas_externas = Vaga.query.filter_by(externa=True).count()

    total_candidaturas = Candidatura.query.count()
    media_candidaturas = round(total_candidaturas / total_vagas, 2) if total_vagas else 0

    total_favoritos = Favorito.query.count()

    total_noticias = Publicacao.query.filter_by(tipo="noticia").count()
    total_dicas = Publicacao.query.filter_by(tipo="dica").count()

    return render_template(
        "relatorios.html",
        total_utilizadores=total_utilizadores,
        total_estudantes=total_estudantes,
        total_empresas=total_empresas,
        total_admins=total_admins,
        total_vagas=total_vagas,
        vagas_internas=vagas_internas,
        vagas_externas=vagas_externas,
        total_candidaturas=total_candidaturas,
        media_candidaturas=media_candidaturas,
        total_favoritos=total_favoritos,
        total_noticias=total_noticias,
        total_dicas=total_dicas,
    )

@app.route("/admin/configuracoes", endpoint="pagina_configuracoes")
def pagina_configuracoes():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))
    return render_template("configuracoes.html")

@app.route("/admin/alterar_senha", methods=["POST"], endpoint="alterar_senha_admin")
def alterar_senha_admin():
    if session.get("tipo") != "admin":
        return redirect(url_for("login"))

    admin = Utilizador.query.get_or_404(session["utilizador_id"])
    senha_atual = request.form.get("senha_atual", "")
    nova_senha = request.form.get("nova_senha", "")

    if not admin.verificar_senha(senha_atual):
        # renderiza o perfil com mensagem de erro (ou redirect)
        return render_template("perfil_admin.html", admin=admin, senha_erro="Senha atual incorreta.")
    if len(nova_senha) < 8:
        return render_template("perfil_admin.html", admin=admin, senha_erro="A nova senha deve ter pelo menos 8 caracteres.")
    admin.senha_hash = generate_password_hash(nova_senha)
    db.session.commit()
    return render_template("perfil_admin.html", admin=admin, senha_sucesso=True)

@app.route("/comentario/<int:coment_id>/remover", methods=["POST"], endpoint="remover_comentario")
def remover_comentario(coment_id):
    comentario = Comentario.query.get_or_404(coment_id)
    if session.get("tipo") == "admin":
        db.session.delete(comentario)
        db.session.commit()
    return redirect(url_for("detalhe_publicacao", pub_id=comentario.publicacao_id))

if __name__ == "__main__":
    app.run(debug=True)