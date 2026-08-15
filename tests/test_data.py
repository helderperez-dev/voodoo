import asyncio

import pytest
import pytest_asyncio

from voodoo.data import BaseModel, on_insert, on_update, rls_policy


class User(BaseModel):
    name: str
    age: int
    is_active: bool


class Post(BaseModel):
    title: str
    content: str
    user_id: int


inserted_users = []
updated_users = []


@on_insert(User)
async def hook_insert_user(user):
    inserted_users.append(user.name)


@on_update(User)
def hook_update_user(user):
    updated_users.append(user.name)


@rls_policy(Post)
def post_policy(context):
    if context.get("role") == "admin":
        return None
    return f"user_id = {context.get('user_id', 0)}"


@pytest_asyncio.fixture(autouse=True)
async def clear_db(test_db):
    await test_db.execute("DELETE FROM user")
    await test_db.execute("DELETE FROM post")
    await test_db.commit()


@pytest.mark.asyncio
async def test_orm_operations(test_db):
    # Insert
    u = User()
    u.name = "Alice"
    u.age = 30
    u.is_active = True
    await u.insert()

    assert u.id is not None

    # Wait for the async trigger to execute
    await asyncio.sleep(0.01)
    assert "Alice" in inserted_users

    # Find all
    users = await User.find_all()
    assert len(users) == 1
    assert users[0].name == "Alice"
    assert users[0].age == 30
    assert users[0].is_active is True

    # Update
    u.age = 31
    await u.update()

    # Wait for the sync trigger to execute (called directly in update)
    await asyncio.sleep(0.01)
    assert "Alice" in updated_users

    users = await User.find_all()
    assert users[0].age == 31


@pytest.mark.asyncio
async def test_rls_policies(test_db):
    p1 = Post()
    p1.title = "Hello"
    p1.content = "World"
    p1.user_id = 1
    await p1.insert()

    p2 = Post()
    p2.title = "Secret"
    p2.content = "Admin only"
    p2.user_id = 2
    await p2.insert()

    # User 1 context
    user_context = {"user_id": 1, "role": "user"}
    posts = await Post.find_all(user_context=user_context)
    assert len(posts) == 1
    assert posts[0].title == "Hello"

    # Admin context
    admin_context = {"user_id": 99, "role": "admin"}
    all_posts = await Post.find_all(user_context=admin_context)
    assert len(all_posts) == 2
