from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.search import SearchError, get_search_provider
from app.schemas.research import ResearchReport
from app.schemas.search_request import ResearchRequest
from app.model import ModelError, get_report_generator
from app.planning import get_query_planner, retrieve

from app.schemas.chat import (
    AgentRequest,
    AgentResponse
)


app = FastAPI(
    title="InsightFlow Agent Service"
)

# V1 stays unchanged. V2 is disabled unless explicitly enabled at startup.
from app.web_research.api import router as web_router
app.include_router(web_router)
from app.web_research.session_api import router as session_router
app.include_router(session_router)
from app.web_research.execution_control import router as execution_router
app.include_router(execution_router)


@app.exception_handler(SearchError)
async def search_error(request, exception):
    return JSONResponse(status_code=504 if exception.code == "SEARCH_TIMEOUT" else 502,
                        content={"code": exception.code, "message": "Search provider could not complete retrieval"})


@app.post("/internal/v1/research/run", response_model=ResearchReport)
def research(request: ResearchRequest, provider=Depends(get_search_provider),
             generator=Depends(get_report_generator), planner=Depends(get_query_planner),
             execution_id: str | None = Header(default=None, alias='X-Research-Run-Id')):
    from app.web_research.execution_control import Execution, current, canonical
    from app.web_research.budget import BudgetExceeded
    from types import SimpleNamespace
    if not execution_id:
        return _wiki(request,provider,generator,planner)
    execution=Execution(SimpleNamespace(run_id=canonical(execution_id),question=request.question,
        language=request.language,resume_from=None),'wikipedia')
    execution.begin()
    if execution.cached is not None:
        return ResearchReport.model_validate(execution.cached)
    token=current.set(execution)
    try:
        result=_wiki(request,provider,generator,planner)
        execution.check()
        execution.finish(result.model_dump(mode='json',by_alias=True))
        return result
    except BudgetExceeded as error:
        execution.finish()
        raise HTTPException(409,detail={'code':error.code}) from None
    except Exception:
        execution.finish()
        raise
    finally:
        current.reset(token)


def _wiki(request,provider,generator,planner):
    report = retrieve(request.question, request.language, provider, planner)
    if report.plan.mode == "direct" and report.plan.reason != "PLANNING_DISABLED":
        return report  # A failed planner must not cause another model call in this attempt.
    from app.web_research.execution_control import current
    if current.get(): current.get().stage('report')
    return generator.generate(report)


@app.exception_handler(ModelError)
async def model_error(request, exception):
    return JSONResponse(status_code=504 if exception.code == "MODEL_TIMEOUT" else 502,
                        content={"code": exception.code, "message": "Model generation could not complete"})


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exception):
    # Do not include submitted content or internal validation details in errors.
    return JSONResponse(status_code=400, content={
        "code": "INVALID_REQUEST",
        "message": "Provide a non-blank question of at most 4000 UTF-16 code units in a JSON object",
    })


@app.get("/health")
def health():
    return {
        "status": "UP"
    }


@app.post("/internal/v1/agent/run", response_model=AgentResponse)
def run_agent(
        request: AgentRequest
):
    return AgentResponse(
        answer=f"Python Agent received: {request.question}",
        sources=[]
    )
