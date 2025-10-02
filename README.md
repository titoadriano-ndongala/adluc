**AdLuc – Plataforma de Emprego para Estudantes**

**Descrição do Projeto**

O AdLuc é uma plataforma web desenvolvida em Python (Flask) que conecta estudantes e empresas, permitindo gerir ofertas de emprego, estágios e bolsas de estudo de forma centralizada e acessível.

O nome AdLuc vem da fusão de Adriano e Lucas, autores do projeto, desenvolvido no âmbito do projeto final do curso de Python do IEFP (Instituto de Emprego e Formação Profissional).

O objetivo é fornecer uma solução moderna e acessível, que vá além dos tradicionais portais de emprego, oferecendo também notícias, dicas e gestão integrada de candidaturas.

**Funcionalidades Principais**

**Estudantes:**
Criar conta e gerir perfil.
Pesquisar e filtrar vagas (cidade, categoria, empresa, tipo, horário, natureza interna/externa).
Guardar vagas como favoritos.
Candidatar-se a vagas internas enviando o CV.
Consultar as suas candidaturas.

**Empresas:**
Criar conta com validação de NIF.
Publicar e gerir vagas (com logotipo da empresa).
Consultar candidaturas recebidas e descarregar CVs.
Administrador:
Gerir utilizadores (estudantes, empresas, admins).
Criar, editar e eliminar notícias e dicas.
Aceder a relatórios interativos com métricas (utilizadores, vagas, candidaturas).
Configurações do sistema (Em desenvolvimento).

**Vagas externas:**
Importação automática de vagas e bolsas através de RSS Feeds (Expresso Emprego, Huork, Euraxess, FCT, etc).
Atualização periódica via Scheduler (APScheduler) a cada 30 minutos.

**Tecnologias Utilizadas**
Backend: Python 3 + Flask
Frontend: HTML, CSS, JavaScript (Jinja2 para templates)
Base de Dados: SQLite (local) 
ORM: SQLAlchemy
Autenticação & Sessões: Flask-Login 
Feeds: Feedparser + Requests

**Instruções de Instalação e Uso**
Clonar o repositório
Criar ambiente virtual
Instalar dependências
Autores: Tito Adriano & Lucas Almeida
Projeto desenvolvido como trabalho final do curso de Python – IEFP


**Para teste**
**Lista de Estudantes**

Joao Caridade senha: 12345 --- joao@caridade
Joana Ricardo ---- joana@ricardo
Ana Dornas ---- ana@dornas
Hugo Vieira --- hugo@vieira

**ADMIN**
mail: tito@lucas
keyword: tito@lucas

**EMPRESA**
**Nelson Duarte** 
nelson@duarte 
Nelson Duarte Company
12345

**Frederico Manuel**
frederico@mauel
Grupo Frederico Manuel 
12345

**Joao Almeida**  
joao@almeida
Uniao Joáo Almeida
12345
--------------------------------------------------------------------