from pydantic import BaseModel, Field
from typing import Optional


class ProductDetailsSchema(BaseModel):
    product_Id : Optional[str]  = None
    product_name: str
    brand_name: str
    category: str
    description: str
    bullet_points: list[str]
    product_price: float = Field(gt=0)
    product_mrp: Optional[float] = None
    product_quantity: float = Field(gt=0)
    product_images: Optional[list[str]] = None
    seller_id: Optional[str] = None
