import os
import unittest

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi.testclient import TestClient

from database import init_db
from main import app


class QuizApiTest(unittest.TestCase):
    def setUp(self):
        init_db()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_health(self):
        result = self.client.get("/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"status": "ok"})

    def test_public_privacy_policy(self):
        result = self.client.get("/privacy")
        self.assertEqual(result.status_code, 200)
        self.assertIn("text/html", result.headers["content-type"])
        self.assertIn("隐私政策", result.text)
        self.assertIn("济南正拓网络科技有限公司", result.text)

        agreement = self.client.get("/agreement")
        self.assertEqual(agreement.status_code, 200)
        self.assertIn("用户协议", agreement.text)

    def test_topics_and_questions_do_not_leak_answers(self):
        topics = self.client.get("/api/topics").json()["items"]
        self.assertEqual(len(topics), 3)
        questions = self.client.get("/api/topics/python/questions").json()["items"]
        self.assertEqual(len(questions), 5)
        self.assertNotIn("answer", questions[0])

    def test_answer_check(self):
        result = self.client.post(
            "/api/answers", json={"question_id": 101, "answer": 3}
        )
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["correct"])

    def test_unknown_topic(self):
        result = self.client.get("/api/topics/missing/questions")
        self.assertEqual(result.status_code, 404)

    def test_save_result_and_stats(self):
        before = self.client.get("/api/stats").json()["completed"]
        result = self.client.post(
            "/api/results",
            json={
                "topic_id": "python",
                "correct_count": 4,
                "total_count": 5,
                "duration_seconds": 60,
            },
        )
        self.assertEqual(result.status_code, 201)
        self.assertGreater(result.json()["id"], 0)
        self.assertTrue(result.json()["created_at"].endswith("Z"))

        stats = self.client.get("/api/stats").json()
        self.assertEqual(stats["completed"], before + 1)

    def test_register_login_me_and_logout(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": "学习者001",
                "email": "learner001@example.com",
                "password": "correct-password",
            },
        )
        self.assertEqual(registration.status_code, 201)
        body = registration.json()
        self.assertTrue(body["token"])
        self.assertEqual(body["user"]["username"], "学习者001")
        headers = {"Authorization": f"Bearer {body['token']}"}

        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "learner001@example.com")

        login = self.client.post(
            "/api/auth/login",
            json={"account": "learner001@example.com", "password": "correct-password"},
        )
        self.assertEqual(login.status_code, 200)

        logout = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_duplicate_registration_and_wrong_password(self):
        payload = {
            "username": "unique_user_002",
            "email": "unique002@example.com",
            "password": "correct-password",
        }
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 201)
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 409)
        wrong = self.client.post(
            "/api/auth/login",
            json={"account": payload["email"], "password": "wrong-password"},
        )
        self.assertEqual(wrong.status_code, 401)

    def test_delete_account_requires_password_and_removes_login(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": "delete_user_004",
                "email": "delete004@example.com",
                "password": "correct-password",
            },
        ).json()
        headers = {"Authorization": f"Bearer {registration['token']}"}
        self.client.post(
            "/api/results",
            headers=headers,
            json={
                "topic_id": "daily",
                "correct_count": 4,
                "total_count": 5,
                "duration_seconds": 50,
            },
        )

        wrong = self.client.request(
            "DELETE",
            "/api/auth/account",
            headers=headers,
            json={"password": "wrong-password"},
        )
        self.assertEqual(wrong.status_code, 401)
        deleted = self.client.request(
            "DELETE",
            "/api/auth/account",
            headers=headers,
            json={"password": "correct-password"},
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        login = self.client.post(
            "/api/auth/login",
            json={"account": "delete004@example.com", "password": "correct-password"},
        )
        self.assertEqual(login.status_code, 401)

    def test_authenticated_stats_are_isolated(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "username": "stats_user_003",
                "email": "stats003@example.com",
                "password": "correct-password",
            },
        ).json()
        headers = {"Authorization": f"Bearer {registration['token']}"}
        self.client.post(
            "/api/results",
            headers=headers,
            json={
                "topic_id": "python",
                "correct_count": 5,
                "total_count": 5,
                "duration_seconds": 40,
            },
        )
        stats = self.client.get("/api/stats", headers=headers).json()
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["accuracy"], 100)


if __name__ == "__main__":
    unittest.main()
