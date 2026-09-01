from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Interacoes(Base):
    __tablename__ = "interacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[str] = mapped_column(ForeignKey("clientes.id_cliente"))
    ano_mes: Mapped[str] = mapped_column(String)
    campanhas_enviadas: Mapped[int | None] = mapped_column(Integer)
    campanhas_reativacao_recebidas: Mapped[int | None] = mapped_column(Integer)
    campanhas_abertas: Mapped[int | None] = mapped_column(Integer)
    cliques: Mapped[int | None] = mapped_column(Integer)
    sessoes_site_app: Mapped[int | None] = mapped_column(Integer)
    carrinhos_abandonados: Mapped[int | None] = mapped_column(Integer)
    tickets_sac: Mapped[int | None] = mapped_column(Integer)
    motivo_sac_principal: Mapped[str | None] = mapped_column(String)
    ticket_resolvido: Mapped[bool | None] = mapped_column(Boolean)
