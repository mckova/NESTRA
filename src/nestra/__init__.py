"""NESTRA: evidence-aware Python routing between retrieval and guarded LLM tiers."""

from .audit import append_audit, redact
from .config import DEFAULT_NESTRA_CONFIG, create_nestra_config, validate_config
from .control import GoalController, HookBus
from .evidence import (
    compile_atomic_evidence,
    evaluate_accuracy_lock,
    ground_answer_span,
    micro_prompt,
)
from .gate import evaluate_gate
from .memory import ScopedMemory, retention_score
from .metrics import MetricsCollector
from .ml import (
    ROUTER_FEATURE_NAMES,
    ROUTER_FEATURE_SCHEMA_VERSION,
    LearnedRouterModel,
    apply_learned_routing,
    evaluate_router_model,
    extract_oracle_router_features,
    extract_router_features,
    feature_vector,
    train_micro_safety_router,
)
from .models import load_bundled_router_model
from .project_memory import (
    ProjectMemoryIndex,
    compile_project_memory,
    evaluate_pre_call_gate,
    restore_project_memory,
    tokenize_project_text,
)
from .providers import (
    ModelProviderError,
    OpenAIResponsesProvider,
    create_openai_responses_provider,
    normalize_usage,
)
from .retrievers import assert_retriever, normalize_retrieved_documents
from .routing import NESTRA_ROUTES, route_nestra_query
from .runtime import NestraRuntime
from .security import (
    NestraRateLimitError,
    SlidingWindowRateLimiter,
    detect_prompt_injection,
    sanitize_user_text,
    stable_hash,
    validate_project_id,
)
from .server import create_nestra_server
from .storage import FileProjectStore, ProjectNotFoundError
from .topology import NESTRA_ROLES, create_fixed_nestra_plan, validate_nestra_plan
from .version import VERSION

__version__ = VERSION

__all__ = [
    "DEFAULT_NESTRA_CONFIG",
    "NESTRA_ROLES",
    "NESTRA_ROUTES",
    "ROUTER_FEATURE_NAMES",
    "ROUTER_FEATURE_SCHEMA_VERSION",
    "VERSION",
    "FileProjectStore",
    "GoalController",
    "HookBus",
    "LearnedRouterModel",
    "MetricsCollector",
    "ModelProviderError",
    "NestraRateLimitError",
    "NestraRuntime",
    "OpenAIResponsesProvider",
    "ProjectMemoryIndex",
    "ProjectNotFoundError",
    "ScopedMemory",
    "SlidingWindowRateLimiter",
    "__version__",
    "append_audit",
    "apply_learned_routing",
    "assert_retriever",
    "compile_atomic_evidence",
    "compile_project_memory",
    "create_fixed_nestra_plan",
    "create_nestra_config",
    "create_nestra_server",
    "create_openai_responses_provider",
    "detect_prompt_injection",
    "evaluate_accuracy_lock",
    "evaluate_gate",
    "evaluate_pre_call_gate",
    "evaluate_router_model",
    "extract_oracle_router_features",
    "extract_router_features",
    "feature_vector",
    "ground_answer_span",
    "load_bundled_router_model",
    "micro_prompt",
    "normalize_retrieved_documents",
    "normalize_usage",
    "redact",
    "restore_project_memory",
    "retention_score",
    "route_nestra_query",
    "sanitize_user_text",
    "stable_hash",
    "tokenize_project_text",
    "train_micro_safety_router",
    "validate_config",
    "validate_nestra_plan",
    "validate_project_id",
]
