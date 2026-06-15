#!/usr/bin/env python3
"""Portal de Montagem de Fichas — Espaço Viva Academia
Uso: streamlit run portal/app.py
"""

import hashlib
import json
import logging
import os
import ssl
import socket
import time
import urllib.parse
import urllib.request
from pathlib import Path

import streamlit as st

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Espaço Viva — Montagem de Fichas",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)

WORKOUT_URL = "https://workoutservice-api.prd.g.actuar.cloud"
WORKOUT_HOST = "workoutservice-api.prd.g.actuar.cloud"
WORKOUT_IP = "34.8.55.176"
TOKEN_FILE = Path(
    os.environ.get(
        "ACTUAR_TOKEN_FILE",
        r"C:\musculação\scripts\token_state.json"
        if os.name == "nt"
        else str(Path(__file__).parent / "token_state.json")
    )
)
EMAIL = "drogafarto@gmail.com"
SENHA = "Pop12qwer*"
LOGIN_URL = "https://userservice-api.prd.g.actuar.cloud/Auth/Login"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("portal")

# Carregar mapa de exercícios local dos blocos
LOCAL_EXERCISES = {}
try:
    _json_path = Path(__file__).parent / "blocos_exercicios.json"
    if _json_path.exists():
        with open(_json_path, "r", encoding="utf-8") as _f:
            LOCAL_EXERCISES = json.load(_f)
    else:
        logger.warning("Arquivo blocos_exercicios.json não encontrado em %s", _json_path)
except Exception as _e:
    logger.error("Erro ao carregar blocos_exercicios.json: %s", _e)

# ══════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════

st.markdown(
    """
<style>
    .block-card {
        background: #1a1a2e !important;
        border: 1px solid #2a2a4a !important;
        border-radius: 12px !important;
        padding: 1.2rem 1.5rem !important;
        margin-bottom: 0.8rem !important;
    }
    .block-card h3 { color: #00ff88 !important; margin: 0 0 0.3rem 0 !important; }
    .block-card .meta { color: #8888aa !important; font-size: 0.85rem !important; }
    .badge {
        display: inline-block !important;
        padding: 0.15rem 0.6rem !important;
        border-radius: 100px !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-right: 0.4rem !important;
    }
    .badge-green { background: #0a3a1a !important; color: #00ff88 !important; }
    .badge-blue { background: #0a1a3a !important; color: #4da6ff !important; }
    .badge-orange { background: #3a2a0a !important; color: #ffaa00 !important; }
    .badge-red { background: #3a0a0a !important; color: #ff4444 !important; }
    .result-header {
        background: linear-gradient(135deg, #0a2a1a 0%, #0a1a2a 100%) !important;
        border: 2px solid #00ff88 !important;
        border-radius: 16px !important;
        padding: 2rem !important;
        margin-bottom: 1.5rem !important;
        text-align: center !important;
    }
    .result-header h2 { color: #00ff88 !important; margin: 0 !important; }
    .result-header p { color: #aaaacc !important; margin: 0.3rem 0 0 0 !important; }
    .stat-box {
        background: #111122 !important;
        border: 1px solid #2a2a4a !important;
        border-radius: 8px !important;
        padding: 0.8rem 1rem !important;
        text-align: center !important;
    }
    .stat-box .val { font-size: 1.4rem !important; font-weight: 700 !important; color: #00ff88 !important; }
    .stat-box .lbl { font-size: 0.75rem !important; color: #8888aa !important; }
    .rec-card {
        background: #1a1a2e !important;
        color: #ffffff !important;
        border-left: 3px solid #ffaa00 !important;
        border-radius: 0 8px 8px 0 !important;
        padding: 0.7rem 1rem !important;
        margin-bottom: 0.4rem !important;
    }
    .big-btn {
        background: #00ff88 !important;
        color: #000 !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        width: 100% !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════
#  SYNC CLIENT
# ══════════════════════════════════════════════════════════

_DNS_CACHE: dict[str, tuple[str, float]] = {}
_DNS_TTL = 300


def _resolve_doh(hostname: str) -> str:
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, ts = _DNS_CACHE[hostname]
        if now - ts < _DNS_TTL:
            return ip
    url = f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        for answer in data.get("Answer", []):
            if answer.get("type") == 1 and "data" in answer:
                _DNS_CACHE[hostname] = (answer["data"], now)
                return answer["data"]
    except Exception:
        pass
    return hostname


def _decode_chunked(body: bytes) -> bytes:
    """Decode HTTP/1.1 chunked transfer encoding operating on raw bytes."""
    result = bytearray()
    i = 0
    n = len(body)
    while i < n:
        crlf = body.find(b"\r\n", i)
        if crlf == -1:
            break
        size_line = body[i:crlf].split(b";", 1)[0].strip()
        if not size_line:
            i = crlf + 2
            continue
        try:
            size = int(size_line, 16)
        except ValueError:
            break
        if size == 0:
            break
        i = crlf + 2
        result.extend(body[i : i + size])
        i += size + 2
        if i > n:
            break
    return bytes(result)


def _raw_request(ip: str, hostname: str, request: bytes) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    sock = None
    ssock = None
    try:
        sock = socket.create_connection((ip, 443), timeout=15)
        ssock = ctx.wrap_socket(sock, server_hostname=hostname)
        ssock.sendall(request)
        response = b""
        while True:
            data = ssock.recv(4096)
            if not data:
                break
            response += data
    finally:
        if ssock:
            try:
                ssock.close()
            except Exception:
                pass
        elif sock:
            try:
                sock.close()
            except Exception:
                pass
    # Split headers and body as bytes
    sep = b"\r\n\r\n"
    sep_idx = response.find(sep)
    if sep_idx == -1:
        headers_bytes = response
        body = b""
    else:
        headers_bytes = response[:sep_idx]
        body = response[sep_idx + len(sep) :]
    headers = headers_bytes.decode("utf-8", errors="replace")
    status_line = headers.split("\r\n")[0]
    if "401" in status_line or "403" in status_line:
        raise PermissionError(f"{status_line}")
    headers_lower = headers.lower()
    is_chunked = "transfer-encoding:" in headers_lower and "chunked" in headers_lower
    content_length = 0
    for line in headers.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                content_length = 0
    if is_chunked:
        body = _decode_chunked(body)
    elif content_length > 0:
        body = body[:content_length]
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        pass
    try:
        return json.JSONDecoder().raw_decode(body.decode("utf-8", errors="replace"))[0]
    except json.JSONDecodeError:
        logger.error("Falha ao decodificar JSON: %s", body[:500])
        raise ValueError(f"JSON invalido: {body[:200]}")


def _get_token() -> str:
    if not TOKEN_FILE.exists():
        return _login_and_save()
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    token = data.get("token", "")
    if not token:
        return _login_and_save()
    return token


def _login_and_save() -> str:
    pw_hash = hashlib.md5((EMAIL.lower() + SENHA).encode()).hexdigest()
    payload = json.dumps(
        {"Email": EMAIL, "Password": pw_hash, "Origin": "actuar"}
    ).encode()
    hostname = (
        urllib.parse.urlparse(LOGIN_URL).hostname
        or "userservice-api.prd.g.actuar.cloud"
    )
    ip = WORKOUT_IP
    req = (
        f"POST /Auth/Login HTTP/1.1\r\n"
        f"Host: {hostname}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"Accept: application/json\r\n"
        f"Connection: close\r\n\r\n"
    ).encode() + payload
    result = _raw_request(ip, hostname, req)
    token = result.get("Token", "")
    if token:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"token": token, "captured_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f
            )
    return token


def api_get(endpoint: str, params: dict | None = None) -> dict:
    hostname: str = WORKOUT_HOST
    ip: str = WORKOUT_IP
    path = endpoint
    if params:
        path += "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    try:
        token = _get_token()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"Accept: application/json\r\n"
            f"Authorization: Bearer {token}\r\n"
            f"Origin: https://novo.actuar.com\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        return _raw_request(ip, hostname, req)
    except PermissionError:
        logger.info("Token expirado ou inválido (401/403). Tentando renovar...")
        token = _login_and_save()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"Accept: application/json\r\n"
            f"Authorization: Bearer {token}\r\n"
            f"Origin: https://novo.actuar.com\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        return _raw_request(ip, hostname, req)


# ══════════════════════════════════════════════════════════
#  CACHE DECORATOR (simple, no st.cache_data in older st)
# ══════════════════════════════════════════════════════════

_CACHE: dict[str, tuple[float, object]] = {}


def cached(ttl: int = 300):
    def deco(fn):
        def wrapper(*args, **kw):
            key = f"{fn.__name__}:{args}:{tuple(sorted(kw.items()))}"
            now = time.time()
            if key in _CACHE:
                ts, val = _CACHE[key]
                if now - ts < ttl:
                    return val
            val = fn(*args, **kw)
            _CACHE[key] = (now, val)
            return val

        return wrapper

    return deco


# ══════════════════════════════════════════════════════════
#  ASSEMBLY LOGIC (from tools.py)
# ══════════════════════════════════════════════════════════

TABELA_DECISAO = [
    ("Masc Iniciante Hipertrofia", 3, 45, "Full Body", ["AQ-001", "FB-166", "FB-167"]),
    (
        "Masc Iniciante Emagrecimento",
        3,
        45,
        "Full Body",
        ["AQ-001", "FB-172", "AE-271"],
    ),
    ("Fem Iniciante Hipertrofia", 3, 45, "Full Body", ["AQ-001", "FB-168", "FB-169"]),
    ("Fem Iniciante Emagrecimento", 3, 45, "Full Body", ["AQ-001", "FB-172", "EM-284"]),
    (
        "Masc Intermediario Hipertrofia",
        4,
        45,
        "Upper/Lower",
        ["AQ-003", "AQ-004", "UL-186", "UL-187", "UL-188", "UL-189"],
    ),
    (
        "Fem Intermediaria Hipertrofia",
        4,
        45,
        "Upper/Lower",
        ["AQ-003", "AQ-004", "UL-190", "UL-191", "GL-137"],
    ),
    (
        "Masc Intermediario Emagrecimento",
        4,
        45,
        "Upper/Lower",
        ["AQ-003", "AQ-004", "UL-186", "UL-187", "EM-281"],
    ),
    (
        "Masc Avancado Hipertrofia",
        6,
        60,
        "PPL",
        ["AQ-003", "AQ-004", "PP-206", "PB-216", "LG-226"],
    ),
    ("Qualquer Condicionamento", 3, 45, "Funcional", ["AQ-006", "FU-236", "AE-272"]),
    ("Qualquer HIIT", 3, 30, "HIIT", ["AQ-005", "HI-256"]),
    ("60+ Iniciante", 2, 35, "Full Body", ["AQ-002", "FB-173", "PA-161"]),
    ("Tempo Curto 30min", 3, 30, "Full Body Compacto", ["AQ-001", "FB-171"]),
]

VOLUME_POR_NIVEL = {
    "iniciante": (18, 20, 40),
    "intermediario": (22, 26, 50),
    "avancado": (26, 30, 60),
}


def _montar_heuristico(
    sexo: str, objetivo: str, nivel: str, frequencia: int, tempo: int
):
    blocos = ["AQ-001"]
    if objetivo == "hipertrofia":
        if nivel == "iniciante":
            blocos.extend(
                ["FB-166", "FB-167"] if sexo == "Masc" else ["FB-168", "FB-169"]
            )
            return ("Heurístico Hipertrofia Iniciante", 3, 45, "Full Body", blocos)
        elif nivel == "intermediario":
            return (
                "Heurístico Hipertrofia Intermediário",
                4,
                45,
                "Upper/Lower",
                ["AQ-003", "AQ-004", "UL-186", "UL-187", "UL-188", "UL-189"],
            )
        else:
            return (
                "Heurístico Hipertrofia Avançado",
                6,
                60,
                "PPL",
                ["AQ-003", "AQ-004", "PP-206", "PB-216", "LG-226"],
            )
    elif objetivo == "emagrecimento":
        if nivel == "iniciante":
            return (
                "Heurístico Emagrecimento Iniciante",
                3,
                45,
                "Full Body",
                ["AQ-001", "FB-172", "EM-284"],
            )
        else:
            return (
                "Heurístico Emagrecimento Intermediário",
                4,
                45,
                "Upper/Lower",
                ["AQ-003", "AQ-004", "UL-186", "UL-187", "EM-281"],
            )
    elif objetivo == "forca":
        if nivel == "iniciante":
            blocos = ["AQ-001", "FB-166"]
        elif nivel == "intermediario":
            blocos = ["AQ-003", "AQ-004", "UL-186", "UL-187"]
        else:
            blocos = ["AQ-003", "AQ-004", "PP-206", "PB-216", "LG-226"]
        return (
            "Heurístico Força",
            4,
            60,
            "Upper/Lower" if nivel != "avancado" else "PPL",
            blocos,
        )
    elif objetivo in ("condicionamento", "resistencia"):
        return (
            "Heurístico Condicionamento",
            3,
            45,
            "Funcional",
            ["AQ-006", "FU-236", "AE-272"],
        )
    return ("Heurístico Fallback", 3, 45, "Full Body", ["AQ-001", "FB-166"])


def _filtrar_limitacoes(blocos: list[str], limitacoes: list[str]) -> list[str]:
    """Remove blocos que conflitem com limitações físicas/saúde do aluno."""
    if not limitacoes or "nenhuma" in limitacoes:
        return list(blocos)

    lim = [l.lower() for l in limitacoes]
    removidos = set()

    def remove(*prefixos):
        for cod in list(blocos):
            for prefixo in prefixos:
                if cod.startswith(prefixo):
                    removidos.add(cod)

    if any(x in lim for x in ("ombro", "ombros")):
        remove("OM-", "PP-206", "PP-")  # desenvolvimento/push com ombro
        removidos.update(["PE-014", "PE-018"])
    if any(x in lim for x in ("joelho", "joelhos", "quadril", "quadril", "tornozelo")):
        remove("PQ-", "LG-226", "CO-032", "FU-")
    if any(x in lim for x in ("coluna", "coluna lombar", "lombar", "hernia_disco")):
        remove(
            "CO-028", "CO-033", "PQ-099", "LG-226", "PE-018", "LE-", "OM-048", "OM-051"
        )
    if any(x in lim for x in ("punho", "punhos", "ler_dort", "tendinite", "bursite")):
        remove("BI-", "TR-071", "TR-072", "TR-073", "PU-")
    if any(x in lim for x in ("hipertensao", "cardiopatia", "asma")):
        remove("HI-256", "HI-257", "HI-258", "HI-259")
    if "gestacao" in lim:
        remove("AB-147", "AB-148", "AB-150", "HI-", "FU-", "PQ-099", "PQ-102")
    if any(x in lim for x in ("obesidade", "idoso_60plus")):
        remove("HI-256", "HI-257", "HI-258", "HI-259", "FU-240", "FU-241", "FU-242")
    if "diabetes" in lim:
        # cardio HIIT muito intenso pode causar hipoglicemia; mantém moderado
        remove("HI-256", "HI-257")

    return [b for b in blocos if b not in removidos]


OPCOES_LIMITACOES = [
    "nenhuma",
    "joelho",
    "coluna",
    "lombar",
    "quadril",
    "tornozelo",
    "ombro",
    "punho",
    "hernia_disco",
    "tendinite",
    "bursite",
    "ler_dort",
    "hipertensao",
    "diabetes",
    "cardiopatia",
    "asma",
    "gestacao",
    "obesidade",
    "idoso_60plus",
]


def _ajustar_blocos_para_divisao(
    blocos: list[str],
    divisao: str,
    sexo: str,
    objetivo: str,
    nivel: str,
    frequencia: int,
) -> list[str]:
    """Substitui os blocos de acordo com a divisao escolhida pelo usuario."""
    sexo_prefix = "Masc" if sexo.lower().startswith("masc") else "Fem"
    nivel_lower = nivel.lower()

    if divisao == "Full Body":
        base = ["AQ-001"]
        if sexo_prefix == "Masc":
            base += ["FB-166", "FB-167"]
        else:
            base += ["FB-168", "FB-169"]
        return base

    if divisao == "Upper/Lower":
        return ["AQ-003", "AQ-004", "UL-186", "UL-187"]

    if divisao == "PPL":
        return ["AQ-003", "AQ-004", "PP-206", "PB-216", "LG-226"]

    if divisao == "A/B/C":
        return ["AQ-001", "PE-011", "CO-026", "OM-046", "BI-061", "TR-071", "PQ-096"]

    return list(blocos)


def agrupar_blocos_por_treino(blocos: list[str], divisao: str) -> dict[str, list[str]]:
    """Agrupa os blocos em Treinos A, B, C, D de acordo com a divisão e alternância."""
    div = divisao.upper()
    grupos = {}

    if "FULL BODY" in div or "COMPACTO" in div:
        fb_a = []
        fb_b = []
        general = []
        for b in blocos:
            if b.startswith("FB-"):
                try:
                    num = int(b.split("-")[1])
                    if num % 2 == 0:
                        fb_a.append(b)
                    else:
                        fb_b.append(b)
                except:
                    fb_a.append(b)
            else:
                general.append(b)
        if fb_a and fb_b:
            grupos["Treino A (Corpo Inteiro - A)"] = general + fb_a
            grupos["Treino B (Corpo Inteiro - B)"] = general + fb_b
        else:
            grupos["Treino A (Corpo Inteiro)"] = blocos

    elif "UPPER/LOWER" in div:
        u1 = []
        u2 = []
        l1 = []
        l2 = []
        general_u = ["AQ-003"]
        general_l = ["AQ-004"]
        
        for b in blocos:
            if b.startswith("UL-"):
                if b in ("UL-186", "UL-190"):
                    u1.append(b)
                elif b == "UL-188":
                    u2.append(b)
                elif b in ("UL-187", "UL-191"):
                    l1.append(b)
                elif b == "UL-189":
                    l2.append(b)
            elif b.startswith("AQ-"):
                pass
            elif any(b.startswith(p) for p in ("PE-", "CO-", "OM-", "BI-", "TR-", "AN-", "BR-")):
                u1.append(b)
            elif any(b.startswith(p) for p in ("PQ-", "PG-", "GL-", "PA-")):
                l1.append(b)
            else:
                if b.startswith("AB-"):
                    general_u.append(b)
                else:
                    general_l.append(b)
                    
        if u1:
            grupos["Treino A (Superior 1)"] = [x for x in blocos if x in general_u or x in u1]
        if l1:
            grupos["Treino B (Inferior 1)"] = [x for x in blocos if x in general_l or x in l1]
        if u2:
            grupos["Treino C (Superior 2)"] = [x for x in blocos if x in general_u or x in u2]
        if l2:
            grupos["Treino D (Inferior 2)"] = [x for x in blocos if x in general_l or x in l2]
            
        if not grupos:
            grupos["Treino A (Superior)"] = [x for x in blocos if x.startswith("AQ-003") or any(x.startswith(p) for p in ("PE-", "CO-", "OM-", "BI-", "TR-", "AN-", "BR-", "UL-186", "UL-188", "UL-190"))]
            grupos["Treino B (Inferior)"] = [x for x in blocos if x not in grupos.get("Treino A (Superior)", [])]

    elif "PPL" in div:
        treino_a = []
        treino_b = []
        treino_c = []
        for b in blocos:
            is_push = b.startswith("PP-") or any(b.startswith(prefix) for prefix in ("PE-", "OM-", "TR-"))
            is_pull = b.startswith("PB-") or any(b.startswith(prefix) for prefix in ("CO-", "BI-", "AN-"))
            is_legs = b.startswith("LG-") or any(b.startswith(prefix) for prefix in ("PQ-", "PG-", "GL-", "PA-"))
            
            if is_push:
                treino_a.append(b)
            elif is_pull:
                treino_b.append(b)
            elif is_legs:
                treino_c.append(b)
            else:
                if b in ("AQ-003", "AQ-001"):
                    treino_a.append(b)
                    treino_b.append(b)
                elif b == "AQ-004":
                    treino_c.append(b)
                elif b.startswith("AB-"):
                    treino_a.append(b)
                else:
                    treino_c.append(b)
                    
        if treino_a:
            grupos["Treino A (Push - Empurrar)"] = treino_a
        if treino_b:
            grupos["Treino B (Pull - Puxar)"] = treino_b
        if treino_c:
            grupos["Treino C (Legs - Pernas)"] = treino_c
            
    elif "A/B/C" in div or "ABC" in div:
        treino_a = []
        treino_b = []
        treino_c = []
        for b in blocos:
            is_a = any(b.startswith(prefix) for prefix in ("PE-", "OM-", "TR-"))
            is_b = any(b.startswith(prefix) for prefix in ("CO-", "BI-", "AN-"))
            is_c = any(b.startswith(prefix) for prefix in ("PQ-", "PG-", "GL-", "PA-"))
            
            if is_a:
                treino_a.append(b)
            elif is_b:
                treino_b.append(b)
            elif is_c:
                treino_c.append(b)
            else:
                if b in ("AQ-001", "AQ-003"):
                    treino_a.append(b)
                    treino_b.append(b)
                elif b == "AQ-004":
                    treino_c.append(b)
                elif b.startswith("AB-"):
                    treino_b.append(b)
                else:
                    treino_c.append(b)
                    
        if treino_a:
            grupos["Treino A (Peito / Ombro / Tríceps)"] = treino_a
        if treino_b:
            grupos["Treino B (Costas / Bíceps)"] = treino_b
        if treino_c:
            grupos["Treino C (Pernas / Glúteos)"] = treino_c
    else:
        grupos["Treino A"] = blocos

    return grupos


labels_limitacoes = {
    "nenhuma": "Nenhuma",
    "joelho": "Joelho",
    "coluna": "Coluna",
    "lombar": "Lombar/Hernia de disco",
    "quadril": "Quadril",
    "tornozelo": "Tornozelo",
    "ombro": "Ombro",
    "punho": "Punho/LER/DORT",
    "hernia_disco": "Hérnia de disco",
    "tendinite": "Tendinite",
    "bursite": "Bursite",
    "ler_dort": "LER/DORT",
    "hipertensao": "Hipertensão",
    "diabetes": "Diabetes",
    "cardiopatia": "Cardiopatia",
    "asma": "Asma",
    "gestacao": "Gestação",
    "obesidade": "Obesidade",
    "idoso_60plus": "Idoso 60+",
}


@cached(ttl=120)
def _buscar_bloco_por_codigo(codigo: str) -> dict | None:
    try:
        r = api_get(
            "/Odata/PredefinedsTrainings",
            {
                "$filter": f"startswith(Description,'{codigo}')",
                "$top": "1",
                "$select": "PredefinedTrainingId,Description,TrainingDuration,CaloricBurnEstimate",
            },
        )
        items = r.get("value", [])
        if items:
            return items[0]
    except Exception:
        pass
    return None


def montar_ficha(
    sexo: str,
    objetivo: str,
    nivel: str,
    frequencia: int,
    tempo_disponivel: int = 60,
    limitacoes: list[str] | None = None,
    divisao_preferida: str = "Automatica",
) -> dict:
    sexo_n = "Masc" if sexo.lower().startswith("m") else "Fem"
    obj_n = objetivo.lower()
    niv_n = nivel.lower()

    match = None
    for perfil, freq, tempo, divisao, blocos in TABELA_DECISAO:
        perfil_l = perfil.lower()
        if sexo_n.lower() in perfil_l or "qualquer" in perfil_l.lower():
            if obj_n in perfil_l or (
                "hiit" in perfil_l and obj_n in ("condicionamento", "emagrecimento")
            ):
                if niv_n in perfil_l or "qualquer" in perfil_l.lower():
                    if (
                        abs(frequencia - freq) <= 1
                        and abs(tempo_disponivel - tempo) <= 15
                    ):
                        match = (perfil, freq, tempo, divisao, list(blocos))
                        break

    if not match:
        match = _montar_heuristico(sexo_n, obj_n, niv_n, frequencia, tempo_disponivel)

    if not match:
        return {"erro": "Não foi possível montar uma ficha para este perfil."}

    perfil, freq, tempo, divisao, blocos = match

    # Override de divisão se o usuário escolheu algo específico
    if divisao_preferida and divisao_preferida.lower() != "automatica":
        divisao_map = {
            "full_body": "Full Body",
            "upper_lower": "Upper/Lower",
            "ppl": "PPL",
            "abc": "A/B/C",
        }
        divisao = divisao_map.get(divisao_preferida.lower(), divisao)
        blocos = _ajustar_blocos_para_divisao(
            blocos, divisao, sexo_n, obj_n, niv_n, frequencia
        )

    vol = VOLUME_POR_NIVEL.get(niv_n, (18, 20, 40))
    recomendacoes = []

    limitacoes = limitacoes or []
    if limitacoes and "nenhuma" not in limitacoes:
        original = list(blocos)
        blocos = _filtrar_limitacoes(blocos, limitacoes)
        removidos = set(original) - set(blocos)
        if removidos:
            recomendacoes.append(
                f"Limitacao: blocos removidos — {', '.join(sorted(removidos))}"
            )

    if (
        tempo_disponivel >= 45
        and not any(b.startswith("AE-") for b in blocos)
        and "EM-" not in str(blocos)
    ):
        recomendacoes.append(
            "Adicione AE-274 (Cardio Finalizador 10min) ao final da sessao"
        )

    if (
        not any(b.startswith("AB-") for b in blocos)
        and not any(b.startswith("FB-") for b in blocos)
        and not any(b.startswith("EM-") for b in blocos)
    ):
        recomendacoes.append("Adicione AB-151 (Abdomen Finalizador 8min)")

    # Buscar detalhes dos blocos na API
    detalhes = []
    with st.spinner("Buscando blocos no Actuar..."):
        for codigo in blocos:
            info = _buscar_bloco_por_codigo(codigo)
            if info:
                detalhes.append(
                    {
                        "codigo": codigo,
                        "nome": info.get("Description", codigo),
                        "duracao": info.get("TrainingDuration", 0),
                        "calorias": info.get("CaloricBurnEstimate", 0),
                        "id": info.get("PredefinedTrainingId"),
                        "encontrado": True,
                    }
                )
            else:
                detalhes.append(
                    {
                        "codigo": codigo,
                        "nome": codigo,
                        "duracao": 0,
                        "calorias": 0,
                        "id": None,
                        "encontrado": False,
                    }
                )

    duracao_total = sum(d.get("duracao", 0) for d in detalhes)
    calorias_total = sum(d.get("calorias", 0) for d in detalhes)

    return {
        "perfil": perfil,
        "parametros": {
            "sexo": sexo,
            "objetivo": objetivo,
            "nivel": nivel,
            "frequencia_semanal": frequencia,
            "tempo_sessao_min": tempo_disponivel,
            "limitacoes": limitacoes or "nenhuma",
        },
        "divisao": divisao,
        "blocos": blocos,
        "volume": {
            "series_min": vol[0],
            "series_max": vol[1],
            "duracao_max_min": vol[2],
        },
        "recomendacoes": recomendacoes,
        "detalhes": detalhes,
        "duracao_total": duracao_total,
        "calorias_total": calorias_total,
    }


# ══════════════════════════════════════════════════════════
#  API HELPERS (para as abas de catalogo)
# ══════════════════════════════════════════════════════════


@cached(ttl=300)
def listar_blocos(busca: str = "", categoria: str = "") -> list:
    try:
        params = {
            "$top": "200",
            "$count": "true",
            "$select": "PredefinedTrainingId,Description,TrainingDuration,CaloricBurnEstimate,Comment",
            "$orderby": "Description asc",
        }
        filters = []
        if busca:
            filters.append(f"contains(Description,'{busca}')")
        if categoria:
            filters.append(f"contains(Description,'{categoria}')")
        if filters:
            params["$filter"] = " and ".join(filters)
        r = api_get("/Odata/PredefinedsTrainings", params)
        return r.get("value", [])
    except Exception as e:
        st.error(f"Erro ao carregar blocos: {e}")
        return []


@cached(ttl=300)
def obter_bloco_detalhes(bloco_id: str) -> dict:
    """Busca detalhe completo do bloco incluindo PredefinedTrainingItems."""
    try:
        r = api_get(f"/PredefinedTraining/{bloco_id}")
        return r
    except Exception as e:
        return {"error": str(e)}


@cached(ttl=300)
def listar_exercicios(busca: str = "", grupo: str = "", top: int = 100) -> list:
    try:
        filters = []
        if busca:
            filters.append(f"contains(ShortDescription,'{busca}')")
        if grupo:
            filters.append(f"contains(MuscleGroupDescription,'{grupo}')")
        params = {
            "$top": str(top),
            "$count": "true",
            "$select": "ExerciseId,ShortDescription,LongDescription,MuscleGroupDescription,ExerciseType,IsActive,VideoStorageId",
        }
        if filters:
            params["$filter"] = " and ".join(filters)
        r = api_get("/Odata/Exercises", params)
        return r.get("value", [])
    except Exception as e:
        st.error(f"Erro ao carregar exercicios: {e}")
        return []


# ══════════════════════════════════════════════════════════
#  UI — SIDEBAR
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dumbbell.png", width=64)
    st.markdown("## Espaço Viva")
    st.caption("Sistema de Montagem de Fichas de Treino")
    st.divider()
    aba = st.radio(
        "Navegacao",
        ["Montar Ficha", "Catalogo de Blocos", "Exercicios"],
        label_visibility="collapsed",
    )

# ══════════════════════════════════════════════════════════
#  TAB 1 — MONTAR FICHA
# ══════════════════════════════════════════════════════════

if aba == "Montar Ficha":
    st.markdown("## Montar Ficha de Treino")
    st.caption("Preencha os dados do aluno e o sistema recomendará os blocos ideais.")
    st.info(
        "O tempo de sessão é o tempo estimado de execução dos blocos principais. "
        "Aquecimento e finalizadores (cardio/abdomen) sao contabilizados separadamente nas recomendacoes.",
        icon="ℹ",
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        sexo = st.radio("Sexo", ["Masculino", "Feminino"], horizontal=True)
        objetivo = st.selectbox(
            "Objetivo", ["Hipertrofia", "Emagrecimento", "Força", "Resistência"]
        )
        nivel = st.selectbox("Nível", ["Iniciante", "Intermediário", "Avançado"])

    with col2:
        frequencia = st.slider(
            "Frequência semanal", 2, 6, 4, help="Dias de treino por semana"
        )
        tempo = st.select_slider(
            "Tempo por sessão",
            options=[30, 45, 60],
            value=60,
            help="Minutos disponíveis por treino",
        )

    with col3:
        limitacoes_sel = st.multiselect(
            "Limitacoes",
            options=OPCOES_LIMITACOES,
            format_func=lambda x: labels_limitacoes.get(x, x),
            default=["nenhuma"],
            help="Selecione as limitacoes fisicas/saude do aluno. Use 'Nenhuma' para nenhuma limitacao.",
        )
        if "nenhuma" in limitacoes_sel and len(limitacoes_sel) > 1:
            limitacoes_sel = [l for l in limitacoes_sel if l != "nenhuma"]
            if not limitacoes_sel:
                limitacoes_sel = ["nenhuma"]
        divisao = st.selectbox(
            "Divisao preferida",
            ["Automatica", "Full Body", "Upper/Lower", "PPL", "A/B/C", "Funcional"],
            help="Deixe 'Automatica' para usar a divisao recomendada pelo sistema.",
        )

    st.markdown("### 👤 Dados do Aluno & Avaliação Física")
    col_al1, col_al2 = st.columns([1.5, 2])
    with col_al1:
        aluno_name = st.text_input("Nome do Aluno", "Aluno de Teste")
        col_av1, col_av2, col_av3 = st.columns(3)
        with col_av1:
            peso = st.number_input("Peso (kg)", min_value=10.0, max_value=250.0, value=75.0, step=0.5)
        with col_av2:
            altura = st.number_input("Altura (m)", min_value=0.5, max_value=2.50, value=1.75, step=0.01)
        with col_av3:
            bf = st.number_input("Gordura (BF%)", min_value=1.0, max_value=80.0, value=15.0, step=0.1)
    with col_al2:
        anamnese = st.text_area(
            "Anamnese / Limitações e Observações Clínicas", 
            "Aluno iniciante, sem dores articulares ou restrições graves. Foco em adaptação anatômica."
        )

    st.divider()

    if st.button("Montar Ficha", type="primary", use_container_width=True):
        lim_list = [l for l in limitacoes_sel if l]
        div_str = divisao
        resultado: dict = {}

        with st.spinner("Analisando perfil e montando ficha..."):
            try:
                resultado = montar_ficha(
                    sexo,
                    objetivo.lower(),
                    nivel.lower(),
                    frequencia,
                    tempo,
                    lim_list,
                    div_str,
                )
            except Exception as e:
                st.error(f"Erro ao montar ficha: {e}")
                st.stop()

        if "erro" in resultado:
            st.error(resultado["erro"])
            st.stop()

        # ── CABEÇALHO ──
        st.markdown(
            f"""<div class="result-header">
            <h2>{resultado["perfil"]}</h2>
            <p>Divisão: <strong>{resultado["divisao"]}</strong> · {resultado["parametros"]["frequencia_semanal"]}x/semana · {resultado["parametros"]["tempo_sessao_min"]}min</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── ESTATÍSTICAS ──
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(
                f"""
                <style>
                .stat-val-green {{
                    color: #00ff88 !important;
                    font-size: 1.4rem !important;
                    font-weight: 700 !important;
                }}
                .stat-lbl-gray {{
                    color: #8888aa !important;
                    font-size: 0.75rem !important;
                }}
                </style>
                <div class='stat-box'>
                    <div class='stat-val-green'>{len(resultado['blocos'])}</div>
                    <div class='stat-lbl-gray'>Blocos</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with sc2:
            st.markdown(
                f"""
                <div class='stat-box'>
                    <div class='stat-val-green'>{resultado['duracao_total']}min</div>
                    <div class='stat-lbl-gray'>Duração total</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with sc3:
            st.markdown(
                f"""
                <div class='stat-box'>
                    <div class='stat-val-green'>{resultado['calorias_total']}</div>
                    <div class='stat-lbl-gray'>Kcal estimadas</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with sc4:
            st.markdown(
                f"""
                <div class='stat-box'>
                    <div class='stat-val-green'>{resultado['volume']['series_min']}-{resultado['volume']['series_max']}</div>
                    <div class='stat-lbl-gray'>Séries / nível</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        # ── BLOCOS ──
        st.markdown("### 📋 Exercícios por Treino")
        
        treinos_agrupados = agrupar_blocos_por_treino(resultado["blocos"], resultado["divisao"])
        
        # Cria abas do Streamlit para cada Ficha (Treino A, B, C...)
        abas = st.tabs(list(treinos_agrupados.keys()))
        for aba_idx, (nome_treino, codigos_bloco) in enumerate(treinos_agrupados.items()):
            with abas[aba_idx]:
                # Tabela de exercícios legíveis para o paciente (sem expor códigos internos ou UUIDs)
                html_table = f"""
                <div style="border: 1px solid #2a2a4a; border-radius: 8px; margin-top: 10px; margin-bottom: 20px; background: #1a1a2e;">
                    <table style="width:100%; border-collapse: collapse; font-family: sans-serif; margin: 0;">
                        <thead>
                            <tr style="background-color: #0a3c2a; color: #00ff88; text-align: left; font-weight: bold; border-bottom: 2px solid #2a2a4a; position: sticky; top: 0; z-index: 10;">
                                <th style="padding: 12px 15px; width: 8%; background-color: #0a3c2a; position: sticky; top: 0;">Ord</th>
                                <th style="padding: 12px 15px; width: 42%; background-color: #0a3c2a; position: sticky; top: 0;">Exercício</th>
                                <th style="padding: 12px 15px; width: 25%; background-color: #0a3c2a; position: sticky; top: 0;">Séries / Repetições / Tempo</th>
                                <th style="padding: 12px 15px; width: 25%; background-color: #0a3c2a; position: sticky; top: 0;">Categoria / Bloco</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                ex_idx = 1
                for cod_bloco in codigos_bloco:
                    local_items = LOCAL_EXERCISES.get(cod_bloco, [])
                    bloco_nome = next((item["nome"] for item in resultado["detalhes"] if item["codigo"] == cod_bloco), cod_bloco)
                    
                    for item in local_items:
                        name = item.get("name", "")
                        comments = item.get("comments", "")
                        bloco_clean = bloco_nome.replace(cod_bloco + " — ", "")
                        
                        bg_color = "#151525" if ex_idx % 2 == 0 else "#1a1a2e"
                        
                        html_table += f"""
                        <tr style="background-color: {bg_color}; color: #ffffff; border-bottom: 1px solid #2a2a4a;">
                            <td style="padding: 10px 15px; font-weight: bold; color: #00ff88;">{ex_idx}</td>
                            <td style="padding: 10px 15px; font-weight: bold;">{name}</td>
                            <td style="padding: 10px 15px; color: #eeeeee;">{comments}</td>
                            <td style="padding: 10px 15px; color: #8888aa; font-size: 0.85rem;">{bloco_clean}</td>
                        </tr>
                        """
                        ex_idx += 1
                
                html_table += "</tbody></table></div>"
                st.markdown(html_table.replace("\n", "").replace("    ", ""), unsafe_allow_html=True)

        # ── RECOMENDAÇÕES ──
        if resultado["recomendacoes"]:
            st.markdown("### 💡 Recomendações")
            for rec in resultado["recomendacoes"]:
                st.markdown(
                    f"<div class='rec-card'>{rec}</div>", unsafe_allow_html=True
                )

        # ── IMPRESSÃO & EXPORTAÇÃO ──
        st.divider()
        st.markdown("### 📥 Impressão e Exportação")
        
        pdf_data = {
            "aluno_name": aluno_name,
            "sexo": sexo,
            "objetivo": objetivo,
            "nivel": nivel,
            "frequencia": frequencia,
            "divisao": resultado["divisao"],
            "anamnese": anamnese,
            "peso": peso,
            "altura": altura,
            "bf": bf,
            "treinos": treinos_agrupados,
            "local_exercises": LOCAL_EXERCISES,
            "bloco_nomes": {d["codigo"]: d["nome"] for d in resultado["detalhes"]},
            "recomendacoes": resultado["recomendacoes"]
        }
        
        try:
            from portal.pdf_generator import generate_a4_pdf, generate_thermal_pdf
        except ModuleNotFoundError:
            from pdf_generator import generate_a4_pdf, generate_thermal_pdf
        
        try:
            a4_pdf_bytes = generate_a4_pdf(pdf_data)
            thermal_pdf_bytes = generate_thermal_pdf(pdf_data)
            
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.download_button(
                    label="📄 Baixar Ficha Oficial A4 (PDF)",
                    data=a4_pdf_bytes,
                    file_name=f"ficha_{aluno_name.replace(' ', '_').lower()}_a4.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            with p_col2:
                st.download_button(
                    label="🧾 Baixar Ficha Térmica 80mm (PDF)",
                    data=thermal_pdf_bytes,
                    file_name=f"ficha_{aluno_name.replace(' ', '_').lower()}_termica.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        except Exception as pdf_err:
            st.error(f"Erro ao gerar arquivos PDF: {pdf_err}")

        st.divider()
        st.caption(
            f"Volume máximo para nível **{nivel}**: {resultado['volume']['series_min']}-{resultado['volume']['series_max']} séries · até {resultado['volume']['duracao_max_min']}min"
        )

# ══════════════════════════════════════════════════════════
#  TAB 2 — CATÁLOGO DE BLOCOS
# ══════════════════════════════════════════════════════════

elif aba == "Catalogo de Blocos":
    st.markdown("## Catalogo de Blocos Modulares")
    st.caption("Explore os 104 blocos de treino cadastrados no sistema.")

    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        busca_bloco = st.text_input(
            "Buscar por nome ou codigo",
            placeholder="Ex: PE-011, Full Body, Aquecimento...",
        )
    with col_b2:
        CATEGORIAS_MAP = {
            "Todas": "",
            "Aquecimento": "AQ-",
            "Peitoral": "PE-",
            "Costas": "CO-",
            "Ombro": "OM-",
            "Biceps": "BI-",
            "Triceps": "TR-",
            "Antebraco": "AN-",
            "Braco Completo": "BR-",
            "Perna Quadriceps": "PQ-",
            "Posterior+Gluteo": "PG-",
            "Gluteo Isolado": "GL-",
            "Abdomen": "AB-",
            "Panturrilha": "PA-",
            "Full Body": "FB-",
            "Upper/Lower": "UL-",
            "Push (PPL)": "PP-",
            "Pull (PPL)": "PB-",
            "Legs (PPL)": "LG-",
            "Funcional": "FU-",
            "HIIT": "HI-",
            "Aerobico": "AE-",
            "Emagrecimento": "EM-",
        }
        cat_filtro_label = st.selectbox("Categoria", list(CATEGORIAS_MAP.keys()))
        cat_filtro = CATEGORIAS_MAP[cat_filtro_label]

    with st.spinner("Carregando blocos..."):
        blocos = listar_blocos(busca_bloco, cat_filtro)

    if not blocos:
        st.info("Nenhum bloco encontrado. Verifique a conexão com o Actuar.")
    else:
        st.success(f"{len(blocos)} blocos encontrados")
        cols = st.columns(3)
        for i, b in enumerate(blocos):
            desc = b.get("Description", "Sem nome")
            # Extrai código do nome
            codigo = desc.split(" — ")[0] if " — " in desc else desc[:6]
            with cols[i % 3]:
                st.markdown(
                    f"""<div class="block-card">
                    <h3>{desc}</h3>
                    <div class="meta">
                    <span class="badge badge-blue">T {b.get("TrainingDuration", "?")}min</span>
                    <span class="badge badge-orange">K {b.get("CaloricBurnEstimate", "?")} kcal</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                bloco_id = b.get("PredefinedTrainingId", "")
                if bloco_id:
                    with st.expander("Descricao + Exercicios", expanded=False):
                        if b.get("Comment"):
                            st.write(b["Comment"])
                        st.markdown("**Exercicios:**")
                        local_items = LOCAL_EXERCISES.get(codigo, [])
                        if local_items:
                            for idx, item in enumerate(local_items, 1):
                                name = item.get("name", "")
                                comments = item.get("comments", "")
                                if comments:
                                    st.markdown(f"**{idx}.** {name} — *{comments}*")
                                else:
                                    st.markdown(f"**{idx}.** {name}")
                        else:
                            st.caption("Nenhum exercicio encontrado neste bloco.")

# ══════════════════════════════════════════════════════════
#  TAB 3 — BIBLIOTECA DE EXERCÍCIOS
# ══════════════════════════════════════════════════════════

elif aba == "Exercicios":
    st.markdown("## Biblioteca de Exercicios")
    st.caption("Consulte os 404 exercícios disponíveis com vídeos demonstrativos.")

    col_e1, col_e2 = st.columns([2, 1])
    with col_e1:
        busca_ex = st.text_input(
            "Buscar exercício", placeholder="Ex: Supino, Agachamento, Rosca..."
        )
    with col_e2:
        grupos = [
            "Todos",
            "Peitoral",
            "Costas",
            "Ombro",
            "Bíceps",
            "Tríceps",
            "Abdômen",
            "Perna",
            "Quadriceps",
            "Posterior de coxa",
            "Glúteo",
            "Panturrilha",
            "Antebraço",
            "Funcional",
            "Cardio",
            "Core",
        ]
        grupo_filtro = st.selectbox("Grupo muscular", grupos)
        if grupo_filtro == "Todos":
            grupo_filtro = ""

    with st.spinner("Carregando exercícios..."):
        exercicios = listar_exercicios(busca_ex, grupo_filtro)

    if not exercicios:
        st.info("Nenhum exercício encontrado.")
    else:
        st.success(f"{len(exercicios)} exercícios encontrados")

        # Tabela
        col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 1, 1])
        with col_h1:
            st.markdown("**Nome**")
        with col_h2:
            st.markdown("**Grupo Muscular**")
        with col_h3:
            st.markdown("**Categoria**")
        with col_h4:
            st.markdown("**Vídeo**")
        st.divider()

        for ex in exercicios:
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            with c1:
                st.write(ex.get("ShortDescription", "—"))
            with c2:
                st.write(ex.get("MuscleGroupDescription", "—"))
            with c3:
                st.write(ex.get("ExerciseType", "—"))
            with c4:
                if ex.get("VideoStorageId"):
                    st.markdown(
                        "<span class='badge badge-green'>Video</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("—")
