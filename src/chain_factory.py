from langchain_core.runnables import RunnableLambda, RunnableBranch
from src.agents.classifier import build_classify_chain
from src.agents.price import build_price_chain
from src.agents.tech import build_tech_chain
from src.agents.default import build_default_chain

# ===================== 优化1：全局缓存子链（只初始化一次） =====================
# 缓存：避免重复创建子链，大幅提速
_CACHED_CHAINS = {}

def build_reply_chain(memory, item_desc, model):
    global _CACHED_CHAINS
    # 用模型+商品描述作为缓存key，不变则不重建
    cache_key = (id(model), hash(item_desc))
    
    if cache_key not in _CACHED_CHAINS:
        # 只初始化一次子链
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

    # ===================== 优化2：删除所有print，关闭IO耗时 =====================
    # 清理商品描述注入函数
    def inject_item_desc(x):
        x["item_desc"] = item_desc
        return x

    # 清理分类处理函数
    def classify_and_pass(x):
        # 原生调用分类链，无嵌套阻塞
        x["intent"] = classify_chain.invoke(x)
        return x

    # ===================== 优化3：分支直接用子链，移除手动.invoke() =====================
    branch = RunnableBranch(
        (lambda x: x.get("intent") == "no_reply", RunnableLambda(lambda _: {"intent": "no_reply", "reply": "-"})),
        (lambda x: x.get("intent") == "price", price_chain),  # 直接接子链！核心提速
        (lambda x: x.get("intent") == "tech", tech_chain),    # 直接接子链！
        default_chain                                         # 直接接子链！
    )

    # 原生链式组合，LangChain自动优化调度
    chain = (
        RunnableLambda(inject_item_desc)
        | RunnableLambda(classify_and_pass)
        | branch
    )
    
    return chain