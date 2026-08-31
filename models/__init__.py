"""Modelos ORM das tabelas fixas do projeto."""

from .base import Base
from .clientes import Clientes
from .interacoes import Interacoes
from .pedidos import Pedidos
from .pedido_itens import PedidoItens

__all__ = ["Base", "Clientes", "Interacoes", "Pedidos", "PedidoItens"]
