from flask import Flask, request, redirect, render_template_string
import sqlite3
import os
import psycopg2
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)

# === НАСТРОЙКА БАЗЫ ДАННЫХ (автоматически выбирает PostgreSQL на хостинге или SQLite локально) ===

def get_db_connection():
    """Возвращает соединение с базой данных — PostgreSQL на сервере, SQLite на компьютере"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and database_url.startswith('postgresql'):
        # Режим PostgreSQL (на Render)
        return psycopg2.connect(database_url, sslmode='require')
    else:
        # Режим SQLite (на вашем компьютере)
        return sqlite3.connect('recipes.db')

def init_db():
    """Создаёт таблицы, если их нет"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        # PostgreSQL синтаксис
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                comment TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite синтаксис
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                author TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                comment TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE
            )
        ''')
    
    conn.commit()
    conn.close()
    print("База данных готова!")

def save_recipe(title, ingredients, instructions):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('''
            INSERT INTO recipes (title, ingredients, instructions)
            VALUES (%s, %s, %s) RETURNING id
        ''', (title, ingredients, instructions))
        recipe_id = cursor.fetchone()[0]
    else:
        cursor.execute('''
            INSERT INTO recipes (title, ingredients, instructions)
            VALUES (?, ?, ?)
        ''', (title, ingredients, instructions))
        recipe_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return recipe_id

def get_all_recipes():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('''
            SELECT r.id, r.title, 
                   COUNT(rev.id) as reviews_count,
                   COALESCE(AVG(rev.rating), 0) as avg_rating
            FROM recipes r
            LEFT JOIN reviews rev ON r.id = rev.recipe_id
            GROUP BY r.id
            ORDER BY r.id DESC
        ''')
    else:
        cursor.execute('''
            SELECT r.id, r.title, 
                   COUNT(rev.id) as reviews_count,
                   COALESCE(AVG(rev.rating), 0) as avg_rating
            FROM recipes r
            LEFT JOIN reviews rev ON r.id = rev.recipe_id
            GROUP BY r.id
            ORDER BY r.id DESC
        ''')
    
    recipes = cursor.fetchall()
    conn.close()
    return recipes

def get_recipe(recipe_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('SELECT id, title, ingredients, instructions FROM recipes WHERE id = %s', (recipe_id,))
    else:
        cursor.execute('SELECT id, title, ingredients, instructions FROM recipes WHERE id = ?', (recipe_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {'id': row[0], 'title': row[1], 'ingredients': row[2], 'instructions': row[3]}
    return None

def get_reviews(recipe_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('''
            SELECT id, author, rating, comment, created_at 
            FROM reviews 
            WHERE recipe_id = %s 
            ORDER BY created_at DESC
        ''', (recipe_id,))
    else:
        cursor.execute('''
            SELECT id, author, rating, comment, created_at 
            FROM reviews 
            WHERE recipe_id = ? 
            ORDER BY created_at DESC
        ''', (recipe_id,))
    
    reviews = cursor.fetchall()
    conn.close()
    return reviews

def add_review(recipe_id, author, rating, comment):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('''
            INSERT INTO reviews (recipe_id, author, rating, comment)
            VALUES (%s, %s, %s, %s)
        ''', (recipe_id, author, rating, comment))
    else:
        cursor.execute('''
            INSERT INTO reviews (recipe_id, author, rating, comment)
            VALUES (?, ?, ?, ?)
        ''', (recipe_id, author, rating, comment))
    
    conn.commit()
    conn.close()

def delete_recipe_by_id(recipe_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('DELETE FROM recipes WHERE id = %s', (recipe_id,))
    else:
        cursor.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
    
    conn.commit()
    conn.close()

def delete_review(review_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if isinstance(conn, psycopg2.extensions.connection):
        cursor.execute('DELETE FROM reviews WHERE id = %s', (review_id,))
    else:
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
    
    conn.commit()
    conn.close()

# === HTML ШАБЛОНЫ (красивое оформление) ===

BASE_HEADER = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>%TITLE% - Кулинарная книга</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍳</text></svg>">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .main-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            animation: fadeIn 0.5s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .nav {
            background: #f8f9fa;
            padding: 15px 30px;
            border-bottom: 1px solid #e0e0e0;
        }
        .nav a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            margin-right: 20px;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s;
        }
        .nav a:hover { background: #667eea; color: white; }
        .content { padding: 30px; }
        .recipes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .recipe-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .recipe-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }
        .recipe-card h3 { color: #333; margin-bottom: 10px; font-size: 1.3em; }
        .rating {
            color: #ffc107;
            margin: 10px 0;
            font-size: 1.1em;
        }
        .reviews-count { color: #666; font-size: 0.9em; margin-left: 10px; }
        .recipe-card .recipe-actions { margin-top: 15px; }
        .recipe-card a { color: #667eea; text-decoration: none; margin-right: 15px; }
        .recipe-card .delete-link { color: #dc3545; }
        .detail-section {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .detail-section h3 { color: #667eea; margin-bottom: 15px; }
        .detail-section pre { white-space: pre-wrap; font-family: inherit; line-height: 1.6; }
        .review {
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .review-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        .review-author { font-weight: bold; color: #333; }
        .review-date { color: #999; font-size: 0.85em; }
        .review-rating { color: #ffc107; font-size: 1.1em; }
        .review-comment { color: #555; line-height: 1.5; margin-top: 10px; }
        .delete-review { color: #dc3545; font-size: 0.85em; text-decoration: none; margin-left: 10px; }
        .add-review {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .add-review h4 { margin-bottom: 15px; color: #333; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 600; color: #333; }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: inherit;
        }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 25px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
        }
        button:hover { transform: scale(1.05); }
        .empty-state { text-align: center; padding: 50px; color: #999; }
        .empty-state p { font-size: 1.2em; margin-bottom: 20px; }
        .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
        .star-rating { display: inline-block; color: #ffc107; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-card">
            <div class="header">
                <h1>🍳 Кулинарная книга</h1>
                <p>Храните свои любимые рецепты в одном месте</p>
            </div>
            <div class="nav">
                <a href="/">🏠 Главная</a>
                <a href="/add">➕ Добавить рецепт</a>
            </div>
            <div class="content">
'''

BASE_FOOTER = '''
            </div>
        </div>
    </div>
</body>
</html>
'''

ADD_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Добавить рецепт - Кулинарная книга</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍳</text></svg>">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .form-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            animation: fadeIn 0.5s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2em; }
        .content { padding: 30px; }
        .form-group { margin-bottom: 25px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
        }
        .form-group input:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover { transform: scale(1.05); }
        .cancel-link { color: #6c757d; text-decoration: none; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <div class="form-card">
            <div class="header">
                <h1>➕ Добавить новый рецепт</h1>
            </div>
            <div class="content">
                <form method="POST">
                    <div class="form-group">
                        <label>🍽️ Название блюда:</label>
                        <input type="text" name="title" required placeholder="Например: Борщ, Панкейки...">
                    </div>
                    <div class="form-group">
                        <label>📝 Ингредиенты:</label>
                        <textarea name="ingredients" rows="5" required placeholder="Пример:&#10;2 яйца&#10;1 стакан муки"></textarea>
                    </div>
                    <div class="form-group">
                        <label>👨‍🍳 Приготовление:</label>
                        <textarea name="instructions" rows="8" required placeholder="Пошаговый рецепт..."></textarea>
                    </div>
                    <button type="submit">💾 Сохранить рецепт</button>
                    <a href="/" class="cancel-link">❌ Отмена</a>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
'''

# === МАРШРУТЫ FLASK ===

@app.route('/')
def index():
    recipes = get_all_recipes()
    
    if recipes:
        recipes_html = '<div class="recipes-grid">'
        for recipe in recipes:
            recipe_id, title, reviews_count, avg_rating = recipe
            stars = '★' * round(avg_rating) + '☆' * (5 - round(avg_rating))
            recipes_html += f'''
            <div class="recipe-card">
                <h3>{title}</h3>
                <div class="rating">
                    <span class="star-rating">{stars}</span>
                    <span class="reviews-count">({reviews_count} отзывов)</span>
                </div>
                <div class="recipe-actions">
                    <a href="/recipe/{recipe_id}">🔍 Смотреть рецепт</a>
                    <a href="/delete/{recipe_id}" class="delete-link" onclick="return confirm('Удалить рецепт и все отзывы?')">🗑️ Удалить</a>
                </div>
            </div>
            '''
        recipes_html += '</div>'
    else:
        recipes_html = '''
        <div class="empty-state">
            <p>😕 Пока нет рецептов</p>
            <a href="/add">➕ Добавить первый рецепт</a>
        </div>
        '''
    
    return BASE_HEADER.replace('%TITLE%', 'Главная') + recipes_html + BASE_FOOTER

@app.route('/add', methods=['GET', 'POST'])
def add_recipe_page():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        ingredients = request.form.get('ingredients', '').strip()
        instructions = request.form.get('instructions', '').strip()
        
        if title and ingredients and instructions:
            save_recipe(title, ingredients, instructions)
            return redirect('/')
    
    return ADD_PAGE_TEMPLATE

@app.route('/recipe/<int:recipe_id>', methods=['GET', 'POST'])
def recipe_detail(recipe_id):
    recipe = get_recipe(recipe_id)
    
    if not recipe:
        return "Рецепт не найден", 404
    
    if request.method == 'POST' and 'submit_review' in request.form:
        author = request.form.get('author', '').strip()
        rating = int(request.form.get('rating', 3))
        comment = request.form.get('comment', '').strip()
        
        if author and comment:
            add_review(recipe_id, author, rating, comment)
            return redirect(f'/recipe/{recipe_id}')
    
    if request.method == 'GET' and 'delete_review' in request.args:
        review_id = request.args.get('delete_review')
        delete_review(review_id)
        return redirect(f'/recipe/{recipe_id}')
    
    reviews = get_reviews(recipe_id)
    
    if reviews:
        avg_rating = sum(r[2] for r in reviews) / len(reviews)
        stars = '★' * round(avg_rating) + '☆' * (5 - round(avg_rating))
        rating_html = f'<div class="rating" style="margin-bottom: 20px;">⭐ Средний рейтинг: {stars} ({avg_rating:.1f}/5) - {len(reviews)} отзывов</div>'
    else:
        rating_html = '<div class="rating" style="margin-bottom: 20px;">⭐ Пока нет отзывов. Будьте первым!</div>'
    
    reviews_html = '<h3>📝 Отзывы посетителей:</h3>'
    
    if reviews:
        for review in reviews:
            review_id, author, rating, comment, created_at = review
            review_stars = '★' * rating + '☆' * (5 - rating)
            created_date = created_at[:16] if created_at else datetime.now().strftime('%Y-%m-%d %H:%M')
            reviews_html += f'''
            <div class="review">
                <div class="review-header">
                    <div>
                        <span class="review-author">{author}</span>
                        <span class="review-rating"> {review_stars}</span>
                    </div>
                    <div>
                        <span class="review-date">{created_date}</span>
                        <a href="?delete_review={review_id}" class="delete-review" onclick="return confirm('Удалить отзыв?')">🗑️</a>
                    </div>
                </div>
                <div class="review-comment">{comment}</div>
            </div>
            '''
    else:
        reviews_html += '<p style="color: #999; margin: 15px 0;">Пока нет отзывов. Оставьте первый отзыв!</p>'
    
    add_review_form = '''
    <div class="add-review">
        <h4>💬 Оставить отзыв:</h4>
        <form method="POST">
            <div class="form-group">
                <label>Ваше имя:</label>
                <input type="text" name="author" required placeholder="Например: Анна, Дмитрий...">
            </div>
            <div class="form-group">
                <label>Оценка:</label>
                <select name="rating">
                    <option value="5">★★★★★ (5) - Отлично</option>
                    <option value="4">★★★★☆ (4) - Хорошо</option>
                    <option value="3">★★★☆☆ (3) - Средне</option>
                    <option value="2">★★☆☆☆ (2) - Плохо</option>
                    <option value="1">★☆☆☆☆ (1) - Ужасно</option>
                </select>
            </div>
            <div class="form-group">
                <label>Ваш отзыв:</label>
                <textarea name="comment" rows="3" required placeholder="Поделитесь впечатлениями о рецепте..."></textarea>
            </div>
            <button type="submit" name="submit_review">📝 Отправить отзыв</button>
        </form>
    </div>
    '''
    
    detail_html = f'''
    <div class="detail-section">
        <h2>🍽️ {recipe['title']}</h2>
        {rating_html}
    </div>
    <div class="detail-section">
        <h3>📝 Ингредиенты:</h3>
        <pre>{recipe['ingredients']}</pre>
    </div>
    <div class="detail-section">
        <h3>👨‍🍳 Приготовление:</h3>
        <pre>{recipe['instructions']}</pre>
    </div>
    <div class="detail-section">
        {reviews_html}
        {add_review_form}
    </div>
    <div style="margin-top: 20px;">
        <a href="/" class="back-link">← Назад к рецептам</a>
        <a href="/delete/{recipe_id}" class="back-link" style="color: #dc3545; margin-left: 20px;" onclick="return confirm('Удалить рецепт и все отзывы?')">🗑️ Удалить рецепт</a>
    </div>
    '''
    
    return BASE_HEADER.replace('%TITLE%', recipe['title']) + detail_html + BASE_FOOTER

@app.route('/delete/<int:recipe_id>')
def delete_recipe_route(recipe_id):
    delete_recipe_by_id(recipe_id)
    return redirect('/')

# === ЗАПУСК ===
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)