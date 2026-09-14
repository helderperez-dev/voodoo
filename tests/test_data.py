import asyncio

import pytest

from voodoo.data import BaseModel, on_insert, on_update, rls_policy


class User(BaseModel):
    name: str
    age: int
    is_active: bool


class Post(BaseModel):
    title: str
    content: str
    user_id: int


inserted_users: list[str] = []
updated_users: list[str] = []


@on_insert(User)
async def hook_insert_user(user: User) -> None:
    inserted_users.append(user.name)


@on_update(User)
def hook_update_user(user: User) -> None:
    updated_users.append(user.name)


@rls_policy(Post)
def post_policy(row: dict, context: dict) -> bool:
    if context.get("role") == "admin":
        return True
    return row.get("user_id") == context.get("user_id")


@pytest.mark.asyncio
async def test_orm_operations(model_store):
    inserted_users.clear()
    updated_users.clear()

    user = User()
    user.name = "Alice"
    user.age = 30
    user.is_active = True
    await user.insert()

    assert user.id is not None

    await asyncio.sleep(0.01)
    assert "Alice" in inserted_users

    users = await User.find_all()
    assert len(users) == 1
    assert users[0].name == "Alice"
    assert users[0].age == 30
    assert users[0].is_active is True

    user.age = 31
    await user.update()
    assert "Alice" in updated_users

    users = await User.find_all()
    assert users[0].age == 31


@pytest.mark.asyncio
async def test_rls_policies(model_store):
    post1 = Post()
    post1.title = "Hello"
    post1.content = "World"
    post1.user_id = 1
    await post1.insert()

    post2 = Post()
    post2.title = "Secret"
    post2.content = "Admin only"
    post2.user_id = 2
    await post2.insert()

    user_context = {"user_id": 1, "role": "user"}
    posts = await Post.find_all(user_context=user_context)
    assert len(posts) == 1
    assert posts[0].title == "Hello"

    admin_context = {"user_id": 99, "role": "admin"}
    all_posts = await Post.find_all(user_context=admin_context)
    assert len(all_posts) == 2
