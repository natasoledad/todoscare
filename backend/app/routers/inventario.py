"""Inventario de insumos (punto 56) — visión Empresa/Cliente.

Catálogos base: proveedores (56.16), centros de costo (56.14), bodegas por
sucursal (56.2) e ítems de insumo con stock mínimo para el semáforo (56.7).
Los movimientos de stock (lotes, entradas/salidas, kardex) llegan en PR-Q.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, nullslast, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inventory import CostCenter, InventoryItem, StockLot, StockMovement, Supplier, Warehouse
from app.models.tenant import Branch
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.inventario import (
    AjusteIn,
    AlertasOut,
    BodegaIn,
    BodegaOut,
    BodegaUpdate,
    CentroCostoIn,
    CentroCostoOut,
    CentroCostoUpdate,
    EntradaIn,
    ItemIn,
    ItemOut,
    ItemUpdate,
    LoteOut,
    MovimientoStockOut,
    ProveedorIn,
    ProveedorOut,
    ProveedorUpdate,
    SalidaIn,
    StockOut,
    StockPorBodega,
)
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/inventario", tags=["inventario"])

DIAS_POR_VENCER = 30  # ventana de alerta de vencimiento (56.9)


async def _stock_de_item(db: AsyncSession, item_id: uuid.UUID) -> Decimal:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(StockLot.cantidad), 0)).where(
                StockLot.item_id == item_id, StockLot.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    return Decimal(total)


def _semaforo(stock: Decimal, minimo: Decimal) -> str:
    if stock <= 0:
        return "sin_stock"
    if stock <= minimo:
        return "bajo"
    return "ok"


def _estado_lote(venc: date | None) -> str:
    if venc is None:
        return "sin_vencimiento"
    hoy = date.today()
    if venc < hoy:
        return "vencido"
    if venc <= hoy + timedelta(days=DIAS_POR_VENCER):
        return "por_vencer"
    return "vigente"


def _clinic_id(ctx: TenantContext) -> uuid.UUID:
    ids = ctx.clinic_ids()
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La cuenta no tiene una clínica asignada")
    return next(iter(ids))


# ─────────────────────────── proveedores (56.16) ───────────────────────────
@router.get("/proveedores", response_model=list[ProveedorOut])
async def list_proveedores(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[ProveedorOut]:
    cid = _clinic_id(ctx)
    rows = (await db.execute(select(Supplier).where(Supplier.clinic_id == cid, Supplier.deleted_at.is_(None)).order_by(Supplier.nombre))).scalars().all()
    return [ProveedorOut(id=s.id, nombre=s.nombre, rut=s.rut, contacto=s.contacto, activo=s.activo) for s in rows]


@router.post("/proveedores", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
async def crear_proveedor(
    payload: ProveedorIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> ProveedorOut:
    cid = _clinic_id(ctx)
    s = Supplier(clinic_id=cid, nombre=payload.nombre, rut=payload.rut, contacto=payload.contacto)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ProveedorOut(id=s.id, nombre=s.nombre, rut=s.rut, contacto=s.contacto, activo=s.activo)


async def _own_supplier(db: AsyncSession, cid: uuid.UUID, sid: uuid.UUID) -> Supplier:
    s = await db.get(Supplier, sid)
    if s is None or s.clinic_id != cid or s.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    return s


@router.patch("/proveedores/{sid}", response_model=ProveedorOut)
async def editar_proveedor(
    sid: uuid.UUID,
    payload: ProveedorUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.EDITAR)),
) -> ProveedorOut:
    cid = _clinic_id(ctx)
    s = await _own_supplier(db, cid, sid)
    for f in ("nombre", "rut", "contacto", "activo"):
        v = getattr(payload, f)
        if v is not None:
            setattr(s, f, v)
    await db.commit()
    await db.refresh(s)
    return ProveedorOut(id=s.id, nombre=s.nombre, rut=s.rut, contacto=s.contacto, activo=s.activo)


@router.delete("/proveedores/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_proveedor(
    sid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    s = await _own_supplier(db, cid, sid)
    await db.delete(s)  # baja lógica vía listener global de auditoría
    await db.commit()


# ─────────────────────────── centros de costo (56.14) ───────────────────────────
@router.get("/centros-costo", response_model=list[CentroCostoOut])
async def list_centros(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[CentroCostoOut]:
    cid = _clinic_id(ctx)
    rows = (await db.execute(select(CostCenter).where(CostCenter.clinic_id == cid, CostCenter.deleted_at.is_(None)).order_by(CostCenter.nombre))).scalars().all()
    return [CentroCostoOut(id=c.id, nombre=c.nombre, activo=c.activo) for c in rows]


@router.post("/centros-costo", response_model=CentroCostoOut, status_code=status.HTTP_201_CREATED)
async def crear_centro(
    payload: CentroCostoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> CentroCostoOut:
    cid = _clinic_id(ctx)
    c = CostCenter(clinic_id=cid, nombre=payload.nombre)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CentroCostoOut(id=c.id, nombre=c.nombre, activo=c.activo)


async def _own_centro(db: AsyncSession, cid: uuid.UUID, ccid: uuid.UUID) -> CostCenter:
    c = await db.get(CostCenter, ccid)
    if c is None or c.clinic_id != cid or c.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centro de costo no encontrado")
    return c


@router.patch("/centros-costo/{ccid}", response_model=CentroCostoOut)
async def editar_centro(
    ccid: uuid.UUID,
    payload: CentroCostoUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.EDITAR)),
) -> CentroCostoOut:
    cid = _clinic_id(ctx)
    c = await _own_centro(db, cid, ccid)
    if payload.nombre is not None:
        c.nombre = payload.nombre
    if payload.activo is not None:
        c.activo = payload.activo
    await db.commit()
    await db.refresh(c)
    return CentroCostoOut(id=c.id, nombre=c.nombre, activo=c.activo)


@router.delete("/centros-costo/{ccid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_centro(
    ccid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    c = await _own_centro(db, cid, ccid)
    await db.delete(c)
    await db.commit()


# ─────────────────────────── bodegas (56.2) ───────────────────────────
async def _bodega_out(db: AsyncSession, w: Warehouse) -> BodegaOut:
    nombre = None
    if w.branch_id:
        b = await db.get(Branch, w.branch_id)
        nombre = b.nombre if b else None
    return BodegaOut(id=w.id, nombre=w.nombre, branch_id=w.branch_id, branch_nombre=nombre, activo=w.activo)


async def _validar_branch(db: AsyncSession, cid: uuid.UUID, branch_id: uuid.UUID | None) -> None:
    if branch_id is None:
        return
    b = await db.get(Branch, branch_id)
    if b is None or b.clinic_id != cid or b.deleted_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sucursal inválida")


@router.get("/bodegas", response_model=list[BodegaOut])
async def list_bodegas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[BodegaOut]:
    cid = _clinic_id(ctx)
    rows = (await db.execute(select(Warehouse).where(Warehouse.clinic_id == cid, Warehouse.deleted_at.is_(None)).order_by(Warehouse.nombre))).scalars().all()
    return [await _bodega_out(db, w) for w in rows]


@router.post("/bodegas", response_model=BodegaOut, status_code=status.HTTP_201_CREATED)
async def crear_bodega(
    payload: BodegaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> BodegaOut:
    cid = _clinic_id(ctx)
    await _validar_branch(db, cid, payload.branch_id)
    w = Warehouse(clinic_id=cid, nombre=payload.nombre, branch_id=payload.branch_id)
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return await _bodega_out(db, w)


async def _own_bodega(db: AsyncSession, cid: uuid.UUID, wid: uuid.UUID) -> Warehouse:
    w = await db.get(Warehouse, wid)
    if w is None or w.clinic_id != cid or w.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bodega no encontrada")
    return w


@router.patch("/bodegas/{wid}", response_model=BodegaOut)
async def editar_bodega(
    wid: uuid.UUID,
    payload: BodegaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.EDITAR)),
) -> BodegaOut:
    cid = _clinic_id(ctx)
    w = await _own_bodega(db, cid, wid)
    if payload.branch_id is not None:
        await _validar_branch(db, cid, payload.branch_id)
        w.branch_id = payload.branch_id
    if payload.nombre is not None:
        w.nombre = payload.nombre
    if payload.activo is not None:
        w.activo = payload.activo
    await db.commit()
    await db.refresh(w)
    return await _bodega_out(db, w)


@router.delete("/bodegas/{wid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_bodega(
    wid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    w = await _own_bodega(db, cid, wid)
    await db.delete(w)
    await db.commit()


# ─────────────────────────── ítems de insumo (56.7) ───────────────────────────
async def _item_out(db: AsyncSession, it: InventoryItem) -> ItemOut:
    sup_nombre = None
    if it.supplier_id:
        s = await db.get(Supplier, it.supplier_id)
        sup_nombre = s.nombre if s else None
    cc_nombre = None
    if it.cost_center_id:
        c = await db.get(CostCenter, it.cost_center_id)
        cc_nombre = c.nombre if c else None
    stock = await _stock_de_item(db, it.id)
    return ItemOut(
        id=it.id, nombre=it.nombre, sku=it.sku, unidad=it.unidad, stock_minimo=float(it.stock_minimo),
        stock_actual=float(stock), estado=_semaforo(stock, Decimal(it.stock_minimo)),
        supplier_id=it.supplier_id, supplier_nombre=sup_nombre,
        cost_center_id=it.cost_center_id, cost_center_nombre=cc_nombre, activo=it.activo,
    )


async def _validar_refs(db: AsyncSession, cid: uuid.UUID, supplier_id: uuid.UUID | None, cost_center_id: uuid.UUID | None) -> None:
    if supplier_id is not None:
        await _own_supplier(db, cid, supplier_id)
    if cost_center_id is not None:
        await _own_centro(db, cid, cost_center_id)


@router.get("/items", response_model=list[ItemOut])
async def list_items(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[ItemOut]:
    cid = _clinic_id(ctx)
    rows = (await db.execute(select(InventoryItem).where(InventoryItem.clinic_id == cid, InventoryItem.deleted_at.is_(None)).order_by(InventoryItem.nombre))).scalars().all()
    return [await _item_out(db, it) for it in rows]


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def crear_item(
    payload: ItemIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> ItemOut:
    cid = _clinic_id(ctx)
    await _validar_refs(db, cid, payload.supplier_id, payload.cost_center_id)
    it = InventoryItem(
        clinic_id=cid, nombre=payload.nombre, sku=payload.sku or None, unidad=payload.unidad,
        stock_minimo=payload.stock_minimo, supplier_id=payload.supplier_id, cost_center_id=payload.cost_center_id,
    )
    db.add(it)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un ítem con ese SKU") from None
    await db.refresh(it)
    return await _item_out(db, it)


async def _own_item(db: AsyncSession, cid: uuid.UUID, iid: uuid.UUID) -> InventoryItem:
    it = await db.get(InventoryItem, iid)
    if it is None or it.clinic_id != cid or it.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ítem no encontrado")
    return it


@router.patch("/items/{iid}", response_model=ItemOut)
async def editar_item(
    iid: uuid.UUID,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.EDITAR)),
) -> ItemOut:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    await _validar_refs(db, cid, payload.supplier_id, payload.cost_center_id)
    for f in ("nombre", "sku", "unidad", "stock_minimo", "supplier_id", "cost_center_id", "activo"):
        v = getattr(payload, f)
        if v is not None:
            setattr(it, f, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un ítem con ese SKU") from None
    await db.refresh(it)
    return await _item_out(db, it)


@router.delete("/items/{iid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_item(
    iid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.ELIMINAR)),
) -> None:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    await db.delete(it)
    await db.commit()


# ─────────────────────────── stock: lotes y movimientos (56.9 · 56.11) ───────────────────────────
async def _stock_en_bodega(db: AsyncSession, item_id: uuid.UUID, warehouse_id: uuid.UUID) -> Decimal:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(StockLot.cantidad), 0)).where(
                StockLot.item_id == item_id, StockLot.warehouse_id == warehouse_id, StockLot.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    return Decimal(total)


async def _mov(db, *, cid, item_id, warehouse_id, lot_id, tipo, cantidad, motivo, cost_center_id, supplier_id):
    """Asienta el kardex: `cantidad` con signo y el saldo total del ítem tras el
    movimiento (se llama después de haber tocado y flusheado los lotes)."""
    saldo = await _stock_de_item(db, item_id)
    db.add(StockMovement(
        clinic_id=cid, item_id=item_id, warehouse_id=warehouse_id, lot_id=lot_id, tipo=tipo,
        cantidad=cantidad, saldo=saldo, motivo=motivo, cost_center_id=cost_center_id, supplier_id=supplier_id,
    ))


@router.post("/items/{iid}/entrada", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def entrada(
    iid: uuid.UUID,
    payload: EntradaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> ItemOut:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    await _own_bodega(db, cid, payload.warehouse_id)
    if payload.supplier_id is not None:
        await _own_supplier(db, cid, payload.supplier_id)
    if payload.cost_center_id is not None:
        await _own_centro(db, cid, payload.cost_center_id)

    lote = payload.lote or None
    conds = [StockLot.item_id == it.id, StockLot.warehouse_id == payload.warehouse_id, StockLot.deleted_at.is_(None)]
    conds.append(StockLot.lote.is_(None) if lote is None else StockLot.lote == lote)
    conds.append(StockLot.vencimiento.is_(None) if payload.vencimiento is None else StockLot.vencimiento == payload.vencimiento)
    lot = (await db.execute(select(StockLot).where(*conds))).scalars().first()
    cant = Decimal(str(payload.cantidad))
    if lot is None:
        lot = StockLot(clinic_id=cid, item_id=it.id, warehouse_id=payload.warehouse_id, lote=lote, vencimiento=payload.vencimiento, cantidad=cant)
        db.add(lot)
    else:
        lot.cantidad = Decimal(lot.cantidad) + cant
    await db.flush()
    await _mov(db, cid=cid, item_id=it.id, warehouse_id=payload.warehouse_id, lot_id=lot.id, tipo="entrada",
               cantidad=cant, motivo=payload.motivo, cost_center_id=payload.cost_center_id, supplier_id=payload.supplier_id)
    await db.commit()
    await db.refresh(it)
    return await _item_out(db, it)


@router.post("/items/{iid}/salida", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def salida(
    iid: uuid.UUID,
    payload: SalidaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.CREAR)),
) -> ItemOut:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    await _own_bodega(db, cid, payload.warehouse_id)
    if payload.cost_center_id is not None:
        await _own_centro(db, cid, payload.cost_center_id)

    cant = Decimal(str(payload.cantidad))
    disponible = await _stock_en_bodega(db, it.id, payload.warehouse_id)
    if disponible < cant:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Stock insuficiente en la bodega (disponible {disponible}, se pide {cant})")

    # FEFO: consume primero los lotes que vencen antes (nulos al final).
    lots = (
        await db.execute(
            select(StockLot).where(
                StockLot.item_id == it.id, StockLot.warehouse_id == payload.warehouse_id,
                StockLot.deleted_at.is_(None), StockLot.cantidad > 0,
            ).order_by(nullslast(StockLot.vencimiento.asc()), StockLot.created_at.asc())
        )
    ).scalars().all()
    restante = cant
    for lot in lots:
        if restante <= 0:
            break
        toma = min(Decimal(lot.cantidad), restante)
        lot.cantidad = Decimal(lot.cantidad) - toma
        restante -= toma
    await db.flush()
    await _mov(db, cid=cid, item_id=it.id, warehouse_id=payload.warehouse_id, lot_id=None, tipo="salida",
               cantidad=-cant, motivo=payload.motivo, cost_center_id=payload.cost_center_id, supplier_id=None)
    await db.commit()
    await db.refresh(it)
    return await _item_out(db, it)


@router.post("/items/{iid}/ajuste", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def ajuste(
    iid: uuid.UUID,
    payload: AjusteIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.EDITAR)),
) -> ItemOut:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    lot = await db.get(StockLot, payload.lot_id)
    if lot is None or lot.clinic_id != cid or lot.item_id != it.id or lot.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado")
    nueva = Decimal(str(payload.cantidad_nueva))
    delta = nueva - Decimal(lot.cantidad)
    lot.cantidad = nueva
    await db.flush()
    await _mov(db, cid=cid, item_id=it.id, warehouse_id=lot.warehouse_id, lot_id=lot.id, tipo="ajuste",
               cantidad=delta, motivo=payload.motivo, cost_center_id=None, supplier_id=None)
    await db.commit()
    await db.refresh(it)
    return await _item_out(db, it)


async def _lote_out(db: AsyncSession, lot: StockLot, *, item_nombre: str | None = None) -> LoteOut:
    w = await db.get(Warehouse, lot.warehouse_id)
    if item_nombre is None:
        it = await db.get(InventoryItem, lot.item_id)
        item_nombre = it.nombre if it else None
    return LoteOut(
        id=lot.id, warehouse_id=lot.warehouse_id, warehouse_nombre=w.nombre if w else None,
        item_id=lot.item_id, item_nombre=item_nombre, lote=lot.lote, vencimiento=lot.vencimiento,
        cantidad=float(lot.cantidad), estado=_estado_lote(lot.vencimiento),
    )


@router.get("/items/{iid}/lotes", response_model=list[LoteOut])
async def lotes_de_item(
    iid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[LoteOut]:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    lots = (
        await db.execute(
            select(StockLot).where(StockLot.item_id == it.id, StockLot.deleted_at.is_(None))
            .order_by(nullslast(StockLot.vencimiento.asc()), StockLot.created_at.asc())
        )
    ).scalars().all()
    return [await _lote_out(db, lot, item_nombre=it.nombre) for lot in lots]


@router.get("/items/{iid}/stock", response_model=StockOut)
async def stock_de_item(
    iid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> StockOut:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    rows = (
        await db.execute(
            select(StockLot.warehouse_id, func.coalesce(func.sum(StockLot.cantidad), 0))
            .where(StockLot.item_id == it.id, StockLot.deleted_at.is_(None))
            .group_by(StockLot.warehouse_id)
        )
    ).all()
    por_bodega = []
    total = Decimal(0)
    for wid, cant in rows:
        w = await db.get(Warehouse, wid)
        por_bodega.append(StockPorBodega(warehouse_id=wid, warehouse_nombre=w.nombre if w else None, cantidad=float(cant)))
        total += Decimal(cant)
    return StockOut(item_id=it.id, stock_actual=float(total), stock_minimo=float(it.stock_minimo),
                    estado=_semaforo(total, Decimal(it.stock_minimo)), por_bodega=por_bodega)


@router.get("/items/{iid}/movimientos", response_model=list[MovimientoStockOut])
async def kardex(
    iid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> list[MovimientoStockOut]:
    cid = _clinic_id(ctx)
    it = await _own_item(db, cid, iid)
    movs = (
        await db.execute(
            select(StockMovement).where(StockMovement.item_id == it.id, StockMovement.deleted_at.is_(None))
            .order_by(StockMovement.created_at.desc())
        )
    ).scalars().all()
    out: list[MovimientoStockOut] = []
    for m in movs:
        w = await db.get(Warehouse, m.warehouse_id)
        cc_nombre = None
        if m.cost_center_id:
            c = await db.get(CostCenter, m.cost_center_id)
            cc_nombre = c.nombre if c else None
        sup_nombre = None
        if m.supplier_id:
            s = await db.get(Supplier, m.supplier_id)
            sup_nombre = s.nombre if s else None
        out.append(MovimientoStockOut(
            id=m.id, tipo=m.tipo, cantidad=float(m.cantidad), saldo=float(m.saldo),
            warehouse_nombre=w.nombre if w else None, motivo=m.motivo,
            cost_center_nombre=cc_nombre, supplier_nombre=sup_nombre, fecha=m.created_at,
        ))
    return out


@router.get("/alertas", response_model=AlertasOut)
async def alertas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INVENTARIO, Action.VER)),
) -> AlertasOut:
    cid = _clinic_id(ctx)
    items = (await db.execute(select(InventoryItem).where(InventoryItem.clinic_id == cid, InventoryItem.deleted_at.is_(None), InventoryItem.activo.is_(True)).order_by(InventoryItem.nombre))).scalars().all()
    bajo = []
    for it in items:
        out = await _item_out(db, it)
        if out.estado != "ok":
            bajo.append(out)

    hoy = date.today()
    limite = hoy + timedelta(days=DIAS_POR_VENCER)
    lots = (
        await db.execute(
            select(StockLot).where(
                StockLot.clinic_id == cid, StockLot.deleted_at.is_(None),
                StockLot.cantidad > 0, StockLot.vencimiento.is_not(None), StockLot.vencimiento <= limite,
            ).order_by(StockLot.vencimiento.asc())
        )
    ).scalars().all()
    por_vencer, vencidos = [], []
    for lot in lots:
        lo = await _lote_out(db, lot)
        (vencidos if lo.estado == "vencido" else por_vencer).append(lo)
    return AlertasOut(bajo_minimo=bajo, lotes_por_vencer=por_vencer, lotes_vencidos=vencidos)
