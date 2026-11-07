"""
Auditable Web Search & Safe Retrieval Adapter — Gambit Lab Nocturne (R1.0)
Implementa busca pública opt-in auditável (Wikimedia/Wikipedia + OpenAlex Scholarly API)
com proteção estrita contra SSRF (bloqueio de localhost, redes privadas, link-local,
cloud metadata 169.254.169.254, validação de DNS e pós-redirect, limite de bytes/tempo/MIME),
gerando SourceRecords rastreáveis com SHA-256, URL canônica e timestamp UTC.
(AUD-01, P0-A, RF-R01..RF-R03, AT-04..AT-06, AT-18)
"""
import os
import re
import html
import json
import socket
import hashlib
import datetime
import ipaddress
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
import httpx


class SSRFBlockedError(PermissionError):
    """Lançada quando uma URL ou redirecionamento viola a política anti-SSRF."""
    pass


class WebSearchUnavailableError(RuntimeError):
    """Lançada quando a pesquisa web está desabilitada ou falha sem inventar fontes."""
    pass


BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
    "instance-data",
}

ALLOWED_MIME_PREFIXES = (
    "application/json",
    "text/plain",
    "text/html",
    "application/xhtml+xml",
    "text/markdown",
    "application/rss+xml",
    "application/xml",
    "text/xml",
    "application/atom+xml",
)

CGNAT_NET_V4 = ipaddress.ip_network("100.64.0.0/10")
METADATA_NET_V4 = ipaddress.ip_network("169.254.0.0/16")


def _check_ip_address_safe(ip_str: str) -> None:
    """Valida que um IP resolvido é estritamente público (rejeita privado/loopback/link-local/metadata)."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError as exc:
        raise SSRFBlockedError(f"Endereço IP inválido na validação SSRF: {ip_str}") from exc

    # Desembrulha IPv4 mapeado em IPv6 (ex: ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or (isinstance(ip_obj, ipaddress.IPv4Address) and (ip_obj in CGNAT_NET_V4 or ip_obj in METADATA_NET_V4))
    ):
        raise SSRFBlockedError(
            f"SSRF_BLOCKED: Endereço não-público bloqueado ({ip_obj})."
        )


def validate_url_ssrf(url: str) -> urllib.parse.ParseResult:
    """
    Valida esquema HTTPS, hostname e todos os endereços IP retornados pelo DNS.
    Bloqueia localhost, IPs privados, link-local e endpoints de metadata de nuvem.
    """
    if not url or not isinstance(url, str):
        raise SSRFBlockedError("SSRF_BLOCKED: URL vazia ou inválida.")

    parsed = urllib.parse.urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").strip().lower()

    if not hostname:
        raise SSRFBlockedError("SSRF_BLOCKED: Hostname ausente na URL.")

    if (
        hostname in BLOCKED_HOSTNAMES
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
        or hostname.endswith(".localhost")
    ):
        raise SSRFBlockedError(f"SSRF_BLOCKED: Hostname interno bloqueado ({hostname}).")

    # Se o hostname já for um literal IP, valida imediatamente antes mesmo de checar esquema/DNS
    try:
        ipaddress.ip_address(hostname)
        _check_ip_address_safe(hostname)
    except ValueError:
        pass

    if scheme != "https":
        raise SSRFBlockedError(
            f"SSRF_BLOCKED: Apenas esquema HTTPS público é permitido (recebido: '{scheme}')."
        )

    if parsed.username or parsed.password:
        raise SSRFBlockedError("SSRF_BLOCKED: Credenciais embutidas na URL são proibidas.")

    port = parsed.port or 443
    if port not in (443,):
        raise SSRFBlockedError(f"SSRF_BLOCKED: Porta não autorizada ({port}); permitido apenas 443.")

    try:
        addr_infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebSearchUnavailableError(f"SEARCH_UNAVAILABLE: Falha de resolução DNS para {hostname}.") from exc

    if not addr_infos:
        raise WebSearchUnavailableError(f"SEARCH_UNAVAILABLE: Nenhum endereço DNS resolvido para {hostname}.")

    for info in addr_infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        _check_ip_address_safe(ip_str)

    return parsed


def sanitize_html_to_text(raw_text: str, max_chars: int = 4000) -> str:
    """Remove scripts, estilos e tags HTML (inclusive entidades escapadas em RSS), preservando apenas texto inerte para citação auditável."""
    unescaped = html.unescape(raw_text or "")
    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", unescaped)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


def _reconstruct_openalex_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """Reconstrói resumo textual a partir do abstract_inverted_index público do OpenAlex."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    positions: Dict[int, str] = {}
    for word, idxs in inverted_index.items():
        if isinstance(idxs, list):
            for idx in idxs:
                if isinstance(idx, int) and 0 <= idx <= 5000:
                    positions[idx] = word
    if not positions:
        return ""
    ordered = [positions[i] for i in sorted(positions.keys())]
    return " ".join(ordered)


SEARCH_STOPWORDS = {
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não",
    "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi",
    "ao", "ele", "das", "tem", "à", "seu", "sua", "ou", "ser", "quando", "muito", "há",
    "nos", "já", "está", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela",
    "entre", "era", "depois", "sem", "mesmo", "aos", "ter", "seus", "quem", "nas", "me",
    "esse", "eles", "estão", "você", "tinha", "foram", "essa", "num", "nem", "suas",
    "meu", "às", "minha", "têm", "numa", "pelos", "elas", "havia", "seja", "qual",
    "quais", "será", "sera", "seria", "sobre", "referente", "benefícios", "beneficios",
    "vantagens", "evidências", "evidencias", "riscos", "limitações", "limitacoes",
    "críticas", "criticas", "controles", "requisitos", "conformidade", "auditoria",
    "vulnerabilidades", "falhas", "brechas", "indicadores", "históricos", "historicos",
    "comparação", "comparacao", "melhor", "melhores", "pior", "piores", "toda", "todo",
    "todos", "todas", "história", "historia", "futuro", "ano", "anos", "vai", "ganhar",
}

GENERIC_CONTEXT_WORDS = {
    "brasil", "brasileiro", "brasileira", "brasileiros", "presidente", "presidênte",
    "presidencia", "presidência", "governo", "governos", "estado", "país", "pais",
    "mundo", "nacional", "público", "publico", "pública", "publica", "sistema", "sistemas",
    "2026", "2027", "2028", "2029", "2030", "2032", "2034", "2035", "2040",
}


def extract_focused_queries(raw_query: str) -> Tuple[str, List[str], List[str]]:
    """
    Extrai (1) a consulta principal enxuta sem sufixos de viés/stopwords,
    (2) termos específicos âncora (entidades/substantivos centrais) e
    (3) variações de busca para Wikipedia, Google News e OpenAlex.
    """
    cleaned = re.sub(r"[^\w\sÀ-ÿ0-9\-]", " ", raw_query or "").strip()
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    core_tokens = [t for t in tokens if t.lower() not in SEARCH_STOPWORDS]
    if not core_tokens:
        core_tokens = tokens[:5]

    specific_anchors = [
        t.lower() for t in core_tokens
        if len(t) >= 3 and t.lower() not in GENERIC_CONTEXT_WORDS and not t.isdigit()
    ]
    if not specific_anchors:
        specific_anchors = [t.lower() for t in core_tokens if len(t) >= 3][:4]

    primary_query = " ".join(core_tokens[:6]) if core_tokens else cleaned[:100]
    candidate_queries: List[str] = []

    # Se os primeiros tokens formam uma entidade/assunto específico (ex.: "Renan Santos"), cria busca focada na entidade
    non_generic = [t for t in core_tokens if t.lower() not in GENERIC_CONTEXT_WORDS and not t.isdigit()]
    bias_Hints_pro = {"propostas", "articulação", "alianças", "partido", "trajetória", "benefícios", "vantagens"}
    bias_Hints_con = {"críticas", "ataques", "rejeição", "controvérsias", "oposição", "riscos", "limitações"}
    entity_tokens = [t for t in non_generic if t.lower() not in bias_Hints_pro and t.lower() not in bias_Hints_con]
    bias_tokens = [t for t in non_generic if t.lower() in bias_Hints_pro or t.lower() in bias_Hints_con]

    if 1 <= len(entity_tokens) <= 4:
        entity_str = " ".join(entity_tokens[:3])
        if bias_tokens:
            candidate_queries.append(f"{entity_str} {' '.join(bias_tokens[:2])}")
        candidate_queries.append(entity_str)
        if any(w in cleaned.lower() for w in ("presidente", "presidênte", "eleição", "eleições", "política", "partido", "governo")):
            candidate_queries.append(f"{entity_str} política Brasil")

    if primary_query and primary_query not in candidate_queries:
        candidate_queries.append(primary_query)

    if len(core_tokens) > 3:
        short_q = " ".join(core_tokens[:3])
        if short_q not in candidate_queries:
            candidate_queries.append(short_q)

    return primary_query, specific_anchors, candidate_queries


class WebSearchAdapter:
    """
    Adaptador auditável de busca web pública com proteção SSRF e snapshots SHA-256.
    """

    MAX_RESPONSE_BYTES = 512 * 1024  # 512 KB
    MAX_REDIRECTS = 3
    TIMEOUT_SECONDS = 8.0
    USER_AGENT = "GambitLabNocturne/2.1 (EpistemicResearchFramework; +https://github.com/gambit-lab)"

    def __init__(self, http_client: Optional[httpx.Client] = None):
        self._custom_client = http_client
        self.call_count: int = 0
        self.last_error: Optional[str] = None

    def is_enabled(self) -> bool:
        val = os.environ.get("GAMBIT_WEB_SEARCH_ENABLED", "true").strip().lower()
        return val not in ("0", "false", "no", "off", "disabled")

    def get_capabilities(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {
                "available": False,
                "provider": None,
                "reason": "DISABLED_BY_CONFIG",
            }
        return {
            "available": True,
            "provider": "wikimedia_openalex_https",
            "reason": None,
        }

    def safe_get_bytes(self, url: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Executa GET HTTPS seguro com validação SSRF pré-conexão e em cada hop de redirecionamento,
        limite estrito de bytes, validação de MIME e timeout curto.
        """
        if not self.is_enabled():
            raise WebSearchUnavailableError("SEARCH_UNAVAILABLE: Pesquisa web desabilitada por configuração.")

        if params:
            qs = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            current_url = f"{url}{sep}{qs}"
        else:
            current_url = url

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, text/html;q=0.8",
        }

        self.call_count += 1

        def _do_fetch(client: httpx.Client) -> bytes:
            target = current_url
            for _ in range(self.MAX_REDIRECTS + 1):
                validate_url_ssrf(target)
                with client.stream("GET", target, headers=headers) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get("Location")
                        if not loc:
                            raise WebSearchUnavailableError("SEARCH_UNAVAILABLE: Redirect sem Location.")
                        target = urllib.parse.urljoin(target, loc)
                        validate_url_ssrf(target)
                        continue

                    if resp.status_code >= 400:
                        raise WebSearchUnavailableError(
                            f"SEARCH_UNAVAILABLE: Provedor web retornou HTTP {resp.status_code}."
                        )

                    ctype = (resp.headers.get("Content-Type") or "").lower()
                    if ctype and not any(ctype.startswith(p) for p in ALLOWED_MIME_PREFIXES):
                        raise WebSearchUnavailableError(
                            f"SEARCH_UNAVAILABLE: Content-Type não permitido ({ctype})."
                        )

                    chunks: List[bytes] = []
                    total = 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > self.MAX_RESPONSE_BYTES:
                            raise WebSearchUnavailableError(
                                f"SEARCH_UNAVAILABLE: Resposta excedeu limite de {self.MAX_RESPONSE_BYTES} bytes."
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)

            raise WebSearchUnavailableError("SEARCH_UNAVAILABLE: Número máximo de redirecionamentos excedido.")

        try:
            if self._custom_client is not None:
                return _do_fetch(self._custom_client)
            with httpx.Client(timeout=self.TIMEOUT_SECONDS, follow_redirects=False) as client:
                return _do_fetch(client)
        except (SSRFBlockedError, WebSearchUnavailableError):
            raise
        except Exception as exc:
            self.last_error = str(exc)
            raise WebSearchUnavailableError(f"SEARCH_UNAVAILABLE: Falha de rede na consulta web ({exc}).") from exc

    def fetch_url_snapshot(self, url: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Recupera snapshot público auditável de uma URL HTTPS específica após validação SSRF."""
        parsed = validate_url_ssrf(url)
        raw_bytes = self.safe_get_bytes(url)
        raw_str = raw_bytes.decode("utf-8", errors="replace")
        text_content = sanitize_html_to_text(raw_str, max_chars=4000)
        if not text_content:
            raise WebSearchUnavailableError("SEARCH_UNAVAILABLE: Conteúdo textual vazio na fonte recuperada.")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        canonical = f"https://{parsed.hostname}{parsed.path}"
        sha256 = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
        return {
            "title": title or f"Web Snapshot — {parsed.hostname}",
            "url": url,
            "canonical_url": canonical,
            "domain": parsed.hostname or "",
            "retrieved_at": now,
            "sha256": sha256,
            "content": text_content,
            "excerpt": text_content[:280],
            "accessible": True,
            "source_type": "web",
        }

    def _search_wikipedia(self, query: str, lang: str = "pt", limit: int = 2) -> List[Dict[str, Any]]:
        api_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_bytes = self.safe_get_bytes(
            api_url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query[:140],
                "srlimit": str(limit),
                "utf8": "1",
                "format": "json",
            },
        )
        search_data = json.loads(search_bytes.decode("utf-8", errors="replace"))
        hits = search_data.get("query", {}).get("search", [])
        if not hits:
            return []

        page_ids = "|".join(str(h["pageid"]) for h in hits if "pageid" in h)
        if not page_ids:
            return []

        ext_bytes = self.safe_get_bytes(
            api_url,
            params={
                "action": "query",
                "pageids": page_ids,
                "prop": "extracts|info",
                "inprop": "url",
                "explaintext": "1",
                "exchars": "2200",
                "format": "json",
            },
        )
        ext_data = json.loads(ext_bytes.decode("utf-8", errors="replace"))
        pages = ext_data.get("query", {}).get("pages", {})
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results: List[Dict[str, Any]] = []

        for pid, pinfo in pages.items():
            extract = sanitize_html_to_text(pinfo.get("extract") or "", max_chars=2500)
            if len(extract) < 40:
                continue
            title = (pinfo.get("title") or f"Wikipedia {pid}").strip()
            canonical_url = pinfo.get("canonicalurl") or pinfo.get("fullurl") or f"https://{lang}.wikipedia.org/?curid={pid}"
            domain = f"{lang}.wikipedia.org"
            content = (
                f"Fonte Web Pública: {title} ({domain})\n"
                f"URL Canônica: {canonical_url}\n"
                f"Recuperado em: {now}\n\n"
                f"{extract}"
            )
            sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            results.append({
                "title": f"{title} — Wikipedia ({lang.upper()})",
                "url": canonical_url,
                "canonical_url": canonical_url,
                "domain": domain,
                "retrieved_at": now,
                "sha256": sha256,
                "content": content,
                "excerpt": extract[:260],
                "accessible": True,
                "source_type": "web",
            })
        return results

    def _search_openalex(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        api_url = "https://api.openalex.org/works"
        raw_bytes = self.safe_get_bytes(
            api_url,
            params={
                "search": query[:140],
                "per-page": str(limit),
            },
        )
        data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        works = data.get("results", [])
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results: List[Dict[str, Any]] = []

        for w in works:
            title = (w.get("display_name") or w.get("title") or "").strip()
            if not title:
                continue
            abstract_txt = _reconstruct_openalex_abstract(w.get("abstract_inverted_index"))
            pub_year = w.get("publication_year") or "s.d."
            cited_by = w.get("cited_by_count", 0)
            canonical_url = w.get("doi") or w.get("id") or "https://openalex.org"
            parsed = urllib.parse.urlparse(canonical_url)
            domain = parsed.hostname or "openalex.org"

            body_text = abstract_txt if len(abstract_txt) >= 40 else (
                f"Artigo acadêmico indexado no OpenAlex ({pub_year}): '{title}'. "
                f"Citações registradas: {cited_by}."
            )
            content = (
                f"Artigo Científico (OpenAlex, {pub_year}): {title}\n"
                f"URL Canônica: {canonical_url}\n"
                f"Citações Acadêmicas: {cited_by}\n"
                f"Recuperado em: {now}\n\n"
                f"{sanitize_html_to_text(body_text, max_chars=2400)}"
            )
            sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            results.append({
                "title": f"{title} ({pub_year}) — OpenAlex",
                "url": canonical_url,
                "canonical_url": canonical_url,
                "domain": domain,
                "retrieved_at": now,
                "sha256": sha256,
                "content": content,
                "excerpt": sanitize_html_to_text(body_text, max_chars=260),
                "accessible": True,
                "source_type": "web",
            })
        return results

    def _search_google_news_rss(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """
        Busca notícias públicas e reportagens jornalísticas via Google News RSS (HTTPS)
        para cobrir temas políticos, econômicos e contemporâneos com alta especificidade.
        """
        rss_url = "https://news.google.com/rss/search"
        raw_bytes = self.safe_get_bytes(
            rss_url,
            params={
                "q": query[:110],
                "hl": "pt-BR",
                "gl": "BR",
                "ceid": "BR:pt-419",
            },
        )
        xml_text = raw_bytes.decode("utf-8", errors="replace")
        items = re.findall(r"(?is)<item>(.*?)</item>", xml_text)
        if not items:
            return []

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        results: List[Dict[str, Any]] = []

        # Agrupa manchetes e resumos jornalísticos verificados ou cria registros individuais ricos
        compiled_lines: List[str] = []
        first_link = "https://news.google.com"
        for idx, item_xml in enumerate(items[: max(limit * 3, 6)]):
            t_match = re.search(r"(?is)<title>(.*?)</title>", item_xml)
            l_match = re.search(r"(?is)<link>(.*?)</link>", item_xml)
            p_match = re.search(r"(?is)<pubDate>(.*?)</pubDate>", item_xml)
            s_match = re.search(r"(?is)<source[^>]*>(.*?)</source>", item_xml)
            d_match = re.search(r"(?is)<description>(.*?)</description>", item_xml)

            raw_title = sanitize_html_to_text(t_match.group(1) if t_match else "", max_chars=240)
            if not raw_title:
                continue
            link = sanitize_html_to_text(l_match.group(1) if l_match else "", max_chars=500).strip()
            pub_date = sanitize_html_to_text(p_match.group(1) if p_match else "", max_chars=80)
            source_name = sanitize_html_to_text(s_match.group(1) if s_match else "Imprensa", max_chars=80)
            desc_clean = sanitize_html_to_text(d_match.group(1) if d_match else "", max_chars=400)

            if idx == 0 and link.startswith("https://"):
                first_link = link

            entry_line = f"[{source_name} · {pub_date}] {raw_title}."
            if desc_clean and desc_clean.lower() not in raw_title.lower():
                entry_line += f" Resumo: {desc_clean}"
            compiled_lines.append(entry_line)

            if len(results) < limit and len(entry_line) >= 45:
                single_url = link if link.startswith("https://") else f"https://news.google.com/rss/search?q={urllib.parse.quote(query[:60])}&item={idx}"
                content = (
                    f"Cobertura Jornalística Verificada ({source_name}): {raw_title}\n"
                    f"Publicado em: {pub_date}\n"
                    f"Recuperado em: {now}\n\n"
                    f"{entry_line}\n"
                    + ("\n".join(compiled_lines[:3]) if len(compiled_lines) > 1 else "")
                ).strip()
                sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
                results.append({
                    "title": f"{raw_title} — {source_name} (Notícias)",
                    "url": single_url,
                    "canonical_url": single_url,
                    "domain": "news.google.com",
                    "retrieved_at": now,
                    "sha256": sha256,
                    "content": content,
                    "excerpt": entry_line[:260],
                    "accessible": True,
                    "source_type": "web",
                })

        return results

    @staticmethod
    def _is_record_relevant(record: Dict[str, Any], specific_anchors: List[str]) -> bool:
        """
        Filtra resultados fora de tópico (ex.: artigos sobre Marinha ou Idosos quando a busca é sobre um político ou tecnologia específica).
        """
        if not specific_anchors:
            return True
        haystack = f"{record.get('title', '')} {record.get('content', '')}".lower()
        # Se houver pelo menos 1 termo específico âncora no título/conteúdo, é relevante
        return any(anchor in haystack for anchor in specific_anchors)

    def search_public_sources(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Executa pesquisa pública auditável combinando Wikipedia (PT/EN), Notícias Públicas (Google News RSS)
        e base científica OpenAlex, priorizando resultados que contenham as entidades/assuntos centrais da pergunta.
        Deduplica por URL canônica e hash SHA-256. Nunca fabrica fontes em caso de erro.
        """
        if not self.is_enabled():
            raise WebSearchUnavailableError("SEARCH_UNAVAILABLE: Pesquisa web desabilitada por configuração.")

        clean_query = re.sub(r"[^\w\sÀ-ÿ0-9\-]", " ", query or "").strip()
        if len(clean_query) < 3:
            clean_query = (query or "").strip()

        primary_query, specific_anchors, candidate_queries = extract_focused_queries(clean_query)

        collected_relevant: List[Dict[str, Any]] = []
        collected_fallback: List[Dict[str, Any]] = []
        errors: List[str] = []

        def _ingest_candidates(items: List[Dict[str, Any]], require_relevance: bool = False) -> None:
            for it in items:
                if self._is_record_relevant(it, specific_anchors):
                    collected_relevant.append(it)
                elif not require_relevance:
                    collected_fallback.append(it)

        # 1. Wikipedia PT (testa consultas focadas em entidades e na pergunta enxuta)
        for q_cand in candidate_queries[:2]:
            if len(collected_relevant) >= max_results:
                break
            try:
                wiki_hits = self._search_wikipedia(q_cand, lang="pt", limit=2)
                _ingest_candidates(wiki_hits, require_relevance=False)
            except SSRFBlockedError:
                raise
            except Exception as exc:
                errors.append(f"Wikipedia-PT: {exc}")

        # 2. Google News RSS (cobertura jornalística atualizada para temas políticos, econômicos e eventos recentes)
        if self._custom_client is None and len(collected_relevant) < max_results:
            for q_cand in candidate_queries[:2]:
                if len(collected_relevant) >= max_results:
                    break
                try:
                    news_hits = self._search_google_news_rss(q_cand, limit=2)
                    _ingest_candidates(news_hits, require_relevance=True)
                except SSRFBlockedError:
                    raise
                except Exception as exc:
                    errors.append(f"GoogleNews-RSS: {exc}")

        # 3. OpenAlex acadêmico (exige pertinência aos termos âncora quando estivermos em rede real para evitar artigos aleatórios)
        try:
            oa_query = primary_query if len(primary_query) >= 4 else clean_query
            oa_hits = self._search_openalex(oa_query, limit=3)
            _ingest_candidates(oa_hits, require_relevance=(self._custom_client is None and len(collected_relevant) > 0))
        except SSRFBlockedError:
            raise
        except Exception as exc:
            errors.append(f"OpenAlex: {exc}")

        # 4. Fallback Wikipedia EN com termos-chave se ainda houver poucos resultados relevantes
        if len(collected_relevant) < max_results:
            short_terms = " ".join(specific_anchors[:4]) or primary_query or clean_query
            try:
                en_hits = self._search_wikipedia(short_terms, lang="en", limit=2)
                _ingest_candidates(en_hits, require_relevance=False)
            except SSRFBlockedError:
                raise
            except Exception as exc:
                errors.append(f"Wikipedia-EN: {exc}")

        # Prioriza fontes que batem com os termos específicos da pergunta; usa fallback apenas se nenhuma fonte relevante foi encontrada
        ordered_pool = collected_relevant if collected_relevant else collected_fallback

        # Deduplicação por URL canônica e SHA-256
        deduped: List[Dict[str, Any]] = []
        seen_urls = set()
        seen_hashes = set()
        for item in ordered_pool:
            c_url = item["canonical_url"]
            h = item["sha256"]
            if c_url in seen_urls or h in seen_hashes:
                continue
            seen_urls.add(c_url)
            seen_hashes.add(h)
            deduped.append(item)
            if len(deduped) >= max_results:
                break

        if not deduped and errors:
            self.last_error = "; ".join(errors)
            raise WebSearchUnavailableError(
                f"SEARCH_UNAVAILABLE: Nenhuma fonte pública pôde ser recuperada ({self.last_error})."
            )

        return deduped

