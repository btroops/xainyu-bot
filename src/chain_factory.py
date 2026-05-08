from langchain_core.runnables import RunnableLambda, RunnableBranch
from src.agents.classifier import build_classify_chain
from src.agents.price import build_price_chain
from src.agents.tech import build_tech_chain
from src.agents.default import build_default_chain

_CACHED_CHAINS = {}

def build_reply_chain(memory, item_desc, model):
    global _CACHED_CHAINS
    cache_key = (id(model), hash(item_desc))

    if cache_key not in _CACHED_CHAINS:
        _CACHED_CHAINS[cache_key] = {
            "classify": build_classify_chain(model),
            "price": build_price_chain(memory, item_desc, model),
            "tech": build_tech_chain(memory, item_desc, model),
            "default": build_default_chain(memory, item_desc, model)
        }

    chains = _CACHED_CHAINS[cache_key]
    classify_chain = chains["classify"]
    price_chain = chains["price"]
    tech_chain = chains["tech"]
    default_chain = chains["default"]

    def inject_item_desc(x):
        x["item_desc"] = item_desc
        return x

    async def classify_and_pass(x):
        x["intent"] = await classify_chain.ainvoke(x)
        return x

    branch = RunnableBranch(
        (lambda x: x.get("intent") == "no_reply", RunnableLambda(lambda _: {"intent": "no_reply", "reply": "-"})),
        (lambda x: x.get("intent") == "price", price_chain),
        (lambda x: x.get("intent") == "tech", tech_chain),
        default_chain
    )

    chain = (
        RunnableLambda(inject_item_desc)
        | RunnableLambda(classify_and_pass)
        | branch
    )
    return chain