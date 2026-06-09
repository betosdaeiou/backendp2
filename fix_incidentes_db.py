import psycopg2

conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()

# Find all incidents that have a completed payment
cur.execute('''
    UPDATE public."Incidente"
    SET estado = 'pagado'
    WHERE id IN (
        SELECT incidente_id 
        FROM public."Pago" 
        WHERE estado = 'Completado'
    ) AND estado != 'pagado'
''')

conn.commit()
print(f"Updated {cur.rowcount} incidents to 'pagado'")
