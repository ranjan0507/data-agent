from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_register_login_and_me():
	register = client.post(
		"auth/register",
		json={
			"email":"auth-test@example.com",
			"password":"password123"
		}
	)
	assert register.status_code in (200,201,409)

	login = client.post(
		"/auth/login",
		json={
			"email":"auth-test@example.com",
			"password":"password123"
		}
	)

	assert login.status_code==200
	token=login.json()["access_token"]

	me=client.get(
		"/auth/me",
		headers={"Authorization": f"Bearer {token}"}
	)

	assert me.status_code==200
	assert me.json()["email"]=="auth-test@example.com"

def test_me_requires_authentication():
	response = client.get("auth/me")
	assert response.status_code==401
