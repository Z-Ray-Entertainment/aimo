import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "core"
FLASK_DIR = PROJECT_ROOT / "flask"

for p in (str(CORE_DIR), str(FLASK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


class SecurityMACTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        tmp_path = Path(cls._tmp_dir.name)
        cls._db_path = tmp_path / "test_aimo.db"
        cls._upload_dir = tmp_path / "uploads"
        cls._upload_dir.mkdir(parents=True, exist_ok=True)

        os.environ["AIMO_DEBUG"] = "true"
        os.environ["AIMO_SECRET_KEY"] = "test-secret-key-for-security-suite"
        os.environ["CLIENT_KEY"] = "test-client-key-for-security-suite"
        os.environ["AIMO_DATABASE_PATH"] = str(cls._db_path)
        os.environ["AIMO_UPLOAD_DIR"] = str(cls._upload_dir)

        from shared.config import Config

        Config.DATABASE_PATH = cls._db_path
        Config.DATABASE_URI = f"sqlite:///{cls._db_path}"
        Config.UPLOAD_DIR = cls._upload_dir
        Config.UPLOAD_PATH = cls._upload_dir
        Config.SECRET_KEY = "test-secret-key-for-security-suite"
        Config.CLIENT_KEY = "test-client-key-for-security-suite"

        from infrastructure.database import init_db

        init_db()

        from domain.auth.services import AuthService
        from domain.characters.services import CharacterService
        from domain.chat.services import ChatService
        from domain.lorebooks.services import LorebookService
        from domain.memories.services import MemoryService
        from domain.permissions.models import Preset, UserPermissions
        from domain.permissions.services import PermissionService
        from domain.personas.models import Gender
        from domain.personas.services import PersonaService
        from domain.worldinfo.services import WorldInfoService
        from infrastructure.repositories.character_repository import CharacterRepository
        from infrastructure.repositories.chat_repository import ChatRepository
        from infrastructure.repositories.lorebook_repository import LorebookRepository
        from infrastructure.repositories.memory_repository import MemoryRepository
        from infrastructure.repositories.persona_repository import PersonaRepository
        from infrastructure.repositories.user_repository import UserRepository
        from infrastructure.repositories.worldinfo_repository import WorldInfoRepository

        user_repo = UserRepository()
        auth_svc = AuthService()
        perm_svc = PermissionService()
        persona_svc = PersonaService()
        persona_repo = PersonaRepository()
        char_svc = CharacterService()
        char_repo = CharacterRepository()
        chat_svc = ChatService()
        chat_repo = ChatRepository()
        mem_svc = MemoryService()
        mem_repo = MemoryRepository()
        lb_svc = LorebookService()
        lb_repo = LorebookRepository()
        wi_svc = WorldInfoService()
        wi_repo = WorldInfoRepository()

        admin_u = auth_svc.create_user("admin", "admin@example.com", "AdminPass123!", is_initial_admin=True)
        cls.admin_user = user_repo.create(admin_u)
        admin_perms = UserPermissions(user_id=cls.admin_user.id)
        perm_svc.assign_preset(cls.admin_user, admin_perms, Preset.ADMIN)
        user_repo.save_permissions(admin_perms)

        user_a_u = auth_svc.create_user("alice", "alice@example.com", "AlicePass123!")
        cls.user_a = user_repo.create(user_a_u)
        perms_a = UserPermissions(user_id=cls.user_a.id)
        perm_svc.assign_preset(cls.user_a, perms_a, Preset.CREATOR)
        user_repo.save_permissions(perms_a)

        user_b_u = auth_svc.create_user("bob", "bob@example.com", "BobPass123!")
        cls.user_b = user_repo.create(user_b_u)
        perms_b = UserPermissions(user_id=cls.user_b.id)
        perm_svc.assign_preset(cls.user_b, perms_b, Preset.CREATOR)
        user_repo.save_permissions(perms_b)

        p_a = persona_repo.create(
            persona_svc.create_persona(
                user_id=cls.user_a.id,
                name="AlicePersona",
                gender=Gender.FEMALE,
                portrait_path="portraits/default_persona.png",
                description="Test persona.",
            )
        )
        char_a = char_repo.save(
            char_svc.create_character(
                user_id=cls.user_a.id,
                name="PrivateChar",
                gender="female",
                primary_portrait_path="portraits/default.png",
                description="Secret character.",
                first_message="Hello.",
                visibility="private",
            )
        )
        sess_a, first_msg = chat_svc.create_session(
            user_id=cls.user_a.id,
            character=char_a,
            persona_id=p_a.id,
            worldinfo_id=None,
            persona_name=p_a.name,
        )
        cls.session_a = chat_repo.create_session(sess_a)
        first_msg.session_id = cls.session_a.id
        chat_repo.add_message(first_msg)
        cls.mem_a = mem_repo.add_memory(
            mem_svc.create_memory(
                chat_session_id=cls.session_a.id,
                message_idx=1,
                title="SecretMem",
                tags=["secret"],
                summary="Secret summary text for Alice only.",
            )
        )

        cls.lb_a = lb_repo.create(lb_svc.create_lorebook(cls.user_a.id, "AliceLB", "Desc", "private"))
        cls.entry_a = lb_repo.add_entry(
            lb_svc.add_entry(cls.lb_a.id, "AliceEntry", ["tag1"], "Secret lore content")
        )
        cls.lb_b = lb_repo.create(lb_svc.create_lorebook(cls.user_b.id, "BobLB", "Desc", "private"))

        cls.wi_a = wi_repo.create(wi_svc.create_worldinfo(cls.user_a.id, "AliceWorld", visibility="private"))
        cls.loc_a = wi_repo.add_location(
            wi_svc.add_location(cls.wi_a.id, "AliceLoc", ["loc"], "Secret loc")
        )
        cls.ev_a = wi_repo.add_event(
            wi_svc.add_event(cls.wi_a.id, "AliceEvent", "Secret event", 50, False)
        )
        cls.wi_b = wi_repo.create(wi_svc.create_worldinfo(cls.user_b.id, "BobWorld", visibility="private"))

        import importlib.util

        core_spec = importlib.util.spec_from_file_location("aimo_core_app", str(CORE_DIR / "app.py"))
        core_mod = importlib.util.module_from_spec(core_spec)
        assert core_spec and core_spec.loader
        core_spec.loader.exec_module(core_mod)

        web_spec = importlib.util.spec_from_file_location("aimo_flask_app", str(FLASK_DIR / "app.py"))
        web_mod = importlib.util.module_from_spec(web_spec)
        assert web_spec and web_spec.loader
        web_spec.loader.exec_module(web_mod)

        cls.core_app = core_mod.create_core_app(Config)
        cls.core_client = cls.core_app.test_client()

        import threading
        from werkzeug.serving import make_server

        cls._core_server = make_server("127.0.0.1", 0, cls.core_app, threaded=True)
        cls._core_port = cls._core_server.server_port
        os.environ["AIMO_CORE_URL"] = f"http://127.0.0.1:{cls._core_port}"
        cls._core_thread = threading.Thread(target=cls._core_server.serve_forever, daemon=True)
        cls._core_thread.start()

        cls.web_app = web_mod.create_webui_app(Config)
        cls.web_client = cls.web_app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_core_server"):
            cls._core_server.shutdown()
            cls._core_server.server_close()
        cls._tmp_dir.cleanup()

    def _signed_core_headers(self, user_id: int) -> dict[str, str]:
        from shared.security import sign_user_id

        ts, sig = sign_user_id(user_id, "test-secret-key-for-security-suite")
        return {
            "X-Client-Key": "test-client-key-for-security-suite",
            "X-User-Id": str(user_id),
            "X-User-Timestamp": ts,
            "X-User-Signature": sig,
        }

    def test_01_unauthenticated_proxy_and_user_id_query_blocked(self) -> None:
        resp_web = self.web_client.get("/api/characters?user_id=1")
        self.assertEqual(resp_web.status_code, 401)

        resp_core_query = self.core_client.get(
            "/api/characters?user_id=1",
            headers={"X-Client-Key": "test-client-key-for-security-suite"},
        )
        self.assertEqual(resp_core_query.status_code, 401)

        resp_core_unsigned = self.core_client.get(
            "/api/characters",
            headers={
                "X-Client-Key": "test-client-key-for-security-suite",
                "X-User-Id": "1",
            },
        )
        self.assertEqual(resp_core_unsigned.status_code, 401)

        resp_core_signed = self.core_client.get(
            "/api/characters",
            headers=self._signed_core_headers(self.admin_user.id),
        )
        self.assertEqual(resp_core_signed.status_code, 200)

    def test_02_admin_notify_requires_auth(self) -> None:
        resp = self.core_client.post(
            "/api/admin/translations/notify",
            headers={"X-Client-Key": "test-client-key-for-security-suite"},
            json={},
        )
        self.assertEqual(resp.status_code, 401)

    def test_03_strict_owner_only_chat_session_mac(self) -> None:
        resp_core = self.core_client.get(
            f"/api/chat/{self.session_a.id}/memories",
            headers=self._signed_core_headers(self.admin_user.id),
        )
        self.assertEqual(resp_core.status_code, 404)

        with self.web_client.session_transaction() as sess:
            sess["user_id"] = self.admin_user.id
        self.web_client.post(
            f"/chat/session/{self.session_a.id}/memories/{self.mem_a.id}/delete",
            follow_redirects=False,
        )
        from infrastructure.repositories.memory_repository import MemoryRepository

        self.assertIsNotNone(MemoryRepository().get_by_id(self.mem_a.id))

    def test_04_cross_tenant_delete_idor_blocked(self) -> None:
        from infrastructure.repositories.lorebook_repository import LorebookRepository
        from infrastructure.repositories.worldinfo_repository import WorldInfoRepository

        with self.web_client.session_transaction() as sess:
            sess["user_id"] = self.user_b.id

        self.web_client.post(f"/lorebooks/{self.lb_b.id}/entries/{self.entry_a.id}/delete")
        self.assertIsNotNone(LorebookRepository().get_entry(self.entry_a.id))

        self.web_client.post(f"/worldinfo/{self.wi_b.id}/locations/{self.loc_a.id}/delete")
        self.assertIsNotNone(WorldInfoRepository().get_location(self.loc_a.id))

        self.web_client.post(f"/worldinfo/{self.wi_b.id}/events/{self.ev_a.id}/delete")
        self.assertIsNotNone(WorldInfoRepository().get_event(self.ev_a.id))

    def test_05_uploads_require_auth(self) -> None:
        secret_file = self._upload_dir / "portraits" / "secret.png"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_bytes(b"fake-png")

        with self.web_client.session_transaction() as sess:
            sess.clear()

        resp = self.web_client.get("/uploads/portraits/secret.png")
        self.assertEqual(resp.status_code, 401)

    def test_06_login_constant_time_open_redirect_and_rate_limit(self) -> None:
        from application.auth.views import _login_limiter

        _login_limiter.reset("127.0.0.1")

        t0 = time.perf_counter()
        resp_unknown = self.web_client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "WrongPassword!"},
        )
        dt_unknown = time.perf_counter() - t0

        t1 = time.perf_counter()
        resp_known = self.web_client.post(
            "/login",
            data={"email": "alice@example.com", "password": "WrongPassword!"},
        )
        dt_known = time.perf_counter() - t1

        self.assertEqual(resp_unknown.status_code, 200)
        self.assertEqual(resp_known.status_code, 200)
        self.assertGreater(dt_unknown, 0.02)
        self.assertLess(abs(dt_known - dt_unknown), 0.25)

        _login_limiter.reset("127.0.0.1")
        resp_redirect = self.web_client.post(
            "/login?next=https://evil.example/phish",
            data={"email": "alice@example.com", "password": "AlicePass123!"},
            follow_redirects=False,
        )
        self.assertEqual(resp_redirect.status_code, 302)
        self.assertNotIn("evil.example", resp_redirect.headers.get("Location", ""))

        _login_limiter.reset("127.0.0.1")
        for _ in range(10):
            self.web_client.post(
                "/login",
                data={"email": "nobody@example.com", "password": "bad"},
            )
        resp_limited = self.web_client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "bad"},
        )
        self.assertEqual(resp_limited.status_code, 429)

    def test_07_production_secret_key_validation(self) -> None:
        from shared.security import validate_secret_key

        with self.assertRaises(RuntimeError):
            validate_secret_key(
                "aimo-dev-only-change-in-production",
                "aimo-dev-only-change-in-production",
                debug=False,
            )


if __name__ == "__main__":
    unittest.main()
