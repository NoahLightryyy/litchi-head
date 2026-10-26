"""Representative companies supplement a draft; they are not supply-chain edges."""
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChainCompaniesRequest(StrictModel):
    sector_name: str = Field(min_length=1, max_length=80)
    refresh: bool = False


class CompanyNodeRef(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_]{1,24}$")
    label: str = Field(min_length=1, max_length=60)


class CompanyReference(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    excerpt: str = Field(min_length=1, max_length=2000)
    accessed_at: datetime


class ChainCompany(StrictModel):
    node_id: str
    name: str = Field(min_length=2, max_length=80)
    business: str = Field(min_length=1, max_length=250)
    influence: str = Field(min_length=1, max_length=250)
    a_share_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    reference_status: Literal["public_reference", "ai_candidate"]
    sources: list[CompanyReference] = Field(max_length=3)

    @model_validator(mode="after")
    def references(self) -> Self:
        if (self.reference_status == "public_reference") != bool(self.sources):
            raise ValueError("Company reference status mismatch")
        if self.a_share_code and not self.sources:
            raise ValueError("A-share links require checked identity")
        return self


class ChainCompaniesResponse(StrictModel):
    schema_version: Literal[1] = 1
    sector_code: str
    sector_name: str
    graph_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_nodes: list[CompanyNodeRef] = Field(min_length=2, max_length=8)
    companies: list[ChainCompany] = Field(min_length=1, max_length=12)
    generated_at: datetime
    model: str
    cached: bool = False
    review_status: Literal["ai_unreviewed"] = "ai_unreviewed"

    @model_validator(mode="after")
    def identity(self) -> Self:
        ids = {node.id for node in self.graph_nodes}
        names = [item.name.casefold().strip() for item in self.companies]
        codes = [item.a_share_code for item in self.companies if item.a_share_code]
        if len(ids) != len(self.graph_nodes) or any(c.node_id not in ids for c in self.companies):
            raise ValueError("Invalid company node")
        if len(names) != len(set(names)) or len(codes) != len(set(codes)):
            raise ValueError("Duplicate company")
        return self


class ChainCompaniesErrorBody(StrictModel):
    code: Literal["CHAIN_COMPANIES_NOT_READY", "CHAIN_COMPANIES_BUSY",
                  "CHAIN_COMPANIES_TIMEOUT", "CHAIN_COMPANIES_FAILED", "CHAIN_COMPANIES_STORAGE"]
    message: str
    retryable: bool


class ChainCompaniesError(StrictModel):
    error: ChainCompaniesErrorBody
