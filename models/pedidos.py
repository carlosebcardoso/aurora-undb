from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Pedidos(Base):
    __tablename__ = "pedidos"

    id_pedido: Mapped[str] = mapped_column(String, primary_key=True)
    id_cliente: Mapped[str] = mapped_column(String)
    data_pedido: Mapped[date | None] = mapped_column(Date)
    canal: Mapped[str | None] = mapped_column(String)
    categoria: Mapped[str | None] = mapped_column(String)
    sku: Mapped[str | None] = mapped_column(String)
    quantidade: Mapped[int | None] = mapped_column(Integer)
    valor_unitario: Mapped[float | None] = mapped_column(Float)
    valor_desconto: Mapped[float | None] = mapped_column(Float)
    cupom_utilizado: Mapped[bool | None] = mapped_column(Boolean)
    prazo_entrega_dias: Mapped[int | None] = mapped_column(Integer)
    atraso_entrega_dias: Mapped[float | None] = mapped_column(Float)
    margem_bruta_pct: Mapped[float | None] = mapped_column(Float)
