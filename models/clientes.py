from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Clientes(Base):
    __tablename__ = "clientes"

    id_cliente: Mapped[str] = mapped_column(String, primary_key=True)
    data_cadastro: Mapped[date | None] = mapped_column(Date)
    data_ultima_atualizacao_cadastro: Mapped[date | None] = mapped_column(Date)
    uf: Mapped[str | None] = mapped_column(String)
    cidade: Mapped[str | None] = mapped_column(String)
    faixa_etaria: Mapped[str | None] = mapped_column(String)
    canal_aquisicao: Mapped[str | None] = mapped_column(String)
    tier_clube: Mapped[str | None] = mapped_column(String)
    optin_email: Mapped[bool | None] = mapped_column(Boolean)
