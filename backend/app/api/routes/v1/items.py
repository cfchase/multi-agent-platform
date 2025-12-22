from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    search: str | None = Query(default=None, description="Search by title or description"),
    sort_by: str = Query(default="id", description="Sort by field (id, title)"),
    sort_order: Literal["asc", "desc"] = Query(default="asc", description="Sort order"),
) -> Any:
    """
    Retrieve items.

    Returns all items with pagination, optional search, and sorting.
    """
    # Build base query
    statement = select(Item)

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        statement = statement.where(
            (Item.title.ilike(search_pattern)) | (Item.description.ilike(search_pattern))
        )

    # Get count before pagination
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    # Apply sorting
    sort_column = getattr(Item, sort_by, Item.id)
    if sort_order == "desc":
        statement = statement.order_by(sort_column.desc())
    else:
        statement = statement.order_by(sort_column.asc())

    # Apply pagination
    statement = statement.offset(skip).limit(limit)
    items = session.exec(statement).all()

    return ItemsPublic(data=items, count=count)


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, id: int) -> Any:
    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(*, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate) -> Any:
    """
    Create new item.

    The item is associated with the current authenticated user.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *, session: SessionDep, current_user: CurrentUser, id: int, item_in: ItemUpdate
) -> Any:
    """
    Update an item.

    Users can only update their own items (unless admin).
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check ownership (admins can update any item)
    if item.owner_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(session: SessionDep, current_user: CurrentUser, id: int) -> Message:
    """
    Delete an item.

    Users can only delete their own items (unless admin).
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check ownership (admins can delete any item)
    if item.owner_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
