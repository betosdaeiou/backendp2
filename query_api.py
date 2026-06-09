import requests

# Login
login_url = "http://127.0.0.1:8000/auth/login"
data = {
    "username": "admin.autofix@demo.com",
    "password": "password"
}
response = requests.post(login_url, data=data)
print("Login:", response.status_code)
if response.status_code == 200:
    token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get mecanicos
    mec_res = requests.get("http://127.0.0.1:8000/mecanicos/", headers=headers)
    print("Mecanicos status:", mec_res.status_code)
    try:
        print("Mecanicos data:", mec_res.json())
    except:
        print("Mecanicos text:", mec_res.text)
