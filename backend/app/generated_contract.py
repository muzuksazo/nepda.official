# Auto-generated from contracts/openapi.json by scripts/generate-backend-openapi.py
# Do not edit manually.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol, Tuple

from .generated_schemas import (
    AuthMeResponse,
    CompleteUploadsRequest,
    CompleteUploadsResponse,
    CreateFilmingGuideRequest,
    CreateHookRequest,
    CreateHookResponse,
    CreateJobRequest,
    CreateProjectRequest,
    CreateRenderRequest,
    CreateRenderResponse,
    DeliverablesResponse,
    EstimateRequest,
    EstimateResponse,
    FilmingGuideResponse,
    GenerateScenariosRequest,
    GenerateScenariosResponse,
    GenerateStoryboardRequest,
    GoogleAuthRequest,
    GoogleAuthResponse,
    HookStatusResponse,
    HookTypesResponse,
    OutputsResponse,
    PresignRequest,
    ProductInfoRequest,
    ProductInfoResponse,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectSummary,
    SelectScenarioResponse,
    StoryboardResponse,
)

OPENAPI_SPEC_VERSION: str = '0.2.0'


@dataclass(frozen=True)
class RouteContract:
    method: str
    path: str
    operation_id: str
    tags: Tuple[str, ...]
    success_status: int
    request_schema: str | None
    response_schema: str | None


EXPECTED_OPERATIONS: Tuple[RouteContract, ...] = (
    RouteContract(method='GET', path='/health', operation_id='health_health_get', tags=(), success_status=200, request_schema=None, response_schema=None),
    RouteContract(method='POST', path='/v1/uploads/presign', operation_id='presign_upload_v1_uploads_presign_post', tags=(), success_status=200, request_schema='PresignRequest', response_schema=None),
    RouteContract(method='GET', path='/v1/jobs', operation_id='list_jobs_v1_jobs_get', tags=(), success_status=200, request_schema=None, response_schema=None),
    RouteContract(method='POST', path='/v1/jobs', operation_id='create_job_v1_jobs_post', tags=(), success_status=202, request_schema='CreateJobRequest', response_schema=None),
    RouteContract(method='GET', path='/v1/jobs/{job_id}', operation_id='get_job_v1_jobs__job_id__get', tags=(), success_status=200, request_schema=None, response_schema=None),
    RouteContract(method='POST', path='/v1/jobs/{job_id}/retry-unit/{unit_id}', operation_id='retry_unit_v1_jobs__job_id__retry_unit__unit_id__post', tags=(), success_status=202, request_schema=None, response_schema=None),
    RouteContract(method='POST', path='/v1/auth/google', operation_id='auth_google_v1_auth_google_post', tags=('Auth',), success_status=200, request_schema='GoogleAuthRequest', response_schema='GoogleAuthResponse'),
    RouteContract(method='POST', path='/v1/auth/logout', operation_id='auth_logout_v1_auth_logout_post', tags=('Auth',), success_status=204, request_schema=None, response_schema=None),
    RouteContract(method='GET', path='/v1/auth/me', operation_id='auth_me_v1_auth_me_get', tags=('Auth',), success_status=200, request_schema=None, response_schema='AuthMeResponse'),
    RouteContract(method='GET', path='/v1/hook-types', operation_id='list_hook_types_v1_hook_types_get', tags=('Planning',), success_status=200, request_schema=None, response_schema='HookTypesResponse'),
    RouteContract(method='GET', path='/v1/projects', operation_id='list_projects_v1_projects_get', tags=('Projects',), success_status=200, request_schema=None, response_schema='ProjectListResponse'),
    RouteContract(method='POST', path='/v1/projects', operation_id='create_project_v1_projects_post', tags=('Projects',), success_status=201, request_schema='CreateProjectRequest', response_schema='ProjectSummary'),
    RouteContract(method='GET', path='/v1/projects/{project_id}', operation_id='get_project_v1_projects__project_id__get', tags=('Projects',), success_status=200, request_schema=None, response_schema='ProjectDetailResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/scenarios', operation_id='generate_scenarios_v1_projects__project_id__scenarios_post', tags=('Planning',), success_status=200, request_schema='GenerateScenariosRequest', response_schema='GenerateScenariosResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/scenarios/{scenario_id}/storyboard', operation_id='generate_storyboard_v1_projects__project_id__scenarios__scenario_id__storyboard_post', tags=('Planning',), success_status=200, request_schema='GenerateStoryboardRequest', response_schema='StoryboardResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/filming-guide', operation_id='create_filming_guide_v1_projects__project_id__filming_guide_post', tags=('Filming Guide',), success_status=200, request_schema='CreateFilmingGuideRequest', response_schema='FilmingGuideResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/estimate', operation_id='estimate_credits_v1_projects__project_id__estimate_post', tags=('Credits',), success_status=200, request_schema='EstimateRequest', response_schema='EstimateResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/uploads/complete', operation_id='complete_uploads_v1_projects__project_id__uploads_complete_post', tags=('Uploads',), success_status=200, request_schema='CompleteUploadsRequest', response_schema='CompleteUploadsResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/renders', operation_id='create_render_v1_projects__project_id__renders_post', tags=('Generation',), success_status=202, request_schema='CreateRenderRequest', response_schema='CreateRenderResponse'),
    RouteContract(method='GET', path='/v1/projects/{project_id}/deliverables', operation_id='get_deliverables_v1_projects__project_id__deliverables_get', tags=('Delivery',), success_status=200, request_schema=None, response_schema='DeliverablesResponse'),
    RouteContract(method='POST', path='/v1/product-info', operation_id='create_product_info_v1_product_info_post', tags=('Projects',), success_status=200, request_schema='ProductInfoRequest', response_schema='ProductInfoResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/scenarios/{scenario_id}/select', operation_id='select_scenario_v1_projects__project_id__scenarios__scenario_id__select_post', tags=('Planning',), success_status=200, request_schema=None, response_schema='SelectScenarioResponse'),
    RouteContract(method='POST', path='/v1/projects/{project_id}/hooks', operation_id='create_hook_v1_projects__project_id__hooks_post', tags=('Hooks',), success_status=202, request_schema='CreateHookRequest', response_schema='CreateHookResponse'),
    RouteContract(method='GET', path='/v1/projects/{project_id}/hooks/{hook_id}', operation_id='get_hook_v1_projects__project_id__hooks__hook_id__get', tags=('Hooks',), success_status=200, request_schema=None, response_schema='HookStatusResponse'),
    RouteContract(method='GET', path='/v1/projects/{project_id}/outputs', operation_id='list_outputs_v1_projects__project_id__outputs_get', tags=('Hooks',), success_status=200, request_schema=None, response_schema='OutputsResponse'),
)


class NapdaBackendProtocol(Protocol):
    """Typed FastAPI route contract generated from contracts/openapi.json."""

    def health_health_get(self) -> Dict[str, Any]: ...
    def presign_upload_v1_uploads_presign_post(self, body: PresignRequest) -> Dict[str, Any]: ...
    def list_jobs_v1_jobs_get(self, limit: int | None = None) -> Dict[str, Any]: ...
    def create_job_v1_jobs_post(self, body: CreateJobRequest) -> Dict[str, Any]: ...
    def get_job_v1_jobs__job_id__get(self, job_id: str) -> Dict[str, Any]: ...
    def retry_unit_v1_jobs__job_id__retry_unit__unit_id__post(self, job_id: str, unit_id: str) -> Dict[str, Any]: ...
    def auth_google_v1_auth_google_post(self, body: GoogleAuthRequest) -> GoogleAuthResponse: ...
    def auth_logout_v1_auth_logout_post(self) -> None: ...
    def auth_me_v1_auth_me_get(self) -> AuthMeResponse: ...
    def list_hook_types_v1_hook_types_get(self) -> HookTypesResponse: ...
    def list_projects_v1_projects_get(self, limit: int | None = None) -> ProjectListResponse: ...
    def create_project_v1_projects_post(self, body: CreateProjectRequest) -> ProjectSummary: ...
    def get_project_v1_projects__project_id__get(self, project_id: str) -> ProjectDetailResponse: ...
    def generate_scenarios_v1_projects__project_id__scenarios_post(self, project_id: str, body: GenerateScenariosRequest) -> GenerateScenariosResponse: ...
    def generate_storyboard_v1_projects__project_id__scenarios__scenario_id__storyboard_post(self, project_id: str, scenario_id: str, body: GenerateStoryboardRequest) -> StoryboardResponse: ...
    def create_filming_guide_v1_projects__project_id__filming_guide_post(self, project_id: str, body: CreateFilmingGuideRequest) -> FilmingGuideResponse: ...
    def estimate_credits_v1_projects__project_id__estimate_post(self, project_id: str, body: EstimateRequest) -> EstimateResponse: ...
    def complete_uploads_v1_projects__project_id__uploads_complete_post(self, project_id: str, body: CompleteUploadsRequest) -> CompleteUploadsResponse: ...
    def create_render_v1_projects__project_id__renders_post(self, project_id: str, body: CreateRenderRequest) -> CreateRenderResponse: ...
    def get_deliverables_v1_projects__project_id__deliverables_get(self, project_id: str) -> DeliverablesResponse: ...
    def create_product_info_v1_product_info_post(self, body: ProductInfoRequest) -> ProductInfoResponse: ...
    def select_scenario_v1_projects__project_id__scenarios__scenario_id__select_post(self, project_id: str, scenario_id: str) -> SelectScenarioResponse: ...
    def create_hook_v1_projects__project_id__hooks_post(self, project_id: str, body: CreateHookRequest) -> CreateHookResponse: ...
    def get_hook_v1_projects__project_id__hooks__hook_id__get(self, project_id: str, hook_id: str) -> HookStatusResponse: ...
    def list_outputs_v1_projects__project_id__outputs_get(self, project_id: str) -> OutputsResponse: ...
