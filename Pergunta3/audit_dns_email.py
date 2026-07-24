#!/usr/bin/env python3
"""
audit_dns_email.py

Dado um dominio, verifica os registros SPF, DKIM, DMARC e PTR/rDNS
e gera um relatorio indicando o que esta presente, ausente ou
possivelmente mal configurado.

Requisitos:
    pip install dnspython

Uso:
    python3 audit_dns_email.py dominio.com.br
    python3 audit_dns_email.py dominio.com.br --selectors default,google,selector1
    python3 audit_dns_email.py dominio.com.br --mx-ptr   # tambem verifica PTR dos MXs
"""

import argparse
import sys
import socket
import textwrap

try:
    import dns.resolver
    import dns.reversename
    import dns.exception
except ImportError:
    print("Erro: o modulo 'dnspython' nao esta instalado.")
    print("Instale com: pip install dnspython")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

# Selectors DKIM comuns usados como tentativa quando o usuario nao informa
# selectors especificos (o DKIM nao tem um local fixo/descobrivel via DNS,
# entao isso e uma varredura heuristica, nao uma garantia de cobertura total).
DEFAULT_DKIM_SELECTORS = [
    "default", "selector1", "selector2", "google", "k1", "k2",
    "mail", "dkim", "s1", "s2", "smtp", "email", "mandrill",
    "sendgrid", "amazonses", "zoho", "mx",
]

DNS_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Utilitarios de cor / formatacao (ANSI, com fallback silencioso)
# ---------------------------------------------------------------------------

class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def status_tag(status):
    """status: OK | AUSENTE | AVISO | ERRO"""
    mapping = {
        "OK": f"{C.GREEN}{C.BOLD}[ OK ]{C.RESET}",
        "AUSENTE": f"{C.RED}{C.BOLD}[AUSENTE]{C.RESET}",
        "AVISO": f"{C.YELLOW}{C.BOLD}[AVISO]{C.RESET}",
        "ERRO": f"{C.RED}{C.BOLD}[ERRO]{C.RESET}",
    }
    return mapping.get(status, f"[{status}]")


# ---------------------------------------------------------------------------
# Funcoes de consulta DNS
# ---------------------------------------------------------------------------

def get_resolver():
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT
    resolver.lifetime = DNS_TIMEOUT
    return resolver


def query_txt(resolver, name):
    """Retorna lista de strings TXT (ja concatenadas) para um nome, ou [] se nao existir."""
    try:
        answers = resolver.resolve(name, "TXT")
        results = []
        for rdata in answers:
            # rdata.strings e uma tupla de bytes (TXT pode ter multiplas strings)
            txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
            results.append(txt)
        return results
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.Timeout:
        raise TimeoutError(f"Timeout consultando TXT em {name}")
    except Exception as exc:
        raise RuntimeError(f"Erro consultando TXT em {name}: {exc}")


def query_a(resolver, name):
    try:
        answers = resolver.resolve(name, "A")
        return [r.address for r in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.Timeout:
        raise TimeoutError(f"Timeout consultando A em {name}")


def query_mx(resolver, name):
    try:
        answers = resolver.resolve(name, "MX")
        return sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0],
        )
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.Timeout:
        raise TimeoutError(f"Timeout consultando MX em {name}")


def query_ptr(resolver, ip):
    """Retorna lista de PTRs (hostnames) para um IP, ou [] se nao existir."""
    try:
        rev_name = dns.reversename.from_address(ip)
        answers = resolver.resolve(rev_name, "PTR")
        return [str(r).rstrip(".") for r in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.Timeout:
        raise TimeoutError(f"Timeout consultando PTR em {ip}")


# ---------------------------------------------------------------------------
# Verificacoes especificas
# ---------------------------------------------------------------------------

def check_spf(resolver, domain, report):
    report.section("SPF (Sender Policy Framework)")
    try:
        txts = query_txt(resolver, domain)
    except (TimeoutError, RuntimeError) as e:
        report.add("ERRO", "SPF", str(e))
        return

    spf_records = [t for t in txts if t.lower().startswith("v=spf1")]

    if not spf_records:
        report.add("AUSENTE", "SPF",
                    f"Nenhum registro TXT 'v=spf1' encontrado em {domain}.")
        return

    if len(spf_records) > 1:
        report.add("ERRO", "SPF",
                    f"Foram encontrados {len(spf_records)} registros SPF. "
                    "So deve existir UM registro SPF por dominio (RFC 7208); "
                    "multiplos registros invalidam a checagem SPF.")

    spf = spf_records[0]
    report.add("OK", "SPF", f"Registro encontrado: {spf}")

    # Checagens de qualidade dentro do registro
    mechanisms = spf.split()

    if "+all" in mechanisms:
        report.add("AVISO", "SPF",
                    "Mecanismo '+all' permite que QUALQUER servidor envie "
                    "e-mails em nome do dominio. Extremamente permissivo, evite.")
    elif "?all" in mechanisms:
        report.add("AVISO", "SPF",
                    "Mecanismo '?all' (neutro) nao define politica de rejeicao. "
                    "Considere usar '-all' (fail) ou '~all' (softfail).")
    elif "~all" in mechanisms:
        report.add("AVISO", "SPF",
                    "Mecanismo '~all' (softfail) esta presente. Funciona, mas "
                    "'-all' (hardfail) e mais rigoroso e recomendado para dominios maduros.")
    elif "-all" in mechanisms:
        report.add("OK", "SPF", "Mecanismo '-all' (hardfail) presente - boa pratica.")
    else:
        report.add("AVISO", "SPF",
                    "Nenhum qualificador 'all' encontrado no final do registro. "
                    "Sem isso, o SPF fica incompleto (sem politica padrao definida).")

    # Contagem de lookups DNS (limite RFC 7208 = 10)
    lookup_mechanisms = ("include:", "a", "mx", "ptr", "exists:", "redirect=")
    lookup_count = 0
    for mech in mechanisms:
        m = mech.lstrip("+-~?")
        if m.startswith(lookup_mechanisms) or m in ("a", "mx", "ptr"):
            lookup_count += 1

    if lookup_count > 10:
        report.add("ERRO", "SPF",
                    f"Aproximadamente {lookup_count} mecanismos que geram consulta DNS "
                    "(include/a/mx/ptr/exists/redirect). O limite do RFC 7208 e 10 "
                    "lookups; excedendo isso o SPF pode resultar em 'permerror'.")
    elif lookup_count >= 8:
        report.add("AVISO", "SPF",
                    f"Aproximadamente {lookup_count} mecanismos de lookup DNS, "
                    "proximo do limite de 10 do RFC 7208. Monitore antes de adicionar mais 'include'.")


def check_dmarc(resolver, domain, report):
    report.section("DMARC (Domain-based Message Authentication)")
    dmarc_name = f"_dmarc.{domain}"
    try:
        txts = query_txt(resolver, dmarc_name)
    except (TimeoutError, RuntimeError) as e:
        report.add("ERRO", "DMARC", str(e))
        return

    dmarc_records = [t for t in txts if t.lower().startswith("v=dmarc1")]

    if not dmarc_records:
        report.add("AUSENTE", "DMARC",
                    f"Nenhum registro TXT 'v=DMARC1' encontrado em {dmarc_name}.")
        return

    if len(dmarc_records) > 1:
        report.add("ERRO", "DMARC",
                    f"Foram encontrados {len(dmarc_records)} registros DMARC em "
                    f"{dmarc_name}. Deve existir apenas UM.")

    dmarc = dmarc_records[0]
    report.add("OK", "DMARC", f"Registro encontrado: {dmarc}")

    tags = {}
    for part in dmarc.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k.strip().lower()] = v.strip()

    policy = tags.get("p")
    if not policy:
        report.add("ERRO", "DMARC", "Tag obrigatoria 'p' (politica) ausente no registro.")
    elif policy == "none":
        report.add("AVISO", "DMARC",
                    "Politica 'p=none' apenas monitora, nao bloqueia nem coloca "
                    "em quarentena mensagens que falham na autenticacao. "
                    "Considere evoluir para 'quarantine' ou 'reject' apos validar os relatorios.")
    elif policy == "quarantine":
        report.add("OK", "DMARC", "Politica 'p=quarantine' esta ativa (nivel intermediario).")
    elif policy == "reject":
        report.add("OK", "DMARC", "Politica 'p=reject' esta ativa (nivel mais rigoroso).")
    else:
        report.add("AVISO", "DMARC", f"Valor de politica '{policy}' nao reconhecido.")

    if "rua" not in tags:
        report.add("AVISO", "DMARC",
                    "Tag 'rua' (destinatario de relatorios agregados) nao configurada. "
                    "Sem ela, nao ha visibilidade sobre falhas de autenticacao.")
    else:
        report.add("OK", "DMARC", f"Relatorios agregados configurados: rua={tags['rua']}")

    if "ruf" in tags:
        report.add("OK", "DMARC", f"Relatorios forenses configurados: ruf={tags['ruf']}")

    pct = tags.get("pct")
    if pct and pct != "100":
        report.add("AVISO", "DMARC",
                    f"Tag 'pct={pct}' indica que a politica se aplica apenas a "
                    f"{pct}% das mensagens. Considere elevar para 100% quando possivel.")

    sp = tags.get("sp")
    if not sp:
        report.add("AVISO", "DMARC",
                    "Tag 'sp' (politica para subdominios) nao definida; "
                    "subdominios herdarao a politica de 'p', o que pode nao ser desejado.")


def check_dkim(resolver, domain, report, selectors):
    report.section("DKIM (DomainKeys Identified Mail)")
    report.add("AVISO", "DKIM",
               "Nao existe um jeito padronizado de descobrir o(s) selector(es) DKIM "
               "via DNS. A verificacao abaixo testa uma lista de selectors comuns; "
               "se o selector real do dominio nao estiver na lista, use --selectors "
               "para informa-lo manualmente (ex.: verifique no painel do provedor "
               "de e-mail ou nos headers de uma mensagem enviada).")

    found_any = False
    for selector in selectors:
        name = f"{selector}._domainkey.{domain}"
        try:
            txts = query_txt(resolver, name)
        except (TimeoutError, RuntimeError) as e:
            report.add("ERRO", "DKIM", f"[{selector}] {e}")
            continue

        dkim_records = [t for t in txts if "v=dkim1" in t.lower() or "p=" in t.lower()]

        if not dkim_records:
            continue

        found_any = True
        record = dkim_records[0]
        report.add("OK", "DKIM", f"Selector '{selector}' encontrado em {name}")

        tags = {}
        for part in record.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                tags[k.strip().lower()] = v.strip()

        pub_key = tags.get("p", "")
        if pub_key == "":
            report.add("ERRO", "DKIM",
                        f"Selector '{selector}': tag 'p' (chave publica) vazia. "
                        "Isso indica uma chave REVOGADA/desativada.")
        else:
            key_len_approx = len(pub_key) * 6 // 8  # base64 aproximado em bits
            report.add("OK", "DKIM",
                        f"Selector '{selector}': chave publica presente "
                        f"(~{key_len_approx * 8 // 8} caracteres base64).")

        htype = tags.get("h")
        if htype:
            report.add("OK", "DKIM", f"Selector '{selector}': algoritmo de hash declarado: {htype}")

    if not found_any:
        report.add("AUSENTE", "DKIM",
                    f"Nenhum registro DKIM encontrado nos selectors testados: "
                    f"{', '.join(selectors)}.")


def check_ptr_rdns(resolver, domain, report, check_mx_ptr=False):
    report.section("PTR / rDNS (Reverse DNS)")

    try:
        ips = query_a(resolver, domain)
    except TimeoutError as e:
        report.add("ERRO", "PTR", str(e))
        ips = []

    if not ips:
        report.add("AVISO", "PTR",
                    f"O dominio {domain} nao possui registro A direto; "
                    "isso e normal se o dominio nao aponta para um servidor web/mail "
                    "propriamente dito. Verificando PTR dos MXs abaixo.")
    else:
        for ip in ips:
            _check_single_ptr(resolver, ip, domain, report, label=domain)

    # Verifica tambem os IPs dos servidores MX, que sao os que efetivamente
    # enviam/recebem e-mail e onde o PTR realmente importa para deliverability.
    try:
        mx_records = query_mx(resolver, domain)
    except TimeoutError as e:
        report.add("ERRO", "MX", str(e))
        mx_records = []

    if not mx_records:
        report.add("AVISO", "MX",
                    f"Nenhum registro MX encontrado para {domain}. "
                    "Sem MX, o dominio nao recebe e-mails diretamente.")
        return

    report.add("OK", "MX",
               "Registros MX: " + ", ".join(f"{pref} {host}" for pref, host in mx_records))

    if check_mx_ptr:
        for _, mx_host in mx_records:
            try:
                mx_ips = query_a(resolver, mx_host)
            except TimeoutError as e:
                report.add("ERRO", "PTR", str(e))
                continue
            if not mx_ips:
                report.add("AVISO", "PTR", f"MX {mx_host} nao resolveu para um IP A.")
                continue
            for ip in mx_ips:
                _check_single_ptr(resolver, ip, mx_host, report, label=f"MX {mx_host}")


def _check_single_ptr(resolver, ip, expected_host, report, label):
    try:
        ptrs = query_ptr(resolver, ip)
    except TimeoutError as e:
        report.add("ERRO", "PTR", str(e))
        return

    if not ptrs:
        report.add("AUSENTE", "PTR",
                    f"{label} ({ip}): nenhum registro PTR configurado. "
                    "Muitos servidores de e-mail rejeitam ou penalizam envios "
                    "de IPs sem rDNS.")
        return

    ptr_host = ptrs[0]
    report.add("OK", "PTR", f"{label} ({ip}): PTR = {ptr_host}")

    # FCrDNS (Forward-Confirmed reverse DNS): o PTR deve resolver de volta
    # (via A) para o mesmo IP, idealmente.
    try:
        forward_ips = query_a(resolver, ptr_host)
    except TimeoutError:
        forward_ips = []

    if ip in forward_ips:
        report.add("OK", "PTR", f"{label} ({ip}): FCrDNS confirmado (PTR aponta de volta ao IP).")
    else:
        report.add("AVISO", "PTR",
                    f"{label} ({ip}): o PTR '{ptr_host}' nao resolve de volta para {ip} "
                    "(sem forward-confirmation). Alguns filtros antispam avaliam isso.")


# ---------------------------------------------------------------------------
# Estrutura do relatorio
# ---------------------------------------------------------------------------

class Report:
    def __init__(self, domain):
        self.domain = domain
        self.items = []          # (secao, status, categoria, mensagem)
        self.current_section = None
        self.counts = {"OK": 0, "AUSENTE": 0, "AVISO": 0, "ERRO": 0}

    def section(self, title):
        self.current_section = title

    def add(self, status, category, message):
        self.items.append((self.current_section, status, category, message))
        self.counts[status] = self.counts.get(status, 0) + 1

    def print_console(self):
        print()
        print(f"{C.BOLD}{'='*70}{C.RESET}")
        print(f"{C.BOLD}Relatorio de auditoria DNS de e-mail: {self.domain}{C.RESET}")
        print(f"{C.BOLD}{'='*70}{C.RESET}")

        last_section = None
        for section, status, category, message in self.items:
            if section != last_section:
                print(f"\n{C.BLUE}{C.BOLD}--- {section} ---{C.RESET}")
                last_section = section
            wrapped = textwrap.fill(
                message, width=100, subsequent_indent=" " * 18
            )
            print(f"{status_tag(status)} {C.BOLD}{category:8s}{C.RESET} {wrapped}")

        print(f"\n{C.BOLD}{'='*70}{C.RESET}")
        print(f"{C.BOLD}Resumo:{C.RESET} "
              f"{C.GREEN}OK={self.counts['OK']}{C.RESET}  "
              f"{C.RED}AUSENTE={self.counts['AUSENTE']}{C.RESET}  "
              f"{C.YELLOW}AVISO={self.counts['AVISO']}{C.RESET}  "
              f"{C.RED}ERRO={self.counts['ERRO']}{C.RESET}")
        print(f"{C.BOLD}{'='*70}{C.RESET}\n")

    def write_text_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Relatorio de auditoria DNS de e-mail: {self.domain}\n")
            f.write("=" * 70 + "\n")
            last_section = None
            for section, status, category, message in self.items:
                if section != last_section:
                    f.write(f"\n--- {section} ---\n")
                    last_section = section
                f.write(f"[{status}] {category}: {message}\n")
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"Resumo: OK={self.counts['OK']}  AUSENTE={self.counts['AUSENTE']}  "
                    f"AVISO={self.counts['AVISO']}  ERRO={self.counts['ERRO']}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audita registros SPF, DKIM, DMARC e PTR/rDNS de um dominio."
    )
    parser.add_argument("domain", help="Dominio a ser auditado (ex.: exemplo.com.br)")
    parser.add_argument(
        "--selectors",
        help="Lista de selectors DKIM separados por virgula para testar "
             f"(padrao: {', '.join(DEFAULT_DKIM_SELECTORS)})",
        default=None,
    )
    parser.add_argument(
        "--mx-ptr",
        action="store_true",
        help="Tambem verifica o PTR/rDNS dos IPs dos servidores MX (recomendado).",
    )
    parser.add_argument(
        "--output", "-o",
        help="Caminho para salvar o relatorio tambem em arquivo de texto.",
        default=None,
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Desativa cores ANSI na saida do console.",
    )
    args = parser.parse_args()

    if args.no_color:
        for attr in ("GREEN", "RED", "YELLOW", "BLUE", "BOLD", "RESET"):
            setattr(C, attr, "")

    domain = args.domain.strip().rstrip(".")
    selectors = (
        [s.strip() for s in args.selectors.split(",") if s.strip()]
        if args.selectors else DEFAULT_DKIM_SELECTORS
    )

    resolver = get_resolver()
    report = Report(domain)

    check_spf(resolver, domain, report)
    check_dkim(resolver, domain, report, selectors)
    check_dmarc(resolver, domain, report)
    check_ptr_rdns(resolver, domain, report, check_mx_ptr=args.mx_ptr)

    report.print_console()

    if args.output:
        report.write_text_file(args.output)
        print(f"Relatorio tambem salvo em: {args.output}")

    # Exit code util para automacao/CI: 0 se nao houver AUSENTE/ERRO, 1 caso contrario
    if report.counts["AUSENTE"] > 0 or report.counts["ERRO"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
