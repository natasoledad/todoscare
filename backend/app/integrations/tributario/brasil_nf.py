"""Constructor de Nota Fiscal eletrônica para Brasil (Tanda 7).

El documento y el órgano competente dependen del hecho gravado:

  · **NFS-e** (serviço) → competência **municipal** (prefeitura). Impuesto:
    **ISS** sobre o valor do serviço, alíquota do município/emissor. Es el caso
    natural de una clínica (prestação de serviço de saúde). XML no padrão ABRASF
    (InfDeclaracaoPrestacaoServico / Servico / Valores).

  · **NF-e** (mercadoria, modelo 55) → competência **estadual** (**SEFAZ** da
    UF). Impuesto: **ICMS**. XML infNFe (emit/dest/det/total/ICMSTot).

  · **NFC-e** (consumidor final, modelo 65) → também estadual (SEFAZ), com CSC.

Punto de enganche real (documentado, no ejecutado aquí): la NFS-e se firma con
o certificado digital (A1/A3) del emisor y se transmite ao webservice da
prefeitura (cada município tem o seu; o padrão nacional NFS-e via gov.br está
em adoção) que devolve o **número da NFS-e** e o **código de verificação**; a
NF-e/NFC-e se autoriza na SEFAZ estadual, que devolve o **protocolo de
autorização** e a chave de acesso de 44 dígitos. Aquí número, protocolo y
código son deterministas (hash del contenido) para verificar el flujo sin
credenciales.
"""

import hashlib
from xml.sax.saxutils import escape

MODELOS = {"nfe": "55", "nfce": "65", "nfse": None}

ISS_ALIQUOTA_DEFAULT = 0.05  # 5% — típica para serviços de saúde
ICMS_ALIQUOTA_DEFAULT = 0.18


def _brl(x: float) -> float:
    return round(float(x), 2)


def _protocolo(seed: str) -> str:
    """Protocolo de autorização (15 dígitos, como SEFAZ) determinista."""
    return str(int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 10**15).zfill(15)


def _codigo_verificacao(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:9].upper()


def _base(items: list[dict]) -> float:
    return _brl(sum(it["cantidad"] * it["precio_unitario"] for it in items))


def _build_nfse(*, numero: int, serie: str | None, emitter, receptor, items, fecha) -> dict:
    cfg = emitter.config or {}
    base = _base(items)
    aliquota = float(cfg.get("iss_aliquota", ISS_ALIQUOTA_DEFAULT))
    iss = _brl(base * aliquota)
    municipio = str(cfg.get("municipio_ibge", ""))
    municipio_nome = str(cfg.get("municipio_nome", "Município"))

    servicos_xml = "".join(
        f"<Servico><Discriminacao>{escape(str(it['descripcion']))}</Discriminacao>"
        f"<Quantidade>{it['cantidad']}</Quantidade>"
        f"<ValorUnitario>{_brl(it['precio_unitario']):.2f}</ValorUnitario></Servico>"
        for it in items
    )
    seed = f"NFSE|{emitter.tax_id}|{numero}|{base}|{fecha}"
    codigo_verif = _codigo_verificacao(seed)
    xml = (
        '<CompNfse><Nfse><InfNfse>'
        f"<Numero>{numero}</Numero><CodigoVerificacao>{codigo_verif}</CodigoVerificacao>"
        f"<DataEmissao>{fecha}</DataEmissao>"
        "<PrestadorServico>"
        f"<Cnpj>{emitter.tax_id}</Cnpj>"
        f"<InscricaoMunicipal>{escape(str(cfg.get('inscricao_municipal', '')))}</InscricaoMunicipal>"
        f"<RazaoSocial>{escape(emitter.razon_social)}</RazaoSocial></PrestadorServico>"
        "<TomadorServico>"
        f"<CpfCnpj>{escape((receptor or {}).get('tax_id') or '')}</CpfCnpj>"
        f"<RazaoSocial>{escape((receptor or {}).get('nombre') or 'Consumidor final')}</RazaoSocial>"
        "</TomadorServico>"
        "<InfDeclaracaoPrestacaoServico><Servicos>"
        f"{servicos_xml}"
        "<Valores>"
        f"<ValorServicos>{base:.2f}</ValorServicos>"
        f"<Aliquota>{aliquota:.4f}</Aliquota>"
        f"<ValorIss>{iss:.2f}</ValorIss></Valores>"
        f"<CodigoMunicipio>{escape(municipio)}</CodigoMunicipio>"
        "</Servicos></InfDeclaracaoPrestacaoServico>"
        "</InfNfse></Nfse></CompNfse>"
    )
    return {
        "codigo": None,
        "jurisdiccion": "municipal",
        "organo": f"Prefeitura de {municipio_nome}",
        "neto": base,
        "exento": 0,
        "impuesto": iss,
        "total": base,
        "impuesto_detalle": {"tipo": "ISS", "tasa": aliquota, "monto": iss},
        "sello": codigo_verif,
        "track_id": _protocolo(seed),
        "xml": xml,
        "estado": "aceptado",
    }


def _build_nfe(*, tipo_documento: str, numero: int, serie: str | None, emitter, receptor, items, fecha) -> dict:
    cfg = emitter.config or {}
    modelo = MODELOS[tipo_documento]  # 55 | 65
    base = _base(items)
    aliquota = float(cfg.get("icms_aliquota", ICMS_ALIQUOTA_DEFAULT))
    icms = _brl(base * aliquota)  # ICMS "por dentro" (já incluso no preço)
    uf = str(cfg.get("uf", "SP"))

    det_xml = ""
    for i, it in enumerate(items, start=1):
        v = _brl(it["cantidad"] * it["precio_unitario"])
        det_xml += (
            f'<det nItem="{i}"><prod>'
            f"<xProd>{escape(str(it['descripcion']))}</xProd>"
            f"<qCom>{it['cantidad']}</qCom>"
            f"<vUnCom>{_brl(it['precio_unitario']):.2f}</vUnCom>"
            f"<vProd>{v:.2f}</vProd></prod></det>"
        )
    seed = f"{tipo_documento.upper()}|{emitter.tax_id}|{modelo}|{serie}|{numero}|{base}|{fecha}"
    # Chave de acesso NF-e: 44 dígitos (UF+AAMM+CNPJ+mod+serie+nNF+...). Simulada.
    chave = hashlib.sha256(seed.encode()).hexdigest()
    chave = "".join(c for c in chave if c.isdigit()).ljust(44, "0")[:44]
    xml = (
        f'<nfeProc><NFe><infNFe Id="NFe{chave}" versao="4.00">'
        f"<ide><cUF>{escape(uf)}</cUF><mod>{modelo}</mod>"
        f"<serie>{escape(serie or '1')}</serie><nNF>{numero}</nNF><dhEmi>{fecha}</dhEmi></ide>"
        f"<emit><CNPJ>{emitter.tax_id}</CNPJ><xNome>{escape(emitter.razon_social)}</xNome>"
        f"<IE>{escape(str(cfg.get('inscricao_estadual', '')))}</IE></emit>"
        f"<dest><CPF_CNPJ>{escape((receptor or {}).get('tax_id') or '')}</CPF_CNPJ>"
        f"<xNome>{escape((receptor or {}).get('nombre') or 'Consumidor final')}</xNome></dest>"
        f"{det_xml}"
        f"<total><ICMSTot><vProd>{base:.2f}</vProd><vICMS>{icms:.2f}</vICMS>"
        f"<vNF>{base:.2f}</vNF></ICMSTot></total>"
        "</infNFe></NFe>"
        f"<protNFe><infProt><chNFe>{chave}</chNFe><nProt>{_protocolo(seed)}</nProt>"
        "<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>"
        "</nfeProc>"
    )
    return {
        "codigo": modelo,
        "jurisdiccion": "estatal",
        "organo": f"SEFAZ-{uf}",
        "neto": base,
        "exento": 0,
        "impuesto": icms,
        "total": base,
        "impuesto_detalle": {"tipo": "ICMS", "tasa": aliquota, "monto": icms, "chave": chave},
        "sello": chave,
        "track_id": _protocolo(seed),
        "xml": xml,
        "estado": "aceptado",
    }


def build_nf(
    *,
    tipo_documento: str,
    numero: int,
    serie: str | None,
    emitter,
    receptor: dict | None,
    items: list[dict],
    fecha: str,
) -> dict:
    """Enruta al órgano competente según o tipo de documento."""
    out = (
        _build_nfse(numero=numero, serie=serie, emitter=emitter, receptor=receptor, items=items, fecha=fecha)
        if tipo_documento == "nfse"
        else _build_nfe(tipo_documento=tipo_documento, numero=numero, serie=serie, emitter=emitter, receptor=receptor, items=items, fecha=fecha)
    )
    out["moneda"] = "BRL"
    return out
