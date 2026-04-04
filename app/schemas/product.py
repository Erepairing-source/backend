"""Request/response models for org product catalog APIs."""
from __future__ import annotations

import json
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.product import ProductCategory, parse_product_category


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: ProductCategory = Field(
        ...,
        description="Slug or enum name, e.g. other, washing_machine, OTHER",
    )
    brand: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    default_warranty_months: int = Field(12, ge=0, le=600)
    extended_warranty_available: bool = False
    specifications: dict[str, Any] = Field(default_factory=dict)
    common_failures: List[str] = Field(default_factory=list)
    recommended_parts: List[Any] = Field(
        default_factory=list,
        description="Part IDs or codes as strings or integers",
    )
    model_number: Optional[str] = Field(None, max_length=100)
    is_active: bool = True
    additional_notes: Optional[str] = Field(
        None,
        description="Optional plain text; merged into specifications as additional_notes (no JSON needed).",
    )

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v):
        return parse_product_category(v)

    @field_validator("specifications", mode="before")
    @classmethod
    def _specs_from_json_string(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            t = v.strip()
            if not t:
                return {}
            try:
                parsed = json.loads(t)
            except json.JSONDecodeError:
                raise ValueError("specifications must be valid JSON or an object") from None
            if not isinstance(parsed, dict):
                raise ValueError("specifications JSON must be an object")
            return parsed
        if isinstance(v, dict):
            return v
        raise ValueError("specifications must be an object or JSON string")

    @field_validator("common_failures", mode="before")
    @classmethod
    def _failures_normalize(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [f.strip() for f in v.splitlines() if f.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        raise ValueError("common_failures must be a list or newline-separated text")

    @field_validator("recommended_parts", mode="before")
    @classmethod
    def _parts_normalize(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return list(v)
        raise ValueError("recommended_parts must be a list or comma-separated string")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[ProductCategory] = None
    brand: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    additional_notes: Optional[str] = Field(
        None,
        description="Plain text merged into specifications.additional_notes when set.",
    )
    default_warranty_months: Optional[int] = Field(None, ge=0, le=600)
    extended_warranty_available: Optional[bool] = None
    specifications: Optional[dict[str, Any]] = None
    common_failures: Optional[List[str]] = None
    recommended_parts: Optional[List[Any]] = None
    is_active: Optional[bool] = None

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category_optional(cls, v):
        if v is None:
            return None
        return parse_product_category(v)

    @field_validator("specifications", mode="before")
    @classmethod
    def _specs_from_json_string(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            t = v.strip()
            if not t:
                return {}
            try:
                parsed = json.loads(t)
            except json.JSONDecodeError:
                raise ValueError("specifications must be valid JSON or an object") from None
            if not isinstance(parsed, dict):
                raise ValueError("specifications JSON must be an object")
            return parsed
        if isinstance(v, dict):
            return v
        raise ValueError("specifications must be an object or JSON string")

    @field_validator("common_failures", mode="before")
    @classmethod
    def _failures_normalize(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return [f.strip() for f in v.splitlines() if f.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        raise ValueError("common_failures must be a list or newline-separated text")

    @field_validator("recommended_parts", mode="before")
    @classmethod
    def _parts_normalize(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return list(v)
        raise ValueError("recommended_parts must be a list or comma-separated string")
