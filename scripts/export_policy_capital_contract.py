import json
from pathlib import Path

from fastapi import FastAPI

from backend.policy_capital_contract import (
    ContractError,
    EvidencePackage,
    ExecutionPreview,
    ExecutionRequest,
    ResearchJob,
    ResearchRequest,
)

app=FastAPI(title='Policy capital evidence contract (design only)', version='1.0.0')
@app.get('/api/research/evidence/{package_id}', response_model=EvidencePackage,
         responses={404:{'model':ContractError},422:{'model':ContractError},503:{'model':ContractError}})
def evidence_contract(package_id: str) -> EvidencePackage:
    raise NotImplementedError('Schema only; not mounted in production')
@app.post('/api/research/jobs', status_code=202, response_model=ResearchJob,
          responses={409:{'model':ContractError},422:{'model':ContractError},503:{'model':ContractError}})
def create_job(body: ResearchRequest) -> ResearchJob:
    raise NotImplementedError
@app.get('/api/research/jobs/{job_id}', response_model=ResearchJob,
         responses={404:{'model':ContractError},503:{'model':ContractError}})
def get_job(job_id: str) -> ResearchJob:
    raise NotImplementedError
@app.post('/api/research/execution-preview', response_model=ExecutionPreview,
          responses={404:{'model':ContractError},422:{'model':ContractError},503:{'model':ContractError}})
def preview(body: ExecutionRequest) -> ExecutionPreview:
    raise NotImplementedError
Path('docs/03-modules/08-backend-api/policy-capital/openapi.json').write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2)+'\n')
