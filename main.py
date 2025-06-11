from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select

from dotenv import load_dotenv
import os

from redis_client import redis_client
from celery_worker import add
from assistant.openai_assistant import ask_openai
# .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy setup
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

# SQLAlchemy model
class ItemModel(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)

# Pydantic model
class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True

# FastAPI app
app = FastAPI()

class AskRequest(BaseModel):
    prompt: str

@app.post("/ask")
def ask(request: AskRequest):
    answer = ask_openai(request.prompt)
    return {"response": answer}

@app.get("/task/")
async def run_task():
    result = add.delay(5, 7)
    return {"task_id": result.id}


@app.get("/cache-example/")
async def cache_example():
    await redis_client.set("hello", "world")
    value = await redis_client.get("hello")
    return {"value": value}

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/items/", response_model=Item)
async def create_item(item: Item, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Item already exists")

    new_item = ItemModel(**item.dict())
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item

@app.get("/items/", response_model=List[Item])
async def read_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel))
    return result.scalars().all()

@app.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, updated: Item, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = updated.name
    item.description = updated.description
    await session.commit()
    await session.refresh(item)
    return item

@app.delete("/items/{item_id}")
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await session.delete(item)
    await session.commit()
    return {"message": "Item deleted"}





# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import List, Optional

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Mock database
# items_db = {}

# # Pydantic model
# class Item(BaseModel):
#     id: int
#     name: str
#     description: Optional[str] = None

# @app.post("/items/", response_model=Item)
# def create_item(item: Item):
#     if item.id in items_db:
#         raise HTTPException(status_code=400, detail="Item already exists")
#     items_db[item.id] = item
#     return item

# @app.get("/items/", response_model=List[Item])
# def read_items():
#     return list(items_db.values())

# @app.get("/items/{item_id}", response_model=Item)
# def read_item(item_id: int):
#     if item_id not in items_db:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return items_db[item_id]

# @app.put("/items/{item_id}", response_model=Item)
# def update_item(item_id: int, updated_item: Item):
#     if item_id not in items_db:
#         raise HTTPException(status_code=404, detail="Item not found")
#     items_db[item_id] = updated_item
#     return updated_item

# @app.delete("/items/{item_id}")
# def delete_item(item_id: int):
#     if item_id not in items_db:
#         raise HTTPException(status_code=404, detail="Item not found")
#     del items_db[item_id]
#     return {"message": "Item deleted"}

