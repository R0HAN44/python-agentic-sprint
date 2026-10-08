from fastapi import FastAPI,Query
from pydantic import BaseModel
from typing import Annotated,Any


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.model_dump()
    if item.tax is not None:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict
  
@app.get("/items/")
async def read_items(q: Annotated[str | None, Query(title="Query String", max_length=50)] = None):
    results : dict[str, Any] = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results