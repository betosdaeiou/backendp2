import psycopg2
conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT id, monto_total, metodo, estado, incidente_id FROM public."Pago"')
print("Pagos:", cur.fetchall())
