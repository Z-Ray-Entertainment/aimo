import sys
from pathlib import Path
import tempfile
import uuid

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "core"
FLASK_DIR = PROJECT_ROOT / "flask"
for p in (str(CORE_DIR), str(FLASK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from domain.auth.models import User
from domain.characters.models import Character, EmotionalSprite, Emotion, Gender
from domain.lorebooks.models import Lorebook, LorebookEntry
from domain.worldinfo.models import WorldInfo, Location, Event
from domain.permissions.models import Preset, PRESET_PERMISSIONS
from infrastructure.database import init_db
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.repositories.user_repository import UserRepository


def run_tests():
    print("=== Testing Creator Authorization, Creator-Tags & Duplication ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        import os
        import infrastructure.database as db_mod
        from shared.config import Config
        os.environ["AIMO_DB_PATH"] = str(db_path)
        Config.DB_PATH = db_path
        db_mod._RESOLVED_DB_PATH = db_path

        init_db(db_path)

        user_repo = UserRepository()
        char_repo = CharacterRepository()
        lb_repo = LorebookRepository()
        wi_repo = WorldInfoRepository()

        # 1. Test User creation & Creator-Tag generation
        user_a = user_repo.create(
            User(
                id=None,
                username="AuthorAlice",
                email="alice@aimo.local",
                password_hash="hash_a",
            )
        )
        assert user_a.id is not None
        assert user_a.creator_tag, "User A must have a non-empty creator_tag"
        # Validate UUID4 format
        uuid_a = uuid.UUID(user_a.creator_tag)
        assert uuid_a.version == 4, "Creator-Tag must be a valid UUID4"

        user_b = user_repo.create(
            User(
                id=None,
                username="CreatorBob",
                email="bob@aimo.local",
                password_hash="hash_b",
            )
        )
        assert user_b.id is not None
        assert user_b.creator_tag, "User B must have a non-empty creator_tag"
        assert user_a.creator_tag != user_b.creator_tag, "Creator-Tags must be unique"
        print("✓ Test 1: Creator-Tags generated as unique UUID4 for all users.")

        # 2. Author creates Character, Lorebook, and WorldInfo
        char = char_repo.save(
            Character(
                id=None,
                user_id=user_a.id,
                name="Elara",
                gender=Gender.FEMALE,
                primary_portrait_path="portraits/elara.png",
                description="An elven mage.",
                first_message="Greetings, traveler.",
                visibility="public",
            )
        )
        assert char.id is not None
        # Add a sprite to char
        char_repo.add_sprite(
            char.id,
            EmotionalSprite(emotion=Emotion.JOY, variant=1, file_path="sprites/elara_joy_1.png"),
        )
        char = char_repo.get_by_id(char.id)
        assert len(char.sprites) == 1

        lb = lb_repo.create(
            Lorebook(
                id=None,
                user_id=user_a.id,
                name="Elven Lore",
                description="Ancient texts",
                visibility="public",
            )
        )
        assert lb.id is not None
        lb_repo.add_entry(
            LorebookEntry(
                id=None,
                lorebook_id=lb.id,
                title="Moon Magic",
                tags=["moon", "magic"],
                content="Luminescent incantations.",
            )
        )

        wi = wi_repo.create(
            WorldInfo(
                id=None,
                user_id=user_a.id,
                name="Silverwood Realm",
                visibility="public",
            )
        )
        assert wi.id is not None
        loc = wi_repo.add_location(
            Location(
                id=None,
                worldinfo_id=wi.id,
                name="Crystal Glade",
                tags=["forest", "crystals"],
                description="A serene glade with luminescent crystals.",
            )
        )
        assert loc.id is not None
        wi_repo.add_event(
            Event(
                id=None,
                worldinfo_id=wi.id,
                title="Starlight Blessing",
                probability=40,
                one_shot=False,
                description="Stars rain gentle blessings.",
                location_id=loc.id,
            )
        )

        print("✓ Test 2: Author successfully created creations with child entities.")

        # 3. Check author vs non-author permissions (Zero-Trust)
        # Alice (author) has edit and delete rights
        assert char.is_editable_by_user(user_a.id, False, user_a.creator_tag) is True
        assert char.is_deletable_by_user(user_a.id, False) is True
        assert lb.is_editable_by_user(user_a.id, False, user_a.creator_tag) is True
        assert lb.is_deletable_by_user(user_a.id, False) is True
        assert wi.is_editable_by_user(user_a.id, False, user_a.creator_tag) is True
        assert wi.is_deletable_by_user(user_a.id, False) is True

        # Bob (other creator) does NOT have edit or delete rights
        assert char.is_editable_by_user(user_b.id, False, user_b.creator_tag) is False
        assert char.is_deletable_by_user(user_b.id, False) is False
        assert lb.is_editable_by_user(user_b.id, False, user_b.creator_tag) is False
        assert lb.is_deletable_by_user(user_b.id, False) is False
        assert wi.is_editable_by_user(user_b.id, False, user_b.creator_tag) is False
        assert wi.is_deletable_by_user(user_b.id, False) is False
        print("✓ Test 3: Zero-Trust verified: Non-authors without tag cannot edit or delete.")

        # 4. Deep Duplication by Bob
        # Bob duplicates Character
        dup_char = char_repo.duplicate(char.id, user_b.id)
        assert dup_char.id is not None and dup_char.id != char.id
        assert dup_char.user_id == user_b.id
        assert dup_char.name == "Elara (Kopie)"
        assert dup_char.visibility == "private"
        assert len(dup_char.sprites) == 1
        assert dup_char.sprites[0].file_path == "sprites/elara_joy_1.png"
        assert dup_char.is_editable_by_user(user_b.id, False, user_b.creator_tag) is True

        # Bob duplicates Lorebook
        dup_lb = lb_repo.duplicate(lb.id, user_b.id)
        assert dup_lb.id is not None and dup_lb.id != lb.id
        assert dup_lb.user_id == user_b.id
        assert dup_lb.name == "Elven Lore (Kopie)"
        dup_entries = lb_repo.list_entries(dup_lb.id)
        assert len(dup_entries) == 1
        assert dup_entries[0].title == "Moon Magic"
        assert dup_lb.is_editable_by_user(user_b.id, False, user_b.creator_tag) is True

        # Bob duplicates WorldInfo
        dup_wi = wi_repo.duplicate(wi.id, user_b.id)
        assert dup_wi.id is not None and dup_wi.id != wi.id
        assert dup_wi.user_id == user_b.id
        assert dup_wi.name == "Silverwood Realm (Kopie)"
        dup_locs = wi_repo.list_locations(dup_wi.id)
        assert len(dup_locs) == 1
        assert dup_locs[0].name == "Crystal Glade"
        dup_events = wi_repo.list_events(dup_wi.id)
        assert len(dup_events) == 1
        assert dup_events[0].title == "Starlight Blessing"
        assert dup_events[0].location_id == dup_locs[0].id, "Event location_id must be mapped to the newly duplicated location!"
        assert dup_wi.is_editable_by_user(user_b.id, False, user_b.creator_tag) is True
        print("✓ Test 4: Deep duplication works flawlessly for Character, Lorebook, and WorldInfo.")

        # 5. Creator-Tag Collaboration
        # Alice adds Bob's creator_tag to her original Character and WorldInfo
        char.collaborator_creator_tags = [user_b.creator_tag]
        char_repo.save(char)

        wi.collaborator_creator_tags = [user_b.creator_tag]
        wi_repo.update(wi)

        # Reload from DB
        reloaded_char = char_repo.get_by_id(char.id)
        assert user_b.creator_tag in reloaded_char.collaborator_creator_tags
        # Now Bob CAN edit Alice's Character
        assert reloaded_char.is_editable_by_user(user_b.id, False, user_b.creator_tag) is True
        # But Bob CANNOT delete Alice's Character
        assert reloaded_char.is_deletable_by_user(user_b.id, False) is False

        reloaded_wi = wi_repo.get_by_id(wi.id)
        assert user_b.creator_tag in reloaded_wi.collaborator_creator_tags
        # Bob CAN edit Alice's WorldInfo
        assert reloaded_wi.is_editable_by_user(user_b.id, False, user_b.creator_tag) is True
        # But Bob CANNOT delete Alice's WorldInfo
        assert reloaded_wi.is_deletable_by_user(user_b.id, False) is False

        # Lorebook was not shared with Bob, so Bob still CANNOT edit it
        reloaded_lb = lb_repo.get_by_id(lb.id)
        assert reloaded_lb.is_editable_by_user(user_b.id, False, user_b.creator_tag) is False

        print("✓ Test 5: Creator-Tag collaboration verified: Edit access granted, deletion denied.")

        # 6. Admin override
        assert reloaded_char.is_editable_by_user(999, is_admin=True) is True
        assert reloaded_char.is_deletable_by_user(999, is_admin=True) is True
        print("✓ Test 6: Initial admin permissions intact.")

        # 7. Flask Web UI Routes testing
        from app import create_webui_app
        flask_app = create_webui_app()
        flask_app.config["TESTING"] = True
        client = flask_app.test_client()

        # Give Alice and Bob Creator preset permissions
        for u in (user_a, user_b):
            user_repo.save_permissions(
                user_repo.get_permissions(u.id).__class__(
                    user_id=u.id,
                    permissions=set(PRESET_PERMISSIONS[Preset.CREATOR]),
                )
            )

        with client.session_transaction() as sess:
            sess["user_id"] = user_b.id

        # Create an unshared public character by Alice to test the copy button
        char_unshared = char_repo.save(
            Character(
                id=None,
                user_id=user_a.id,
                name="Sylvanus Unshared",
                gender=Gender.MALE,
                primary_portrait_path="portraits/sylvanus.png",
                description="Forest guardian",
                first_message="Greetings",
                visibility="public",
                collaborator_creator_tags=[],
            )
        )

        # 7a. GET /overview - Bob sees edit button for char (shared via creator_tag)
        # and duplicate button for char_unshared (not shared)
        resp = client.get("/overview", follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert f"/characters/{char.id}/edit" in html  # Shared: Bob has edit link
        assert (
            f"/characters/{char_unshared.id}/duplicate" in html
            or f"/characters/{char_unshared.id}/copy" in html
        )  # Not shared: Bob has copy/duplicate form
        assert "creator-tag-modal" in html
        assert user_b.creator_tag in html

        # 7b. POST /characters/<id>/duplicate - Bob duplicates Alice's character
        resp = client.post(f"/characters/{char_unshared.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        assert "Kopie" in resp.get_data(as_text=True)

        # 7c. POST /worldinfo/<id>/duplicate - Bob duplicates Alice's world
        resp = client.post(f"/worldinfo/{wi.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        assert "Kopie" in resp.get_data(as_text=True)

        # 7d. POST /lorebooks/<id>/duplicate - Bob duplicates Alice's lorebook
        resp = client.post(f"/lorebooks/{lb.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        assert "Kopie" in resp.get_data(as_text=True)

        print("✓ Test 7: Flask Web UI routes and modals verified end-to-end.")

        # 8. Headless Core REST API Verification
        client_key = "test-secret-client-key-12345"
        os.environ["CLIENT_KEY"] = client_key
        import importlib.machinery
        core_app_mod = importlib.machinery.SourceFileLoader("core_app", str(CORE_DIR / "app.py")).load_module()
        core_app = core_app_mod.create_core_app()
        core_app.config["TESTING"] = True
        core_client = core_app.test_client()

        # 8a. Request without CLIENT_KEY should fail with 401
        resp_unauth = core_client.post(f"/api/characters/{char.id}/duplicate")
        assert resp_unauth.status_code == 401

        # 8b. Duplication via REST API with CLIENT_KEY and Bob's user ID
        headers = {
            "X-Client-Key": client_key,
            "X-User-Id": str(user_b.id),
        }

        # Character REST duplicate
        resp_char = core_client.post(f"/api/characters/{char.id}/duplicate", headers=headers)
        assert resp_char.status_code == 201
        data_char = resp_char.get_json()
        assert data_char["id"] is not None
        assert "Kopie" in data_char["name"]

        # WorldInfo REST duplicate
        resp_wi = core_client.post(f"/api/worldinfo/{wi.id}/duplicate", headers=headers)
        assert resp_wi.status_code == 201
        data_wi = resp_wi.get_json()
        assert data_wi["id"] is not None
        assert "Kopie" in data_wi["name"]

        # Lorebook REST duplicate
        resp_lb = core_client.post(f"/api/lorebooks/{lb.id}/duplicate", headers=headers)
        assert resp_lb.status_code == 201
        data_lb = resp_lb.get_json()
        assert data_lb["id"] is not None
        assert "Kopie" in data_lb["name"]

        print("✓ Test 8: Headless REST API endpoints (/duplicate) and security headers verified.")

        # 9. Collaboration Tab & Reusable Component Verification across all three editors
        # 9a. Lorebook Tab View (Grundeinstellungen, Einträge, Kollaboration) & Collaboration Manager
        with client.session_transaction() as sess:
            sess["user_id"] = user_a.id  # Alice (author)

        resp_lb_get = client.get(f"/lorebooks/{lb.id}")
        assert resp_lb_get.status_code == 200
        html_lb = resp_lb_get.get_data(as_text=True)

        # Tab navigation checks: 3 tabs
        assert 'data-tab-target="tab-info"' in html_lb
        assert "Grundeinstellungen" in html_lb
        assert 'data-tab-target="tab-entries"' in html_lb
        assert 'data-tab-target="tab-collab"' in html_lb

        # Default active tab must be Grundeinstellungen (tab-info)
        assert 'id="tab-info" class="tab-pane active"' in html_lb
        assert 'data-tab-target="tab-info"' in html_lb

        # Header action buttons: Speichern (with form="lorebook-meta-form"), Duplizieren, Löschen
        assert 'form="lorebook-meta-form"' in html_lb
        assert 'Speichern</button>' in html_lb
        assert 'Duplizieren</button>' in html_lb
        assert 'Lorebook löschen</button>' in html_lb

        # Tab 1: Grundeinstellungen form fields
        assert 'name="name"' in html_lb
        assert 'name="visibility"' in html_lb
        assert 'name="description"' in html_lb

        # Collab tab elements
        assert "collab-table" in html_lb
        assert "Neuen Creator hinzufügen" in html_lb
        assert "i18n-lb-desc" not in html_lb, "Lorebook description translation feature must be removed"
        assert 'data-i18n-entity-type="lorebook"' not in html_lb, "Lorebook translation attributes must be removed"

        # Alice adds Bob's creator tag to Lorebook and updates metadata via form submit
        resp_lb_post = client.post(
            f"/lorebooks/{lb.id}",
            data={
                "name": "Updated Lorebook Name",
                "visibility": "public",
                "description": "Updated Kurzbeschreibung in Tab 1",
                "collaborator_creator_tags": user_b.creator_tag,
            },
            follow_redirects=True,
        )
        assert resp_lb_post.status_code == 200
        reloaded_lb = lb_repo.get_by_id(lb.id)
        assert reloaded_lb.name == "Updated Lorebook Name"
        assert reloaded_lb.visibility == "public"
        assert reloaded_lb.description == "Updated Kurzbeschreibung in Tab 1"
        assert user_b.creator_tag in reloaded_lb.collaborator_creator_tags

        # Adding an entry redirects to tab=entries
        resp_entry = client.post(
            f"/lorebooks/{lb.id}/entries/add",
            data={
                "title": "Neuer Testeintrag",
                "tags": "test, magie",
                "content": "Inhalt des Eintrags",
                "visibility": "public",
            },
            follow_redirects=False,
        )
        assert resp_entry.status_code == 302
        assert "tab=entries" in resp_entry.location

        # Bob views the Lorebook: sees collaboration tab as collaborator with read-only view
        with client.session_transaction() as sess:
            sess["user_id"] = user_b.id

        resp_bob_lb = client.get(f"/lorebooks/{lb.id}")
        assert resp_bob_lb.status_code == 200
        html_bob_lb = resp_bob_lb.get_data(as_text=True)
        assert "Kollaborator-Ansicht" in html_bob_lb
        assert user_b.creator_tag in html_bob_lb
        assert "Neuen Creator hinzufügen" not in html_bob_lb  # Collaborators cannot add others

        # 9b. WorldInfo Collaboration Tab
        with client.session_transaction() as sess:
            sess["user_id"] = user_a.id  # Alice

        resp_wi_get = client.get(f"/worldinfo/{wi.id}")
        assert resp_wi_get.status_code == 200
        html_wi = resp_wi_get.get_data(as_text=True)
        assert 'data-tab-target="tab-places"' in html_wi
        assert 'data-tab-target="tab-events"' in html_wi
        assert 'data-tab-target="tab-collab"' in html_wi
        assert "collab-table" in html_wi

        # 9c. Character Designer Collaboration Tab
        resp_char_get = client.get(f"/characters/{char.id}/edit")
        assert resp_char_get.status_code == 200
        html_char = resp_char_get.get_data(as_text=True)
        assert 'data-tab-target="tab-char-collab"' in html_char
        assert "collab-table" in html_char
        assert "Neuen Creator hinzufügen" in html_char

        print("✓ Test 9: Collaboration tab & reusable collaboration_manager verified across Character, WorldInfo, and Lorebooks.")

        # 10. Verification: Users without creator permission do NOT see Creator-Tag in UI
        user_c = user_repo.create(
            User(
                id=None,
                username="RegularCharlie",
                email="charlie@aimo.local",
                password_hash="hash_c",
            )
        )
        assert user_c.id is not None
        assert user_c.creator_tag, "Creator tag is generated in DB for Charlie"

        # Give Charlie only USER preset (only chat_access and persona_manage, NO creator permissions)
        user_repo.save_permissions(
            user_repo.get_permissions(user_c.id).__class__(
                user_id=user_c.id,
                permissions=set(PRESET_PERMISSIONS[Preset.USER]),
            )
        )

        with client.session_transaction() as sess:
            sess["user_id"] = user_c.id

        resp_charlie = client.get("/overview", follow_redirects=True)
        assert resp_charlie.status_code == 200
        html_charlie = resp_charlie.get_data(as_text=True)
        # Charlie must NOT see the creator-tag button or modal
        assert "data-modal-open=\"creator-tag-modal\"" not in html_charlie
        assert "id=\"creator-tag-modal\"" not in html_charlie
        assert user_c.creator_tag not in html_charlie

        # Bob (with CREATOR preset) DOES see the creator-tag button and modal
        with client.session_transaction() as sess:
            sess["user_id"] = user_b.id

        resp_bob = client.get("/overview", follow_redirects=True)
        assert resp_bob.status_code == 200
        html_bob = resp_bob.get_data(as_text=True)
        assert "data-modal-open=\"creator-tag-modal\"" in html_bob
        assert "id=\"creator-tag-modal\"" in html_bob
        assert user_b.creator_tag in html_bob

        print("✓ Test 10: Users without creator permissions do NOT see Creator-Tag in UI, while creators do.")

    print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY! 🎉")


if __name__ == "__main__":
    run_tests()
