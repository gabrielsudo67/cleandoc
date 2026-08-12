"""
app.py — Removedor de Marca d'Água (versão premium com login e planos).

Execução:
    streamlit run app.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import streamlit as st
from PIL import Image

from src import auth
from src import exporters
from src import payments
from src import stats
from src.plans import FREE, PREMIUM, get_plan
from src.engine.image_cleaner import CleanConfig, clean_image
from src.engine.pdf_cleaner import (
    clean_pdf,
    is_pdf_scanned,
    pdf_page_count,
    render_pdf_pages,
    render_pdf_preview,
)

APP_NAME = "CleanDoc"
TAGLINE = "Remova marcas d'água de documentos e imagens com qualidade profissional."

_LEGAL_DIR = Path(__file__).resolve().parent / "legal"


def load_legal(filename: str) -> str:
    """Carrega um documento legal (Markdown) da pasta legal/."""
    try:
        return (_LEGAL_DIR / filename).read_text(encoding="utf-8")
    except Exception:
        return "Documento indisponível no momento."

# --------------------------------------------------------------------------- #
# Configuração da página
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title=f"{APP_NAME} — Removedor de Marca d'Água",
    page_icon="🧼",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    @keyframes floatGlow {
        0%   { transform: translate(0,0) scale(1); opacity:.9; }
        50%  { transform: translate(2%, 3%) scale(1.05); opacity:1; }
        100% { transform: translate(0,0) scale(1); opacity:.9; }
    }
    @keyframes fadeUp {
        from { opacity:0; transform: translateY(14px); }
        to   { opacity:1; transform: translateY(0); }
    }

    .stApp {
        background:
            radial-gradient(1200px 600px at 12% -10%, #1c1d20 0%, transparent 55%),
            radial-gradient(1000px 520px at 100% 0%, #212226 0%, transparent 50%),
            radial-gradient(900px 500px at 50% 120%, #161618 0%, transparent 55%),
            #060607;
    }
    .stApp::before {
        content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
        background: radial-gradient(600px 300px at 20% 30%, rgba(200,204,214,.06), transparent 60%),
                    radial-gradient(500px 260px at 85% 20%, rgba(160,164,174,.06), transparent 60%);
        animation: floatGlow 14s ease-in-out infinite;
    }
    .block-container { padding-top: 2.4rem; max-width: 1200px; position:relative; z-index:1;
        animation: fadeUp .5s ease both; }
    h1,h2,h3 { color:#f4f5f7; letter-spacing:-0.02em; }

    .brand { display:flex; align-items:center; gap:.6rem; font-weight:800;
             font-size:1.35rem; color:#fff; }
    .brand .dot { width:12px; height:12px; border-radius:50%;
                  background:linear-gradient(135deg,#9a9ea8,#e6e8ec);
                  box-shadow:0 0 18px rgba(230,232,236,.55); animation: floatGlow 4s ease-in-out infinite; }

    .hero { text-align:center; padding: 1.5rem 0 0.5rem; }
    .hero h1 { font-size: 3.1rem; margin-bottom:.4rem;
        background:linear-gradient(90deg,#ffffff,#c9ccd3 60%,#8b8e96);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .hero p { color:#9a9da6; font-size:1.15rem; max-width:640px; margin:0 auto; }

    .glass { background:rgba(20,21,23,.75); border:1px solid #2a2b2f;
             border-radius:18px; padding:1.4rem 1.6rem; backdrop-filter: blur(9px);
             transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease; }
    .glass:hover { transform: translateY(-4px);
             border-color:#484a50; box-shadow:0 16px 40px rgba(0,0,0,.55); }

    .pill { display:inline-block; padding:3px 12px; border-radius:999px;
            font-size:.75rem; font-weight:700; }
    .pill-free { background:#212327; color:#9a9da6; }
    .pill-premium { background:linear-gradient(90deg,#d0d3da,#f2f3f5); color:#0a0a0b;
            box-shadow:0 0 16px rgba(230,232,236,.35); }

    .price { font-size:2.4rem; font-weight:800; color:#fff; }
    .price small { font-size:1rem; color:#9a9da6; font-weight:500; }

    .stButton button, .stDownloadButton button {
        border-radius:11px; font-weight:700; border:1px solid #3a3b40; color:#f4f5f7;
        background:linear-gradient(90deg,#26272b,#3a3c42); background-size:180% 100%;
        transition: transform .18s ease, box-shadow .18s ease, background-position .4s ease, border-color .2s ease; }
    .stButton button:hover, .stDownloadButton button:hover {
        transform: translateY(-2px); background-position:100% 0; border-color:#6b6d75;
        box-shadow:0 10px 26px rgba(0,0,0,.5); }
    .stButton button:active, .stDownloadButton button:active { transform: translateY(0); }

    [data-testid="stFileUploaderDropzone"] {
        border:1.6px dashed #3a3b40; border-radius:14px; background:#0d0d0f;
        transition: border-color .25s ease, background .25s ease; }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color:#8b8e96; background:#111113; }

    .stTabs [data-baseweb="tab"] { transition: color .2s ease; }
    [data-testid="stImage"] img { border-radius:10px;
        transition: transform .25s ease, box-shadow .25s ease; }
    [data-testid="stImage"] img:hover { transform: scale(1.01);
        box-shadow:0 10px 30px rgba(0,0,0,.6); }

    footer, #MainMenu { visibility:hidden; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Estado de sessão
# --------------------------------------------------------------------------- #
if "user_email" not in st.session_state:
    st.session_state.user_email = None


def current_user() -> dict | None:
    if st.session_state.user_email:
        return auth.get_user(st.session_state.user_email)
    return None


def logout():
    st.session_state.user_email = None


def _base_url() -> str:
    """URL pública do app (para o retorno do Mercado Pago)."""
    try:
        return str(st.secrets["app"]["base_url"]).strip() or "http://localhost:8501"
    except Exception:
        return "http://localhost:8501"


def _admin_emails() -> set[str]:
    """E-mails com acesso ao Painel do Dono (definidos em secrets [app].admin_email)."""
    try:
        raw = st.secrets["app"]["admin_email"]
        return {e.strip().lower() for e in str(raw).split(",") if e.strip()}
    except Exception:
        return set()


def is_admin(email: str) -> bool:
    return email.strip().lower() in _admin_emails()


def handle_payment_return():
    """
    Ao voltar do checkout do Mercado Pago, a URL traz payment_id/status.
    Confirmamos o pagamento pela API e liberamos o Premium para o e-mail pago.
    Como o retorno é uma nova página, re-autenticamos pelo external_reference.
    """
    params = st.query_params
    payment_id = params.get("payment_id") or params.get("collection_id")
    if not payment_id:
        return
    approved, status, email = payments.verify_payment(payment_id)
    if approved and email:
        auth.set_plan(email, "premium")
        st.session_state.user_email = email  # re-loga o usuário que pagou
        st.session_state["_pay_msg"] = ("success",
            "Pagamento aprovado! Seu plano Premium foi liberado. 🎉")
    else:
        st.session_state["_pay_msg"] = ("warning",
            f"Pagamento ainda não confirmado (status: {status}). "
            "Se você pagou via Pix/boleto, pode levar alguns minutos.")
    st.query_params.clear()


# =========================================================================== #
# TELA 1 — Entrada (não autenticado): hero + login/cadastro + planos
# =========================================================================== #
def render_landing():
    st.markdown(
        f'<div class="brand"><span class="dot"></span>{APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="hero"><h1>Documentos limpos em segundos</h1>'
        f'<p>{TAGLINE}</p></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    col_form, col_plans = st.columns([1.1, 1], gap="large")

    # ---- Login / Cadastro ----
    with col_form:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["Entrar", "Criar conta"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("E-mail", key="login_email")
                password = st.text_input("Senha", type="password", key="login_pw")
                submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                ok, msg = auth.authenticate(email, password)
                if ok:
                    st.session_state.user_email = email.strip().lower()
                    st.rerun()
                else:
                    st.error(msg)

        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Nome", key="su_name")
                email_s = st.text_input("E-mail", key="su_email")
                pw_s = st.text_input("Senha (mín. 6 caracteres)", type="password", key="su_pw")
                accept = st.checkbox(
                    "Li e aceito os Termos de Uso e a Política de Privacidade",
                    key="su_accept",
                )
                submitted_s = st.form_submit_button("Criar conta grátis", use_container_width=True)
            if submitted_s:
                if not accept:
                    st.error("Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar a conta.")
                else:
                    ok, msg = auth.register(email_s, pw_s, name)
                    if ok:
                        st.session_state.user_email = email_s.strip().lower()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            st.caption("Ao criar conta, você concorda com os documentos disponíveis no rodapé desta página.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Cartões de planos ----
    with col_plans:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.markdown('<span class="pill pill-free">Grátis</span>', unsafe_allow_html=True)
        st.markdown('<div class="price">R$ 0</div>', unsafe_allow_html=True)
        for p in FREE.perks:
            st.markdown(f"✓ {p}")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="pill pill-premium">Premium</span>', unsafe_allow_html=True)
        _valor = f"R$ {PREMIUM.price:.2f}".replace(".", ",")
        st.markdown(
            f'<div class="price">{_valor} '
            f'<small>pagamento único</small></div>',
            unsafe_allow_html=True,
        )
        for p in PREMIUM.perks:
            st.markdown(f"✓ {p}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Rodapé legal ----
    render_legal_footer()


def render_legal_footer():
    """Rodapé com os documentos legais (LGPD/CDC)."""
    st.divider()
    st.caption(f"© 2026 {APP_NAME} · Documentos legais")
    with st.expander("📄 Política de Privacidade"):
        st.markdown(load_legal("privacidade.md"))
    with st.expander("📄 Termos de Uso"):
        st.markdown(load_legal("termos.md"))
    with st.expander("📄 Política de Cookies"):
        st.markdown(load_legal("cookies.md"))


# =========================================================================== #
# Ferramenta (autenticado)
# =========================================================================== #
def render_app(user: dict):
    plan = get_plan(user["plan"])

    # ---- Barra lateral ----
    with st.sidebar:
        st.markdown(
            f'<div class="brand"><span class="dot"></span>{APP_NAME}</div>',
            unsafe_allow_html=True,
        )
        pill = "pill-premium" if plan.key == "premium" else "pill-free"
        st.markdown(
            f'Olá, **{user["name"]}**<br>'
            f'<span class="pill {pill}">Plano {plan.name}</span>',
            unsafe_allow_html=True,
        )
        if st.button("Sair", use_container_width=True):
            logout(); st.rerun()

        st.divider()
        st.header("⚙️ Ajustes")
        sensitivity = st.slider("Sensibilidade da limpeza", 0.0, 1.0, 0.5, 0.05,
            help="Mais alta remove marcas d'água mais fortes.")
        keep_dark = st.toggle("Manter assinaturas / texto escuro", value=True)

        st.subheader("Formato de saída")
        out_format = st.radio("Exportar como", plan.formats, horizontal=True)
        if plan.key == "free":
            st.caption("🔒 PDF e Word são exclusivos do Premium.")
        jpg_quality = st.slider("Qualidade JPG", 60, 100, 92, 1) if out_format == "JPG" else 92

        with st.expander("Avançado"):
            use_adaptive = st.toggle("Limiarização adaptativa", value=True)
            dark_threshold = st.slider("Limiar de escuro", 0, 255, 110, 5)
            pdf_dpi = st.select_slider("Resolução do PDF (DPI)",
                options=[100, 120, 150, 200, 300], value=150)
            force_raster = st.toggle("Forçar rasterização do PDF", value=False)

        st.divider()
        if plan.key == "free":
            st.markdown("**🔓 Quer mais?**")
            st.caption(f"Premium ({PREMIUM.price_label}): até {PREMIUM.max_file_mb}MB "
                       f"e lote de {PREMIUM.max_files_batch} arquivos.")
            if st.button("⭐ Obter Premium", use_container_width=True):
                st.session_state.show_upgrade = True

        if is_admin(user["email"]):
            st.divider()
            if st.button("📊 Painel do Dono", use_container_width=True):
                st.session_state.show_admin = True
                st.rerun()

        st.caption("Processamento 100% local no servidor. Arquivos não são compartilhados.")

    config = CleanConfig(sensitivity=sensitivity, keep_dark=keep_dark,
                         use_adaptive_threshold=use_adaptive, dark_threshold=dark_threshold)

    # ---- Modal de upgrade (Mercado Pago) ----
    if st.session_state.get("show_upgrade"):
        with st.container():
            st.info(
                f"**Premium por {PREMIUM.price_label}** — pagamento via Mercado Pago "
                "(Pix, cartão ou boleto). Acesso vitalício."
            )
            if payments.is_configured():
                ok, url = payments.create_preference(
                    user_email=user["email"], plan_name=PREMIUM.name,
                    price=PREMIUM.price, base_url=_base_url(),
                )
                if ok:
                    st.link_button("💳 Pagar com Mercado Pago", url, use_container_width=True)
                    st.caption("Você será levado ao ambiente seguro do Mercado Pago e "
                               "voltará ao CleanDoc após o pagamento.")
                else:
                    st.error(url)
                if st.button("Fechar"):
                    st.session_state.show_upgrade = False; st.rerun()
            else:
                st.warning(
                    "Pagamento ainda não configurado. Cole seu **Access Token** do "
                    "Mercado Pago em `.streamlit/secrets.toml` para ativar a cobrança real."
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Fechar"):
                        st.session_state.show_upgrade = False; st.rerun()
                with c2:
                    if st.button("Ativar (modo teste)"):
                        auth.set_plan(user["email"], "premium")
                        st.session_state.show_upgrade = False
                        st.success("Plano Premium ativado (teste)."); st.rerun()

    # ---- Cabeçalho ----
    st.markdown(
        f'<div class="hero"><h1>Removedor de Marca d\'Água</h1>'
        f'<p>Envie seus arquivos e baixe-os limpos.</p></div>',
        unsafe_allow_html=True,
    )

    # ---- Upload (limites por plano) ----
    allow_multiple = plan.batch
    label = ("Arraste e solte aqui — vários arquivos permitidos"
             if allow_multiple else "Arraste e solte 1 arquivo aqui")
    uploaded = st.file_uploader(label, type=["pdf", "png", "jpg", "jpeg"],
                                accept_multiple_files=allow_multiple)

    if not uploaded:
        st.info(f"👆 Envie {'um ou mais arquivos' if allow_multiple else 'um arquivo'} "
                f"**PDF, PNG ou JPG** (até {plan.max_file_mb} MB cada).")
        return

    files = uploaded if isinstance(uploaded, list) else [uploaded]

    # trava de lote para plano grátis
    if not plan.batch and len(files) > 1:
        files = files[:1]

    # trava de tamanho por arquivo
    valid_files = []
    for f in files:
        size_mb = f.size / (1024 * 1024)
        if size_mb > plan.max_file_mb:
            st.error(
                f"❌ **{f.name}** tem {size_mb:.1f} MB — acima do limite de "
                f"{plan.max_file_mb} MB do plano {plan.name}. "
                + ("Assine o Premium para enviar arquivos maiores." if plan.key == "free" else "")
            )
        else:
            valid_files.append(f)
    if not valid_files:
        return

    # ---- Processamento ----
    # No plano grátis, documentos multipágina em formato de imagem viram .zip
    # (nunca PDF), preservando a exclusividade de PDF/Word para o Premium.
    img_fallback = "pdf" if plan.key == "premium" else "zip"

    results = []
    progress = st.progress(0.0, text="Iniciando…")
    for i, f in enumerate(valid_files, start=1):
        data = f.read()
        is_pdf = f.name.lower().rsplit(".", 1)[-1] == "pdf"
        stem = f.name.rsplit(".", 1)[0]
        progress.progress(i / len(valid_files), text=f"Limpando {f.name} ({i}/{len(valid_files)})…")
        try:
            if is_pdf:
                scanned = is_pdf_scanned(data)
                badge = "Digitalizado (imagem)" if scanned else "Vetorial (nativo)"
                before = render_pdf_preview(data, 0, dpi=120)
                cleaned_pdf_bytes = clean_pdf(data, config, dpi=pdf_dpi, force_raster=force_raster)
                cleaned_images = render_pdf_pages(cleaned_pdf_bytes, dpi=pdf_dpi)
                after = cleaned_images[0]
            else:
                original = Image.open(io.BytesIO(data))
                cleaned_img = clean_image(original, config)
                before, after, badge = original, cleaned_img, "Imagem"
                cleaned_pdf_bytes = None
                cleaned_images = [cleaned_img]

            out_name, out_bytes, mime, note = exporters.build_output(
                out_format, cleaned_images,
                is_pdf_input=is_pdf, cleaned_pdf_bytes=cleaned_pdf_bytes,
                stem=stem, jpg_quality=jpg_quality,
                multipage_image_fallback=img_fallback,
            )
            results.append(dict(name=f.name, out_name=out_name, out_bytes=out_bytes,
                                before=before, after=after, badge=badge, is_pdf=is_pdf,
                                mime=mime, note=note, error=None))
        except Exception as exc:
            results.append(dict(name=f.name, error=str(exc)))
    progress.empty()

    ok = [r for r in results if not r.get("error")]
    st.success(f"Concluído: {len(ok)} de {len(results)} arquivo(s).")

    # download em lote (premium com >1 arquivo)
    if plan.batch and len(ok) > 1:
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in ok:
                zf.writestr(r["out_name"], r["out_bytes"])
        st.download_button(f"⬇️ Baixar todos ({len(ok)}) em .zip", zbuf.getvalue(),
                           "documentos_limpos.zip", "application/zip", use_container_width=True)
        st.divider()

    for idx, r in enumerate(results):
        if r.get("error"):
            st.error(f"❌ **{r['name']}** — {r['error']}")
            continue
        with st.expander(f"📄 {r['name']}", expanded=(len(results) == 1)):
            st.markdown(f'<span class="pill pill-free">{r["badge"]}</span>', unsafe_allow_html=True)
            cb, ca = st.columns(2, gap="large")
            with cb:
                st.subheader("Antes"); st.image(r["before"], use_container_width=True)
            with ca:
                st.subheader("Depois"); st.image(r["after"], use_container_width=True)
            if r.get("note"):
                st.caption(f"ℹ️ {r['note']}")
            st.download_button(f"⬇️ Baixar {r['out_name']}", r["out_bytes"], r["out_name"],
                               r["mime"], use_container_width=True, key=f"dl_{idx}")

    render_legal_footer()


# =========================================================================== #
# Painel do Dono (somente admin)
# =========================================================================== #
def render_admin_panel():
    st.markdown(
        '<div class="hero"><h1>📊 Painel do Dono</h1>'
        '<p>Visão geral do CleanDoc — visível apenas para você.</p></div>',
        unsafe_allow_html=True,
    )
    users = stats.get_all_users()
    s = stats.summarize(users, PREMIUM.price)
    visits = stats.get_visit_count()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Cadastros", s["total"])
    c2.metric("⭐ Premium", s["premium"])
    c3.metric("💰 Receita estimada", f"R$ {s['revenue']:.2f}".replace(".", ","))
    c4.metric("📈 Conversão", f"{s['conversion']:.1f}%")

    if visits is not None:
        st.metric("🔢 Visitas ao site", visits)
    else:
        st.caption("🔢 Contador de visitas: crie a tabela `visits` no Supabase para ativar "
                   "(SQL fornecido pelo desenvolvedor).")

    by_day = stats.signups_by_day(users)
    if by_day:
        st.subheader("Cadastros por dia")
        try:
            import pandas as pd
            df = pd.DataFrame({"cadastros": list(by_day.values())},
                              index=list(by_day.keys()))
            st.bar_chart(df, color="#9a9da6")
        except Exception:
            st.write(by_day)

    with st.expander("Ver lista de cadastros"):
        rows = [{"E-mail": u.get("email"), "Nome": u.get("name"),
                 "Plano": u.get("plan", "free"), "Cadastro": str(u.get("created_at", ""))[:10]}
                for u in users]
        st.dataframe(rows, use_container_width=True)

    if st.button("← Voltar ao app"):
        st.session_state.show_admin = False
        st.rerun()


# =========================================================================== #
# Roteamento
# =========================================================================== #
handle_payment_return()  # confirma pagamento se voltamos do Mercado Pago

# Conta 1 visita por sessão (silencioso se a tabela `visits` não existir)
if not st.session_state.get("_visit_counted"):
    stats.record_visit()
    st.session_state["_visit_counted"] = True

_msg = st.session_state.pop("_pay_msg", None)
if _msg:
    kind, text = _msg
    (st.success if kind == "success" else st.warning)(text)

user = current_user()
if user is None:
    render_landing()
elif st.session_state.get("show_admin") and is_admin(user["email"]):
    render_admin_panel()
else:
    render_app(user)
