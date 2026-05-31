"""Known trusted providers — curated whitelist for x402 payment endpoints.

These are well-known API providers that agents commonly interact with.
Pre-whitelisted to avoid unnecessary ESCALATE decisions.
"""

# Categorized known providers with their domains
KNOWN_PROVIDERS: dict[str, list[str]] = {
    # ── LLM / Inference ──
    "llm_inference": [
        "openai.com",
        "api.openai.com",
        "platform.openai.com",
        "anthropic.com",
        "api.anthropic.com",
        "openrouter.ai",
        "api.openrouter.ai",
        "groq.com",
        "api.groq.com",
        "api.together.xyz",
        "fireworks.ai",
        "api.fireworks.ai",
        "x.ai",
        "api.x.ai",
        "googleapis.com",
        "generativelanguage.googleapis.com",
        "mistral.ai",
        "api.mistral.ai",
        "cohere.com",
        "api.cohere.com",
        "perplexity.ai",
        "api.perplexity.ai",
        "deepseek.com",
        "api.deepseek.com",
        "bedrock.amazonaws.com",
        "sagemaker.amazonaws.com",
    ],
    # ── Blockchain / RPC ──
    "blockchain_rpc": [
        "rpc.ankr.com",
        "eth-mainnet.g.alchemy.com",
        "polygon-mainnet.g.alchemy.com",
        "base-mainnet.g.alchemy.com",
        "mainnet.infura.io",
        "rpc.helius.xyz",
        "api.helius.xyz",
        "api.quicknode.com",
        "nd-xxx-xx-xx.p2pify.com",
        "chainstacklabs.com",
        "api.tenderly.co",
    ],
    # ── Developer APIs ──
    "developer_apis": [
        "api.github.com",
        "github.com",
        "api.npmjs.org",
        "registry.npmjs.org",
        "pypi.org",
        "api.pypi.org",
        "huggingface.co",
        "hf.co",
        "api.cloudflare.com",
        "api.vercel.com",
        "api.cloudflare.com",
    ],
    # ── Data / Storage ──
    "data_storage": [
        "api.s3.amazonaws.com",
        "s3.amazonaws.com",
        "storage.googleapis.com",
        "api.pinata.cloud",
        "gateway.pinata.cloud",
        "api.infura.io",
    ],
    # ── x402 / Payment ──
    "x402_protocol": [
        "x402.org",
        "coinbase.com",
        "api.coinbase.com",
        "base.org",
        "basescan.org",
        "explorer.base.org",
    ],
    # ── Search / Tools ──
    "search_tools": [
        "api.tavily.com",
        "api.brave.com",
        "api-explorer.serper.dev",
        "api.firecrawl.dev",
    ],
    # ── Image / Media ──
    "media_generation": [
        "api.replicate.com",
        "fal.run",
        "fal.ai",
        "api.stability.ai",
        "api.dall-e.com",
    ],
}

# Flat set for quick lookup
_all_domains: set[str] = set()
for domains in KNOWN_PROVIDERS.values():
    _all_domains.update(d.lower() for d in domains)


def is_known_provider(domain: str) -> bool:
    """Check if a domain is a known trusted provider."""
    d = domain.lower().strip()
    # Exact match
    if d in _all_domains:
        return True
    # Subdomain match (e.g. "my.openai.com" → matches "openai.com")
    for known in _all_domains:
        if d.endswith("." + known) or d == known:
            return True
    return False


def get_provider_category(domain: str) -> str | None:
    """Return the category of a known provider, or None if unknown."""
    d = domain.lower().strip()
    for category, domains in KNOWN_PROVIDERS.items():
        for known in domains:
            if d == known.lower() or d.endswith("." + known.lower()):
                return category
    return None


def add_custom_provider(domain: str, category: str = "custom") -> None:
    """Add a custom provider to the known list at runtime."""
    KNOWN_PROVIDERS.setdefault(category, []).append(domain.lower())
    _all_domains.add(domain.lower())


def get_all_providers() -> dict[str, list[str]]:
    """Return full categorized provider list."""
    return dict(KNOWN_PROVIDERS)
