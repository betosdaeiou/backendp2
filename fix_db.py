from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:password@localhost:5432/emergencias')
with engine.connect() as conn:
    with conn.begin():
        conn.execute(text("DELETE FROM \"PlanSaaS\" WHERE \"Nombre\" = 'Personalizado'"))
        conn.execute(text("DELETE FROM \"PlanSaaS\" WHERE \"Nombre\" = 'Premium' AND \"Id\" NOT IN (SELECT MIN(\"Id\") FROM \"PlanSaaS\" WHERE \"Nombre\" = 'Premium')"))
print("Duplicados eliminados.")
