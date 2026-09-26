from fastapi import HTTPException
from fastapi import status
from fastapi import APIRouter
from fastapi import Query

from app.schemas.post import (
    PostCreate,
    PostResponse,
    PostUpdate,
    PaginatedPostsResponse
)
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

from app.models.user import User
from app.models.post import Post
from app.core.database import get_db

from app.utils.auth import CurrentUser

router = APIRouter()

@router.get(
    "",
    response_model=PaginatedPostsResponse
)
async def get_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    # greater than or equal to 0 for skip, and between 1 and 100 for limit
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10
):
    count_result = await db.execute(
        select(func.count()).select_from(Post)
    )
    total = count_result.scalar() or 0
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .order_by(Post.date_posted.desc())
        .offset(skip)
        .limit(limit)
    )
    posts = result.scalars().all()
    has_more = skip + len(posts) < total
    return PaginatedPostsResponse(
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
        posts=[PostResponse.model_validate(post) for post in posts]
    )

@router.post(
    "", 
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_post(
    post: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    new_post = Post(
        title=post.title,
        content=post.content,
        user_id=current_user.id
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"]) # Refresh the instance to get the generated ID and other attributes from the database, including the author relationship
    return new_post

@router.get(
    "/{post_id}",
    response_model=PostResponse
)
async def get_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .where(Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return post

@router.put(
    "/{post_id}",
    response_model=PostResponse
)
async def update_post_full(
    post_id: int,
    post_data: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this post"
        )
    post.title = post_data.title
    post.content = post_data.content
    await db.commit()
    await db.refresh(post, attribute_names=["author"]) # Refresh the instance to get the updated author relationship
    return post


@router.patch(
    "/{post_id}",
    response_model=PostResponse
)
async def update_post_partial(
    post_id: int,
    post_data: PostUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this post"
        )
    update_data = post_data.model_dump(exclude_unset=True) # Get only the fields that were provided in the request
    for key, value in update_data.items():
        setattr(post, key, value)
    await db.commit()
    await db.refresh(post, attribute_names=["author"]) # Refresh the instance to get the updated author relationship
    return post

@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post"
        )
    await db.delete(post)
    await db.commit()