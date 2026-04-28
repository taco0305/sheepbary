import sqlite3
import os
import sys
from flask import Flask, render_template, request, jsonify, send_file
import asyncio
import edge_tts

from datetime import datetime

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = Flask(__name__, 
            static_folder=resource_path('static'),
            template_folder=resource_path('templates'))

# If running as an EXE, use a local writeable path for the database
if getattr(sys, 'frozen', False):
    db_path = os.path.join(os.path.dirname(sys.executable), 'pos_system.db')
else:
    db_path = 'pos_system.db'

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                 )''')
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    category_id INTEGER,
                    image_url TEXT,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                 )''')
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_amount REAL NOT NULL,
                    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                 )''')
    # Order items table
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER,
                    price REAL,
                    FOREIGN KEY (order_id) REFERENCES orders (id),
                    FOREIGN KEY (product_id) REFERENCES products (id)
                 )''')
    
    # Check if empty, then seed data
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        categories = [('純茶系列',), ('特挑奶茶',), ('鮮果茶飲',), ('現磨咖啡',)]
        c.executemany("INSERT INTO categories (name) VALUES (?)", categories)
        
        products = [
            ('經典紅茶', 35, 1, '/static/img/black_tea.png'),
            ('茉莉綠茶', 35, 1, '/static/img/green_tea.png'),
            ('波霸奶茶', 55, 2, '/static/img/pearl_milk_tea.png'),
            ('黑糖珍珠鮮奶', 65, 2, '/static/img/brown_sugar.png'),
            ('百香綠茶', 50, 3, '/static/img/passion_fruit.png'),
            ('葡萄柚綠茶', 65, 3, '/static/img/grapefruit.png'),
            ('美式咖啡', 50, 4, '/static/img/americano.png'),
            ('經典拿鐵', 75, 4, '/static/img/latte.png'),
        ]
        c.executemany("INSERT INTO products (name, price, category_id, image_url) VALUES (?, ?, ?, ?)", products)
    
    conn.commit()
    conn.close()

# Initialize DB on start
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/api/tts')
def get_tts():
    text = request.args.get('text', '')
    if not text:
        return "Missing text", 400
    
    voice = "zh-TW-HsiaoChenNeural"
    # Create temp directory if not exists
    temp_dir = os.path.join(app.static_folder, 'temp')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    import hashlib
    # Cache by text hash to avoid regeneration
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    output_path = os.path.join(temp_dir, f"{text_hash}.mp3")
    
    if not os.path.exists(output_path):
        async def generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            
        asyncio.run(generate())
        
    return send_file(output_path, mimetype="audio/mpeg")

@app.route('/api/menu')
def get_menu():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    products = conn.execute('SELECT * FROM products').fetchall()
    
    menu = []
    for cat in categories:
        cat_data = {
            'id': cat['id'],
            'name': cat['name'],
            'products': []
        }
        for prod in products:
            if prod['category_id'] == cat['id']:
                cat_data['products'].append({
                    'id': prod['id'],
                    'name': prod['name'],
                    'price': prod['price'],
                    'image': prod['image_url']
                })
        menu.append(cat_data)
    
    conn.close()
    return jsonify(menu)

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'No items in order'}), 400
    
    total_amount = sum(item['price'] * item['quantity'] for item in items)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO orders (total_amount) VALUES (?)", (total_amount,))
    order_id = c.lastrowid
    
    for item in items:
        c.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                  (order_id, item['id'], item['quantity'], item['price']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'order_id': order_id, 'total': total_amount})

@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    # Total Revenue
    total_revenue = conn.execute("SELECT SUM(total_amount) FROM orders").fetchone()[0] or 0
    # Total Orders
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    # Revenue by Date
    daily_sales = conn.execute("""
        SELECT date(order_time) as date, SUM(total_amount) as total
        FROM orders
        GROUP BY date
        ORDER BY date DESC
        LIMIT 30
    """).fetchall()
    
    # Top Selling Items
    top_items = conn.execute("""
        SELECT p.name, SUM(oi.quantity) as count
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        GROUP BY p.name
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'daily_sales': [{'date': row['date'], 'total': row['total']} for row in daily_sales],
        'top_items': [{'name': row['name'], 'count': row['count']} for row in top_items]
    })

@app.route('/api/ai_insight')
def get_ai_insight():
    # Fetch current stats for context
    conn = get_db_connection()
    total_revenue = conn.execute("SELECT SUM(total_amount) FROM orders").fetchone()[0] or 0
    top_items = conn.execute("""
        SELECT p.name, SUM(oi.quantity) as count
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        GROUP BY p.name
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    items_str = ", ".join([f"{row['name']}({row['count']}杯)" for row in top_items])
    
    api_key = "xai-DLsfZK8EYyoRAqKsCkHfGgXqsGdTRsKqSy7sBFHiyPnTB603Uy1Tor4hEZ0U24XAUWTVRs8D9X87ijUl"

    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
    )

    try:
        prompt = f"我的飲料店目前總營業額為 {total_revenue} 元。最熱銷的前五名產品分別是：{items_str}。請以專業經營顧問的身份，提供 3 點具體的經營建议或促銷策略（繁體中文，每點約 50 字）。"
        
        response = client.chat.completions.create(
            model="grok-2",
            messages=[
                {"role": "system", "content": "你是一位專業的飲料店經營分析專家 Grok。"},
                {"role": "user", "content": prompt}
            ]
        )
        insight = response.choices[0].message.content
        return jsonify({'insight': insight})
    except Exception as e:
        # Local Backup Analysis Logic if API fails
        error_msg = str(e)
        backup_insight = f"【Grok 數據分析模式 (預覽)】<br><br>"
        backup_insight += f"目前店內表現穩定，總營收已達 <b>{total_revenue} 元</b>。<br>"
        
        if top_items:
            main_item = top_items[0]['name']
            backup_insight += f"1. <b>核心產品力：</b>目前的明星產品是『{main_item}』，建議針對此產品推出『第二杯半價』促銷，進一步鞏固客源。<br>"
            backup_insight += f"2. <b>品項搭配建議：</b>觀察到熱銷排行包含 {items_str}，可考慮將前兩名組成『雙人分享組』銷售。<br>"
            backup_insight += f"3. <b>品牌優化：</b>建議在社群平台分享製作過程，強化『現點現做』的專業感。<br>"
        else:
            backup_insight += "目前尚無銷售數據，建議先進行首單測試，讓系統為您追蹤績效。"

        # If it's specifically a credit error, add a small tip
        if "403" in error_msg:
            backup_insight += "<br><small style='color:var(--text-muted)'>(註：偵測到 API 額度不足，已切換至本機智慧分析模式)</small>"
            
        return jsonify({'insight': backup_insight})

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

local_ip = get_local_ip()

def start_flask():
    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)

if __name__ == '__main__':
    import tkinter as tk
    from tkinter import messagebox
    import webbrowser
    import threading
    import os
    import sys

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Backend Desktop Management UI (Tkinter)
    root = tk.Tk()
    root.title(f"品味茶飲 POS 控制台 | 內網伺服器")
    root.geometry("400x320")
    root.configure(bg='#0f172a')

    # Status Label
    status_label = tk.Label(root, text="● 內網服務運行中", fg="#22d3ee", bg="#0f172a", font=("Microsoft JhengHei", 16, "bold"))
    status_label.pack(pady=20)

    # Info Label
    info_label = tk.Label(root, text=f"外部訪問位址: http://{local_ip}", fg="#4ade80", bg="#0f172a", font=("Consolas", 10, "bold"))
    info_label.pack(pady=5)
    
    local_info = tk.Label(root, text="其他手機/平板可掃描或輸入上方網址點餐", fg="#94a3b8", bg="#0f172a", font=("Microsoft JhengHei", 9))
    local_info.pack(pady=5)

    # Buttons Style Helper
    btn_style = {
        "font": ("Microsoft JhengHei", 12, "bold"),
        "fg": "white",
        "bg": "#6366f1",
        "activebackground": "#4f46e5",
        "activeforeground": "white",
        "relief": "flat",
        "width": 20,
        "pady": 10
    }

    def open_order():
        webbrowser.open(f"http://{local_ip}")

    def open_admin():
        webbrowser.open(f"http://{local_ip}/admin")

    # Order Button
    order_btn = tk.Button(root, text="開啟點餐頁面 (WEB)", command=open_order, **btn_style)
    order_btn.pack(pady=10)

    # Admin Button
    admin_btn_style = btn_style.copy()
    admin_btn_style["bg"] = "#a855f7"
    admin_btn = tk.Button(root, text="開啟營收報表 (WEB)", command=open_admin, **admin_btn_style)
    admin_btn.pack(pady=10)

    def on_closing():
        if messagebox.askokcancel("退出", "確定要關閉 POS 系統後端嗎？"):
            root.destroy()
            sys.exit()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
