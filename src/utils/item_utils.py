import json, sqlite3, os
from loguru import logger

def format_price(price):
    try:
        return round(float(price) / 100, 2)
    except:
        return 0.0

def build_item_description(item_data: dict) -> str:
    clean_skus = []
    for sku in item_data.get('skuList', []):
        specs = [p['valueText'] for p in sku.get('propertyList', []) if p.get('valueText')]
        spec_text = " ".join(specs) if specs else "默认规格"
        clean_skus.append({
            "spec": spec_text,
            "price": format_price(sku.get('price', 0)),
            "stock": sku.get('quantity', 0)
        })
    valid_prices = [s['price'] for s in clean_skus if s['price'] > 0]
    if valid_prices:
        min_p, max_p = min(valid_prices), max(valid_prices)
        price_disp = f"¥{min_p}" if min_p == max_p else f"¥{min_p} - ¥{max_p}"
    else:
        main_price = round(float(item_data.get('soldPrice', 0)), 2)
        price_disp = f"¥{main_price}"

    summary = {
        "title": item_data.get('title', ''),
        "desc": item_data.get('desc', ''),
        "price_range": price_disp,
        "total_stock": item_data.get('quantity', 0),
        "sku_details": clean_skus
    }
    return json.dumps(summary, ensure_ascii=False)

def init_db(db_path: str):
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # 开启 WAL 模式，提升并发性能
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bargain_counts (
            chat_id TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"数据库初始化完成: {db_path}")

def get_item_desc(item_id: str, api, db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT data FROM items WHERE item_id=?", (item_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return build_item_description(json.loads(row[0]))
    result = api.get_item_info(item_id)
    if 'data' in result and 'itemDO' in result['data']:
        item_data = result['data']['itemDO']
        conn.execute("INSERT OR REPLACE INTO items(item_id,data) VALUES (?,?)",
                     (item_id, json.dumps(item_data, ensure_ascii=False)))
        conn.commit()
        conn.close()
        return build_item_description(item_data)
    else:
        conn.close()
        logger.warning(f"获取商品 {item_id} 信息失败")
        return "商品信息获取失败"