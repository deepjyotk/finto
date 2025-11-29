"""Dependency injection providers - thin wiring layer only"""

from typing import Annotated, AsyncIterator, Callable

from fastapi import Depends
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import SessionLocal, get_session
from src.core.enums import LLMModel
from src.core.settings import settings
from src.graph import Graph
from src.nodes.code_generation import CodeGenerationNode
from src.nodes.execute_code import ExecuteCodeNode
from src.nodes.final_response_generation import FinalResponseGenerationNode
from src.nodes.portfolio import PortfolioNode
from src.nodes.router import RouterNode
from src.nodes.web_search import WebSearchNode
from src.repositories.broker_repo import BrokerRepository
from src.repositories.holdings_repo import HoldingsRepository
from src.repositories.user_repo import UserRepository
from src.repositories.whatsapp_repo import WhatsAppRepository
from src.services.auth import AuthService
from src.services.broker import BrokerService
from src.services.chat import ChatService
from src.services.holdings import HoldingsService
from src.services.whatsapp import WhatsAppService

LLMFactory = Callable[[LLMModel], ChatOpenAI]
HoldingsServiceDependency = Callable[[], AsyncIterator[HoldingsService]]


def get_llm_factory() -> LLMFactory:
    """Provide a factory that builds ChatOpenAI clients from an LLMModel enum."""
    return lambda model: ChatOpenAI(model=model.model_name, **model.llm_kwargs)


def _get_holdings_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HoldingsRepository:
    """Provide HoldingsRepository with its own session scope."""
    return HoldingsRepository(session)


def _get_holdings_service(
    repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
) -> HoldingsService:
    """Provide HoldingsService with its own session scope."""
    return HoldingsService(repo=repo)


def get_holdings_service(
    repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
) -> HoldingsService:
    """Provide HoldingsService with its own session scope."""
    return HoldingsService(repo=repo)


def _get_router_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> RouterNode:
    """Provide RouterNode with injected LLM factory."""
    return RouterNode(llm_factory=llm_factory)


def _get_news_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> WebSearchNode:
    """Provide WebSearchNode with injected LLM factory."""
    return WebSearchNode(llm_factory=llm_factory)


def _get_portfolio_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> PortfolioNode:
    """Provide PortfolioNode with injected LLM factory."""
    return PortfolioNode(llm_factory=llm_factory)


def _get_code_generation_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> CodeGenerationNode:
    """Provide CodeGenerationNode with injected LLM factory."""
    return CodeGenerationNode(llm_factory=llm_factory)


def _get_final_response_node(
    llm_factory: Annotated[LLMFactory, Depends(get_llm_factory)],
) -> FinalResponseGenerationNode:
    """Provide FinalResponseGenerationNode with injected LLM factory."""
    return FinalResponseGenerationNode(llm_factory=llm_factory)


def _get_execute_code_node(
    holdings_service: Annotated[HoldingsService, Depends(_get_holdings_service)],
) -> ExecuteCodeNode:
    """Provide ExecuteCodeNode with injected holdings service."""
    return ExecuteCodeNode(holding_service=holdings_service)


def build_agent_graph(session: AsyncSession | None = None) -> Graph:
    """
    Build a Graph instance without FastAPI's dependency injection.

    Args:
        session: Optional AsyncSession to reuse; if omitted a new SessionLocal is created.

    Returns:
        Configured Graph ready for execution.
    """
    llm_factory = get_llm_factory()

    news_node = WebSearchNode(llm_factory=llm_factory)
    portfolio_node = PortfolioNode(llm_factory=llm_factory)
    code_generation_node = CodeGenerationNode(llm_factory=llm_factory)
    final_response_node = FinalResponseGenerationNode(llm_factory=llm_factory)

    session_to_use = session or SessionLocal()
    holdings_repo = HoldingsRepository(session_to_use)
    holdings_service = HoldingsService(repo=holdings_repo)
    execute_code_node = ExecuteCodeNode(holding_service=holdings_service)

    router_node = RouterNode(llm_factory=llm_factory)

    return Graph(
        news_node_instance=news_node,
        portfolio_node=portfolio_node,
        code_generation_node=code_generation_node,
        final_response_node=final_response_node,
        execute_code_node=execute_code_node,
        router_node=router_node,
    )


def get_graph(
    news_node: Annotated[WebSearchNode, Depends(_get_news_node)],
    portfolio_node: Annotated[PortfolioNode, Depends(_get_portfolio_node)],
    code_generation_node: Annotated[CodeGenerationNode, Depends(_get_code_generation_node)],
    final_response_node: Annotated[FinalResponseGenerationNode, Depends(_get_final_response_node)],
    execute_code_node: Annotated[ExecuteCodeNode, Depends(_get_execute_code_node)],
    router_node: Annotated[RouterNode, Depends(_get_router_node)],
) -> Graph:
    """Provide Graph instance with all node dependencies injected."""
    return Graph(
        news_node_instance=news_node,
        portfolio_node=portfolio_node,
        code_generation_node=code_generation_node,
        final_response_node=final_response_node,
        execute_code_node=execute_code_node,
        router_node=router_node,
    )


def _get_auth_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> UserRepository:
    """
    Provide UserRepository instance.

    Returns:
        Configured UserRepository instance
    """
    return UserRepository(session)


def get_auth_service(
    repo: Annotated[UserRepository, Depends(_get_auth_repository)],
) -> AuthService:
    """
    Provide AuthService with its dependencies.

    This is the only place where we wire together:
    Session → Repository → Service

    Args:
        session: Database session from get_session dependency

    Returns:
        Configured AuthService instance
    """
    return AuthService(repo=repo, secret_key=settings.secret_key, algorithm=settings.algorithm)


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
