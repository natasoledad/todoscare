"""Aranceles multi-tabla (punto 62): tablas de precio con categorías y
prestaciones. Coexiste con el catálogo de servicios; el arancel es la lista de
precios para cotizar/cobrar (base, particular, por empresa/convenio)."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tariff import Arancel, ArancelCategoria, ArancelItem
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.aranceles import (
    ArancelIn,
    ArancelOut,
    ArancelUpdate,
    CategoriaIn,
    CategoriaOut,
    CategoriaUpdate,
    CopiarBaseOut,
    ImportarArancelIn,
    ImportarArancelOut,
    ImportErrorItem,
    IncrementarIn,
    IncrementarOut,
    ItemIn,
    ItemOut,
    ItemUpdate,
)
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/aranceles", tags=["aranceles"])


# ─────────────────────────── aranceles ───────────────────────────
async def _n_items(db: AsyncSession, arancel_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(ArancelItem).where(ArancelItem.arancel_id == arancel_id, ArancelItem.deleted_at.is_(None))
        )
    ).scalar_one()


async def _own_arancel(db: AsyncSession, clinic_id: uuid.UUID, arancel_id: uuid.UUID) -> Arancel:
    a = await db.get(Arancel, arancel_id)
    if a is None or a.deleted_at is not None or a.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arancel no encontrado")
    return a


async def _clear_base(db: AsyncSession, clinic_id: uuid.UUID, keep_id: uuid.UUID | None = None) -> None:
    rows = (await db.execute(select(Arancel).where(Arancel.clinic_id == clinic_id, Arancel.es_base.is_(True), Arancel.deleted_at.is_(None)))).scalars().all()
    for a in rows:
        if a.id != keep_id:
            a.es_base = False


@router.get("", response_model=list[ArancelOut])
async def list_aranceles(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[ArancelOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(Arancel).where(Arancel.clinic_id == clinic_id, Arancel.deleted_at.is_(None)).order_by(Arancel.nombre))).scalars().all()
    return [ArancelOut(id=a.id, nombre=a.nombre, tipo=a.tipo, es_base=a.es_base, activo=a.activo, n_items=await _n_items(db, a.id)) for a in rows]


@router.post("", response_model=ArancelOut, status_code=status.HTTP_201_CREATED)
async def crear_arancel(
    payload: ArancelIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> ArancelOut:
    clinic_id = empresa_clinic_id(ctx)
    a = Arancel(clinic_id=clinic_id, nombre=payload.nombre, tipo=payload.tipo, es_base=payload.es_base)
    if payload.es_base:
        await _clear_base(db, clinic_id)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return ArancelOut(id=a.id, nombre=a.nombre, tipo=a.tipo, es_base=a.es_base, activo=a.activo, n_items=0)


@router.patch("/{arancel_id}", response_model=ArancelOut)
async def editar_arancel(
    arancel_id: uuid.UUID,
    payload: ArancelUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> ArancelOut:
    clinic_id = empresa_clinic_id(ctx)
    a = await _own_arancel(db, clinic_id, arancel_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("es_base") is True:
        await _clear_base(db, clinic_id, keep_id=a.id)
    for k, v in data.items():
        setattr(a, k, v)
    await db.commit()
    await db.refresh(a)
    return ArancelOut(id=a.id, nombre=a.nombre, tipo=a.tipo, es_base=a.es_base, activo=a.activo, n_items=await _n_items(db, a.id))


@router.delete("/{arancel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_arancel(
    arancel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    a = await _own_arancel(db, clinic_id, arancel_id)
    await db.delete(a)
    await db.commit()


# ─────────────────────────── categorías ───────────────────────────
async def _own_categoria(db: AsyncSession, clinic_id: uuid.UUID, cat_id: uuid.UUID) -> ArancelCategoria:
    c = await db.get(ArancelCategoria, cat_id)
    if c is None or c.deleted_at is not None or c.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    return c


@router.get("/{arancel_id}/categorias", response_model=list[CategoriaOut])
async def list_categorias(
    arancel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[CategoriaOut]:
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)
    rows = (await db.execute(select(ArancelCategoria).where(ArancelCategoria.arancel_id == arancel_id, ArancelCategoria.deleted_at.is_(None)).order_by(ArancelCategoria.orden, ArancelCategoria.nombre))).scalars().all()
    return [CategoriaOut(id=c.id, arancel_id=c.arancel_id, nombre=c.nombre, orden=c.orden) for c in rows]


@router.post("/{arancel_id}/categorias", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    arancel_id: uuid.UUID,
    payload: CategoriaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> CategoriaOut:
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)
    c = ArancelCategoria(clinic_id=clinic_id, arancel_id=arancel_id, nombre=payload.nombre, orden=payload.orden)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CategoriaOut(id=c.id, arancel_id=c.arancel_id, nombre=c.nombre, orden=c.orden)


@router.patch("/categorias/{cat_id}", response_model=CategoriaOut)
async def editar_categoria(
    cat_id: uuid.UUID,
    payload: CategoriaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> CategoriaOut:
    clinic_id = empresa_clinic_id(ctx)
    c = await _own_categoria(db, clinic_id, cat_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return CategoriaOut(id=c.id, arancel_id=c.arancel_id, nombre=c.nombre, orden=c.orden)


@router.delete("/categorias/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_categoria(
    cat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    c = await _own_categoria(db, clinic_id, cat_id)
    await db.delete(c)
    await db.commit()


# ─────────────────────────── ítems (prestaciones) ───────────────────────────
async def _item_out(db: AsyncSession, i: ArancelItem) -> ItemOut:
    cat = await db.get(ArancelCategoria, i.categoria_id) if i.categoria_id else None
    return ItemOut(
        id=i.id, arancel_id=i.arancel_id, categoria_id=i.categoria_id, categoria_nombre=cat.nombre if cat else None,
        codigo=i.codigo, nombre=i.nombre, precio=float(i.precio),
        precio_referencia=float(i.precio_referencia) if i.precio_referencia is not None else None,
        permite_descuento=i.permite_descuento, comisiona=i.comisiona, activo=i.activo,
    )


async def _own_item(db: AsyncSession, clinic_id: uuid.UUID, item_id: uuid.UUID) -> ArancelItem:
    i = await db.get(ArancelItem, item_id)
    if i is None or i.deleted_at is not None or i.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prestación no encontrada")
    return i


@router.get("/{arancel_id}/items", response_model=list[ItemOut])
async def list_items(
    arancel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.VER)),
) -> list[ItemOut]:
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)
    rows = (await db.execute(select(ArancelItem).where(ArancelItem.arancel_id == arancel_id, ArancelItem.deleted_at.is_(None)).order_by(ArancelItem.codigo, ArancelItem.nombre))).scalars().all()
    return [await _item_out(db, i) for i in rows]


@router.post("/{arancel_id}/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def crear_item(
    arancel_id: uuid.UUID,
    payload: ItemIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> ItemOut:
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)
    if payload.categoria_id is not None:
        await _own_categoria(db, clinic_id, payload.categoria_id)
    i = ArancelItem(
        clinic_id=clinic_id, arancel_id=arancel_id, categoria_id=payload.categoria_id, codigo=payload.codigo,
        nombre=payload.nombre, precio=payload.precio, precio_referencia=payload.precio_referencia,
        permite_descuento=payload.permite_descuento, comisiona=payload.comisiona,
    )
    db.add(i)
    await db.commit()
    await db.refresh(i)
    return await _item_out(db, i)


@router.patch("/items/{item_id}", response_model=ItemOut)
async def editar_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> ItemOut:
    clinic_id = empresa_clinic_id(ctx)
    i = await _own_item(db, clinic_id, item_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("categoria_id") is not None:
        await _own_categoria(db, clinic_id, data["categoria_id"])
    for k, v in data.items():
        setattr(i, k, v)
    await db.commit()
    await db.refresh(i)
    return await _item_out(db, i)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    i = await _own_item(db, clinic_id, item_id)
    await db.delete(i)
    await db.commit()


# ─────────────────────────── carga masiva (62.8) ───────────────────────────
_HEADER_ALIAS = {
    "codigo": "codigo", "código": "codigo", "code": "codigo",
    "nombre": "nombre", "prestacion": "nombre", "prestación": "nombre", "descripcion": "nombre", "descripción": "nombre",
    "precio": "precio", "valor": "precio", "precio_final": "precio",
    "categoria": "categoria", "categoría": "categoria", "grupo": "categoria",
    "precio_referencia": "precio_referencia", "referencia": "precio_referencia", "fonasa": "precio_referencia",
}
_ORDEN_SIN_ENCABEZADO = ["codigo", "nombre", "precio", "categoria", "precio_referencia"]


def _parse_precio(texto: str) -> float:
    """Interpreta precios en formato chileno o inglés ('12.345', '12.345,50',
    '$ 12.345', '12345.50')."""
    s = "".join(ch for ch in str(texto) if ch.isdigit() or ch in ".,-").strip()
    if not s:
        raise ValueError("precio vacío")
    if "," in s and "." in s:          # 12.345,50 -> el último separador es el decimal
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:                     # 12345,50 -> coma decimal
        s = s.replace(",", ".")
    elif s.count(".") > 1:             # 1.234.567 -> puntos de miles
        s = s.replace(".", "")
    elif "." in s and len(s.rsplit(".", 1)[1]) == 3:  # 25.000 -> punto de miles (formato CL)
        s = s.replace(".", "")
    return round(float(s), 2)


@router.post("/{arancel_id}/importar", response_model=ImportarArancelOut)
async def importar_items(
    arancel_id: uuid.UUID,
    payload: ImportarArancelIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> ImportarArancelOut:
    """Carga masiva de prestaciones desde CSV/Excel (62.8). Columnas: código,
    nombre, precio, categoría, precio de referencia. Autocrea categorías por
    nombre; si el código ya existe en el arancel, actualiza (upsert)."""
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)

    texto = payload.contenido.strip()
    sep = payload.separador or (";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ",")
    filas = list(csv.reader(io.StringIO(texto), delimiter=sep))
    if not filas:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Archivo vacío")

    if payload.tiene_encabezado:
        cabecera = [_HEADER_ALIAS.get(c.strip().lower(), c.strip().lower()) for c in filas[0]]
        datos = filas[1:]
    else:
        cabecera = _ORDEN_SIN_ENCABEZADO
        datos = filas
    idx = {campo: cabecera.index(campo) for campo in set(cabecera) if campo in ("codigo", "nombre", "precio", "categoria", "precio_referencia")}
    if "nombre" not in idx or "precio" not in idx:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Faltan columnas obligatorias: nombre y precio")

    # cache de categorías del arancel por nombre (crea las que falten)
    cats = (await db.execute(select(ArancelCategoria).where(ArancelCategoria.arancel_id == arancel_id, ArancelCategoria.deleted_at.is_(None)))).scalars().all()
    cat_by_nombre = {c.nombre.strip().lower(): c for c in cats}
    items = (await db.execute(select(ArancelItem).where(ArancelItem.arancel_id == arancel_id, ArancelItem.deleted_at.is_(None)))).scalars().all()
    item_by_codigo = {i.codigo: i for i in items if i.codigo}

    creados = actualizados = 0
    errores: list[ImportErrorItem] = []
    base_fila = 2 if payload.tiene_encabezado else 1
    for n, fila in enumerate(datos, start=base_fila):
        if not any(c.strip() for c in fila):
            continue
        try:
            nombre = fila[idx["nombre"]].strip()
            if not nombre:
                raise ValueError("nombre vacío")
            precio = _parse_precio(fila[idx["precio"]])
            codigo = fila[idx["codigo"]].strip() if "codigo" in idx and idx["codigo"] < len(fila) else None
            codigo = codigo or None
            categoria_id = None
            if "categoria" in idx and idx["categoria"] < len(fila) and fila[idx["categoria"]].strip():
                nom_cat = fila[idx["categoria"]].strip()
                cat = cat_by_nombre.get(nom_cat.lower())
                if cat is None:
                    cat = ArancelCategoria(clinic_id=clinic_id, arancel_id=arancel_id, nombre=nom_cat)
                    db.add(cat)
                    await db.flush()
                    cat_by_nombre[nom_cat.lower()] = cat
                categoria_id = cat.id
            pref = None
            if "precio_referencia" in idx and idx["precio_referencia"] < len(fila) and fila[idx["precio_referencia"]].strip():
                pref = _parse_precio(fila[idx["precio_referencia"]])

            existente = item_by_codigo.get(codigo) if codigo else None
            if existente is not None:
                existente.nombre = nombre
                existente.precio = precio
                if categoria_id is not None:
                    existente.categoria_id = categoria_id
                if pref is not None:
                    existente.precio_referencia = pref
                actualizados += 1
            else:
                nuevo = ArancelItem(clinic_id=clinic_id, arancel_id=arancel_id, categoria_id=categoria_id, codigo=codigo, nombre=nombre, precio=precio, precio_referencia=pref)
                db.add(nuevo)
                if codigo:
                    await db.flush()
                    item_by_codigo[codigo] = nuevo
                creados += 1
        except (ValueError, IndexError) as exc:
            errores.append(ImportErrorItem(fila=n, motivo=str(exc)))

    await db.commit()
    return ImportarArancelOut(creados=creados, actualizados=actualizados, total_filas=len(datos), errores=errores)


# ─────────────────────────── acciones (62.9 / 62.15) ───────────────────────────
@router.post("/{arancel_id}/incrementar", response_model=IncrementarOut)
async def incrementar_precios(
    arancel_id: uuid.UUID,
    payload: IncrementarIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.EDITAR)),
) -> IncrementarOut:
    """Ajuste porcentual a todas las prestaciones del arancel (62.9). pct=0.10 => +10%."""
    clinic_id = empresa_clinic_id(ctx)
    await _own_arancel(db, clinic_id, arancel_id)
    items = (await db.execute(select(ArancelItem).where(ArancelItem.arancel_id == arancel_id, ArancelItem.deleted_at.is_(None)))).scalars().all()
    factor = 1 + payload.pct
    for i in items:
        i.precio = round(float(i.precio) * factor, 2)
    await db.commit()
    return IncrementarOut(afectados=len(items))


@router.post("/{arancel_id}/copiar-base", response_model=CopiarBaseOut)
async def copiar_desde_base(
    arancel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CATALOGO_PRECIOS, Action.CREAR)),
) -> CopiarBaseOut:
    """Copia las categorías y prestaciones del arancel BASE de la clínica a este
    arancel, para luego ajustarlas (62.15). No duplica si ya se copió antes:
    omite ítems cuyo código ya existe en el destino."""
    clinic_id = empresa_clinic_id(ctx)
    destino = await _own_arancel(db, clinic_id, arancel_id)
    base = (await db.execute(select(Arancel).where(Arancel.clinic_id == clinic_id, Arancel.es_base.is_(True), Arancel.deleted_at.is_(None)))).scalars().first()
    if base is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay un arancel base definido")
    if base.id == destino.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El arancel base no puede copiarse sobre sí mismo")

    # mapear categorías base -> destino (por nombre; crea las que falten)
    dest_cats = (await db.execute(select(ArancelCategoria).where(ArancelCategoria.arancel_id == destino.id, ArancelCategoria.deleted_at.is_(None)))).scalars().all()
    cat_by_nombre = {c.nombre: c for c in dest_cats}
    base_cats = (await db.execute(select(ArancelCategoria).where(ArancelCategoria.arancel_id == base.id, ArancelCategoria.deleted_at.is_(None)))).scalars().all()
    base_cat_to_dest: dict[uuid.UUID, uuid.UUID] = {}
    for bc in base_cats:
        dc = cat_by_nombre.get(bc.nombre)
        if dc is None:
            dc = ArancelCategoria(clinic_id=clinic_id, arancel_id=destino.id, nombre=bc.nombre, orden=bc.orden)
            db.add(dc)
            await db.flush()
            cat_by_nombre[bc.nombre] = dc
        base_cat_to_dest[bc.id] = dc.id

    dest_codigos = {i.codigo for i in (await db.execute(select(ArancelItem).where(ArancelItem.arancel_id == destino.id, ArancelItem.deleted_at.is_(None)))).scalars().all() if i.codigo}
    base_items = (await db.execute(select(ArancelItem).where(ArancelItem.arancel_id == base.id, ArancelItem.deleted_at.is_(None)))).scalars().all()
    copiados = 0
    for bi in base_items:
        if bi.codigo and bi.codigo in dest_codigos:
            continue
        db.add(ArancelItem(
            clinic_id=clinic_id, arancel_id=destino.id,
            categoria_id=base_cat_to_dest.get(bi.categoria_id) if bi.categoria_id else None,
            codigo=bi.codigo, nombre=bi.nombre, precio=bi.precio, precio_referencia=bi.precio_referencia,
            permite_descuento=bi.permite_descuento, comisiona=bi.comisiona,
        ))
        copiados += 1
    await db.commit()
    return CopiarBaseOut(copiados=copiados)
