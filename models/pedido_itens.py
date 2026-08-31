from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PedidoItens(Base):
    __tablename__ = "pedido_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_pedido: Mapped[str] = mapped_column(ForeignKey("pedidos.id_pedido"))
    categoria: Mapped[str | None] = mapped_column(String)
    sku: Mapped[str | None] = mapped_column(String)
    quantidade: Mapped[int | None] = mapped_column(Integer)
    valor_unitario: Mapped[float | None] = mapped_column(Float)
    valor_desconto: Mapped[float | None] = mapped_column(Float)
    margem_bruta_pct: Mapped[float | None] = mapped_column(Float)
