import requests

r = requests.post('http://127.0.0.1:8000/auth/login', data={'username': 'conductor.ana@demo.local', 'password': 'User123!'})
token = r.json()['access_token']

# Try the endpoint, print full error
r2 = requests.get(
    'http://127.0.0.1:8000/incidentes/talleres-disponibles',
    headers={'Authorization': 'Bearer ' + token}
)
print('Status:', r2.status_code)
print('Headers:', dict(r2.headers))
print('Body:', r2.text[:2000])
