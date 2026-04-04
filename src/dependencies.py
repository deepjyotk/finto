"""Dependency injection providers - thin wiring layer only"""

from typing import Annotated

from fastapi import Depends
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import SessionLocal, get_session
from src.core.enums import LLMModel, ThesysModel
from src.core.llm import LLMFactory
from src.core.settings import llm_settings, sendgrid_settings, settings
from src.graph import Graph
from src.nodes.final_response_generation import FinalResponseGenerationNode
from src.nodes.financial_analysis_tool_node import PortfolioNode
from src.nodes.orchestrator import OrchestratorNode
from src.nodes.web_search import WebSearchNode
from src.repositories.broker_repo import BrokerRepository
from src.repositories.chat_repo import ChatRepository
from src.repositories.holdings_repo import HoldingsRepository
from src.repositories.pending_registration_repo import PendingRegistrationRepository
from src.repositories.user_repo import UserRepository
from src.repositories.whatsapp_repo import WhatsAppRepository
from src.services.a2ui_chat_service import A2UIChatService
from src.services.auth import AuthService
from src.services.broker import BrokerService
from src.services.chat import ChatService
from src.services.chat_thesys_service import ThesysChatService
from src.services.email import EmailService
from src.services.holdings import HoldingsService
from src.services.whatsapp import WhatsAppService


def get_llm_factory() -> LLMFactory:
    """Provide a factory that builds chat model clients from an LLMModel enum."""

    def factory(model: LLMModel | ThesysModel) -> BaseChatModel:
        if isinstance(model, LLMModel):
            resolved = model.resolve_to_openai_member()
            if resolved.provider == "anthropic":
                return ChatAnthropic(model=resolved.model_name, **resolved.llm_kwargs)
            if resolved.provider == "google":
                return ChatGoogleGenerativeAI(model=resolved.model_name, **resolved.llm_kwargs)
            return ChatOpenAI(
                model=resolved.model_name,
                api_key=llm_settings.openai_api_key,
                **resolved.llm_kwargs,
            )
        return ChatOpenAI(model=model.value, api_key=llm_settings.openai_api_key)

    return factory


def _get_holdings_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HoldingsRepository:
    """Provide HoldingsRepository with its own session scope."""
    return HoldingsRepository(session)


# def _get_holdings_service(
#     repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
# ) -> HoldingsService:
#     """Provide HoldingsService with its own session scope."""
#     return HoldingsService(repo=repo)


def get_holdings_service(
    repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
) -> HoldingsService:
    """Provide HoldingsService with its own session scope."""
    return HoldingsService(repo=repo)


def _get_web_search_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> WebSearchNode:
    """Provide WebSearchNode with injected LLM factory."""
    return WebSearchNode(llm_factory=llm_factory)


def _get_portfolio_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
    holdings_service: Annotated[HoldingsService, Depends(get_holdings_service)],
) -> PortfolioNode:
    """Provide PortfolioNode with injected LLM factory and holdings service."""
    return PortfolioNode(llm_factory=llm_factory, holding_service=holdings_service)


def _get_orchestrator_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
    portfolio_node: Annotated[PortfolioNode, Depends(_get_portfolio_node)],
    web_search_node: Annotated[WebSearchNode, Depends(_get_web_search_node)],
) -> OrchestratorNode:
    """Provide OrchestratorNode with injected LLM factory and worker nodes."""
    return OrchestratorNode(
        llm_factory=llm_factory,
        portfolio_node=portfolio_node,
        web_search_node=web_search_node,
    )


def _get_final_response_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> FinalResponseGenerationNode:
    """Provide FinalResponseGenerationNode with injected LLM factory."""
    return FinalResponseGenerationNode(llm_factory=llm_factory)


def build_agent_graph(session: AsyncSession | None = None) -> Graph:
    """
    Build a Graph instance without FastAPI's dependency injection.

    Args:
        session: Optional AsyncSession to reuse; if omitted a new SessionLocal is created.

    Returns:
        Configured Graph ready for execution.
    """
    llm_factory = get_llm_factory()

    web_search_node = WebSearchNode(llm_factory=llm_factory)
    final_response_node = FinalResponseGenerationNode(llm_factory=llm_factory)

    session_to_use = session or SessionLocal()
    holdings_repo = HoldingsRepository(session_to_use)
    holdings_service = HoldingsService(repo=holdings_repo)
    portfolio_node = PortfolioNode(llm_factory=llm_factory, holding_service=holdings_service)

    orchestrator_node = OrchestratorNode(
        llm_factory=llm_factory,
        portfolio_node=portfolio_node,
        web_search_node=web_search_node,
    )

    return Graph(
        orchestrator_node=orchestrator_node,
        final_response_node=final_response_node,
    )


def get_graph(
    final_response_node: Annotated[FinalResponseGenerationNode, Depends(_get_final_response_node)],
    orchestrator_node: Annotated[OrchestratorNode, Depends(_get_orchestrator_node)],
) -> Graph:
    """Provide Graph instance with all node dependencies injected."""
    return Graph(
        orchestrator_node=orchestrator_node,
        final_response_node=final_response_node,
    )


def _get_auth_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    """
    Provide UserRepository instance.

    Returns:
        Configured UserRepository instance
    """
    return UserRepository(session)


def _get_pending_registration_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PendingRegistrationRepository:
    """
    Provide PendingRegistrationRepository instance.

    Returns:
        Configured PendingRegistrationRepository instance
    """
    return PendingRegistrationRepository(session)


def get_email_service() -> EmailService:
    """
    Provide EmailService instance.

    Returns:
        Configured EmailService instance (may be disabled if SendGrid not configured)
    """
    return EmailService(
        api_key=sendgrid_settings.api_key,
        from_email=sendgrid_settings.from_email,
        from_name=sendgrid_settings.from_name,
    )


def get_auth_service(
    repo: Annotated[UserRepository, Depends(_get_auth_repository)],
    pending_repo: Annotated[
        PendingRegistrationRepository, Depends(_get_pending_registration_repository)
    ],
    email_service: Annotated[EmailService, Depends(get_email_service)],
) -> AuthService:
    """
    Provide AuthService with its dependencies.

    This is the only place where we wire together:
    Session → Repository → Service

    Args:
        repo: UserRepository from _get_auth_repository dependency
        pending_repo: PendingRegistrationRepository from _get_pending_registration_repository
        email_service: EmailService for sending OTP emails

    Returns:
        Configured AuthService instance
    """
    return AuthService(
        repo=repo,
        pending_repo=pending_repo,
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        email_service=email_service,
    )


def _get_holdings_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HoldingsRepository:
    """
    Provide HoldingsRepository instance.

    Returns:
        Configured HoldingsRepository instance
    """
    return HoldingsRepository(session)


def get_holdings_service(
    repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
) -> HoldingsService:
    """
    Provide HoldingsService with its dependencies.

    This wires together:
    Session → Repository → Service

    Args:
        repo: HoldingsRepository from _get_holdings_repository dependency

    Returns:
        Configured HoldingsService instance
    """
    return HoldingsService(repo=repo)


def get_chat_service(graph: Annotated[Graph, Depends(get_graph)]) -> ChatService:
    """
    Provide ChatService instance.
    Returns:
        Configured ChatService instance
    """
    return ChatService(graph=graph)


def _get_chat_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatRepository:
    """
    Provide ChatRepository instance.

    Returns:
        Configured ChatRepository instance
    """
    return ChatRepository(session)


def get_thesys_chat_service(
    graph: Annotated[Graph, Depends(get_graph)],
    chat_repo: Annotated[ChatRepository, Depends(_get_chat_repository)],
) -> ThesysChatService:
    """
    Provide ThesysChatService instance.
    Returns:
        Configured ThesysChatService instance
    """
    return ThesysChatService(graph=graph, chat_repo=chat_repo)


def get_a2ui_chat_service(
    graph: Annotated[Graph, Depends(get_graph)],
    chat_repo: Annotated[ChatRepository, Depends(_get_chat_repository)],
) -> A2UIChatService:
    """
    Provide A2UIChatService instance.
    Returns:
        Configured A2UIChatService instance
    """
    return A2UIChatService(graph=graph, chat_repo=chat_repo)


def _get_broker_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BrokerRepository:
    """
    Provide BrokerRepository instance.

    Returns:
        Configured BrokerRepository instance
    """
    return BrokerRepository(session)


def get_broker_service(
    repo: Annotated[BrokerRepository, Depends(_get_broker_repository)],
) -> BrokerService:
    """
    Provide BrokerService with its dependencies.

    This wires together:
    Session → Repository → Service

    Args:
        repo: BrokerRepository from _get_broker_repository dependency

    Returns:
        Configured BrokerService instance
    """
    return BrokerService(repo=repo)


def _get_whatsapp_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WhatsAppRepository:
    """
    Provide WhatsAppRepository instance.

    Returns:
        Configured WhatsAppRepository instance
    """
    return WhatsAppRepository(session)


def get_whatsapp_service(
    repo: Annotated[WhatsAppRepository, Depends(_get_whatsapp_repository)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> WhatsAppService:
    """
    Provide WhatsAppService with its dependencies.

    This wires together:
    Session → Repository → Service

    Args:
        repo: WhatsAppRepository from _get_whatsapp_repository dependency

    Returns:
        Configured WhatsAppService instance
    """
    return WhatsAppService(repo=repo, chat_service=chat_service)
