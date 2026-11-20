import requests
import sys

BASE_URL = "http://127.0.0.1:5050/api"

def run_tests():
    print("1. Testing Health Endpoint...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health_data = r.json()
    print("Health response:", health_data)
    assert health_data["all_healthy"] is True

    print("\n2. Testing User Login / Auth Service...")
    test_email = "micro_test@nxtbuild.io"
    test_pass = "TestPassword123!"
    
    # Try signup first
    signup_res = requests.post(
        f"{BASE_URL}/auth/signup",
        json={"email": test_email, "password": test_pass, "name": "Micro Test User"}
    )
    if signup_res.status_code == 201:
        res_json = signup_res.json()
        token = res_json["token"]
        print("Signup successful! Token received.")
    else:
        # User may already exist, try login
        login_res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": test_email, "password": test_pass}
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        res_json = login_res.json()
        token = res_json["token"]
        print("Login successful! Token received.")

    headers = {"Authorization": f"Bearer {token}"}

    print("\n3. Testing /auth/me...")
    me_res = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    assert me_res.status_code == 200, f"/auth/me failed: {me_res.text}"
    user_info = me_res.json()["user"]
    print(f"Authenticated as: {user_info['name']} ({user_info['email']})")

    print("\n4. Testing Project Creation (Project Service)...")
    create_res = requests.post(
        f"{BASE_URL}/projects",
        headers=headers,
        json={"title": "E2E Microservices Test Project", "description": "Testing 4-service architecture"}
    )
    assert create_res.status_code in (200, 201), f"Create project failed: {create_res.text}"
    project = create_res.json()["project"]
    project_id = project["_id"]
    print(f"Created project: {project['title']} (ID: {project_id})")

    print("\n5. Testing Projects List...")
    list_res = requests.get(f"{BASE_URL}/projects", headers=headers)
    assert list_res.status_code == 200, f"List projects failed: {list_res.text}"
    projects = list_res.json()["projects"]
    assert any(p["_id"] == project_id for p in projects), "Created project not found in list"
    print(f"Found {len(projects)} projects for user.")

    print("\n6. Testing AI Generation Service via Gateway...")
    print("Sending generation prompt: 'Create a simple modern counter component with +/- buttons'...")
    gen_res = requests.post(
        f"{BASE_URL}/projects/{project_id}/generate",
        headers=headers,
        json={"prompt": "Create a simple modern counter component with +/- buttons"},
        timeout=60.0
    )
    assert gen_res.status_code == 200, f"AI generation failed: {gen_res.text}"
    gen_project = gen_res.json()["project"]
    print("AI Generation Succeeded!")
    print(f"Title: {gen_project.get('title')}")
    print(f"Generated Code length: {len(gen_project.get('code', ''))} characters")
    assert len(gen_project.get("code", "")) > 50, "Generated code should not be empty"

    print("\n7. Verifying Project Updated in Project Service...")
    proj_res = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    assert proj_res.status_code == 200, f"Fetch project failed: {proj_res.text}"
    updated_project = proj_res.json()["project"]
    assert len(updated_project["messages"]) >= 2, "Project should have user + assistant messages"
    print(f"Verified! Project has {len(updated_project['messages'])} chat messages.")
    for msg in updated_project["messages"]:
        print(f"  [{msg.get('role')}]: {msg.get('text')[:80]}...")

    print("\n8. Cleaning up Test Project...")
    del_res = requests.delete(f"{BASE_URL}/projects/{project_id}", headers=headers)
    assert del_res.status_code == 200, f"Delete project failed: {del_res.text}"
    print("Test project deleted cleanly.")

    print("\n========================================================")
    print("🎉 ALL 8 END-TO-END MICROSERVICES INTEGRATION TESTS PASSED! 🎉")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
