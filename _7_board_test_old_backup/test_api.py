"""RESTful API Automated Verification Script

Tests JWT authentication, CRUD, search, filter, and cursor-based pagination.
"""

from app import app
import json
import sys

# Windows UTF-8 stdout safe handling
if sys.platform.startswith("win"):
  try:
    sys.stdout.reconfigure(encoding="utf-8")
  except Exception:
    pass


def test_all():
  client = app.test_client()
  print("\n========== [1. Auth Tests] ==========")

  # 1. Login with sample admin
  res = client.post(
      "/api/auth/login",
      data=json.dumps({"username": "admin", "password": "1234"}),
      content_type="application/json",
  )
  assert res.status_code == 200, f"Login failed: {res.data}"
  admin_token = res.get_json()["token"]
  print("[OK] Admin Login Success! JWT Token generated.")

  # 2. Register a new test user
  reg_res = client.post(
      "/api/auth/register",
      data=json.dumps({
          "username": "tester_new_user_1",
          "password": "password123",
          "nickname": "새내기테스터",
      }),
      content_type="application/json",
  )
  assert reg_res.status_code in (201, 409)
  print("[OK] Register Endpoint Success!")

  # 3. Check /me with Bearer token
  me_res = client.get(
      "/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
  )
  assert me_res.status_code == 200
  assert me_res.get_json()["user"]["username"] == "admin"
  print("[OK] /api/auth/me Profile Verification Success!")

  print("\n========== [2. Categories & Filter Tests] ==========")
  cat_res = client.get("/api/categories")
  assert cat_res.status_code == 200
  categories = cat_res.get_json()["categories"]
  print(f"[OK] Categories: {[c['name'] for c in categories]}")

  print("\n========== [3. Cursor Pagination Tests] ==========")
  # First page with limit=3
  p1_res = client.get("/api/posts?limit=3")
  assert p1_res.status_code == 200
  p1_data = p1_res.get_json()
  assert len(p1_data["items"]) == 3
  assert p1_data["has_more"] is True
  next_cursor = p1_data["next_cursor"]
  print(
      f"[OK] Page 1 Loaded: 3 items, has_more={p1_data['has_more']},"
      f" next_cursor={next_cursor}"
  )

  # Second page using next_cursor
  p2_res = client.get(f"/api/posts?limit=3&cursor={next_cursor}")
  assert p2_res.status_code == 200
  p2_data = p2_res.get_json()
  assert len(p2_data["items"]) == 3
  print(
      f"[OK] Page 2 Loaded via Cursor ({next_cursor}): 3 items,"
      f" next_cursor={p2_data['next_cursor']}"
  )

  print("\n========== [4. Search & Filter Tests] ==========")
  # Search keyword 'Flask'
  search_res = client.get("/api/posts?search=Flask&search_type=all")
  assert search_res.status_code == 200
  search_data = search_res.get_json()
  print(f"[OK] Search 'Flask' Results Count: {len(search_data['items'])}")

  # Filter by category '공지'
  filter_res = client.get("/api/posts?category=공지")
  assert filter_res.status_code == 200
  filter_data = filter_res.get_json()
  print(f"[OK] Filter '공지' Results Count: {len(filter_data['items'])}")

  print("\n========== [5. CRUD Tests] ==========")
  # Create Post
  create_res = client.post(
      "/api/posts",
      headers={"Authorization": f"Bearer {admin_token}"},
      data=json.dumps({
          "title": "자동화 테스트 게시글",
          "content": "RESTful CRUD 및 커서 페이징 테스트 본문입니다.",
          "category": "자유",
      }),
      content_type="application/json",
  )
  assert create_res.status_code == 201
  new_post_id = create_res.get_json()["post_id"]
  print(f"[OK] Post Created! ID: {new_post_id}")

  # Read Detail
  detail_res = client.get(
      f"/api/posts/{new_post_id}",
      headers={"Authorization": f"Bearer {admin_token}"},
  )
  assert detail_res.status_code == 200
  post_obj = detail_res.get_json()["post"]
  assert post_obj["is_author"] is True
  print(
      f"[OK] Post Detail Read: Title='{post_obj['title']}',"
      f" Views={post_obj['views']}"
  )

  # Update Post
  update_res = client.put(
      f"/api/posts/{new_post_id}",
      headers={"Authorization": f"Bearer {admin_token}"},
      data=json.dumps({
          "title": "수정된 자동화 테스트 게시글",
          "content": "내용이 성공적으로 수정되었습니다.",
          "category": "팁",
      }),
      content_type="application/json",
  )
  assert update_res.status_code == 200
  print("[OK] Post Updated Successfully!")

  # Delete Post
  delete_res = client.delete(
      f"/api/posts/{new_post_id}",
      headers={"Authorization": f"Bearer {admin_token}"},
  )
  assert delete_res.status_code == 200
  print("[OK] Post Deleted Successfully!")

  print("\n*** ALL 12 AUTOMATED API TESTS PASSED SUCCESSFULLY! ***")


if __name__ == "__main__":
  test_all()
