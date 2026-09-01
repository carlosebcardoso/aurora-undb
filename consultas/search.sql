SELECT
    c.id_cliente,
    c.uf,
    c.canal_aquisicao,
    c.tier_clube,
    p.id_pedido,
    p.data_pedido,
    p.prazo_entrega_dias,
    p.atraso_entrega_dias
FROM clientes c
JOIN pedidos p
    ON c.id_cliente = p.id_cliente
WHERE p.atraso_entrega_dias IS NOT NULL
ORDER BY p.atraso_entrega_dias DESC;