"""LLM provider factory for the analytics agent framework.

Swapping LLM providers requires only changing the ``LLM_PROVIDER`` and
``LLM_MODEL_NAME`` environment variables — no code changes are needed.
To add a new provider, install the corresponding ``langchain_*`` integration
package and add a branch to ``create_llm_provider``.
"""

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig


def create_llm_provider(config: AnalyticsConfig) -> BaseChatModel:
    """Return a configured LLM provider as a ``BaseChatModel``.

    Reads ``config.llm_provider`` and ``config.llm_model_name`` to select and
    instantiate the appropriate LangChain chat model.  All nodes receive the
    returned object via dependency injection and never instantiate a concrete
    LLM class directly.

    Args:
        config: The analytics agent configuration containing provider selection
            and model name.

    Returns:
        A ``BaseChatModel`` instance ready for invocation.

    Raises:
        ValueError: If ``config.llm_provider`` is not a recognised provider name.

    Example:
        config = AnalyticsConfig()
        llm = create_llm_provider(config)
        response = await llm.ainvoke("Hello")
    """
    provider_name = config.llm_provider.lower()

    if provider_name == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm_model_name,
            temperature=0,
            api_key=config.openai_api_key,  # type: ignore[arg-type]
        )

    if provider_name == "anthropic":
        from langchain_anthropic import ChatAnthropic  # type: ignore[import-not-found]

        return ChatAnthropic(model=config.llm_model_name, temperature=0)  # type: ignore[call-arg]

    raise ValueError(
        f"Unrecognised LLM provider: '{config.llm_provider}'. "
        "Supported providers: 'openai', 'anthropic'. "
        "Install the corresponding langchain_* package and add a branch to create_llm_provider()."
    )
