INSERT INTO cuenta (numero_cuenta, moneda, saldo) VALUES
    ('CUEN_001', 'USD', 1000.00),
    ('CUEN_002', 'USD', 500.00),
    ('CUEN_003', 'USD', 5200.00),
    ('CUEN_004', 'USD', 200.00),
    ('CUEN_005', 'USD', 300.00)
ON CONFLICT (numero_cuenta) DO NOTHING;