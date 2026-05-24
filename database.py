import sqlite3

DB_NAME = 'recipes.db'

def init_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    ingredients TEXT NOT NULL,
                    instructions TEXT NOT NULL
                )
            ''')
            conn.commit()
            print("База данных успешно инициализирована")
    except Exception as e:
        print(f"Ошибка при инициализации БД: {e}")

def add_recipe(title, ingredients, instructions):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO recipes (title, ingredients, instructions)
                VALUES (?, ?, ?)
            ''', (title, ingredients, instructions))
            conn.commit()
            print(f"Рецепт '{title}' добавлен")
    except Exception as e:
        print(f"Ошибка при добавлении рецепта: {e}")

def get_all_recipes():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, title FROM recipes ORDER BY id DESC')
            return cursor.fetchall()
    except Exception as e:
        print(f"Ошибка при получении рецептов: {e}")
        return []

def get_recipe(recipe_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, title, ingredients, instructions FROM recipes WHERE id = ?', (recipe_id,))
            row = cursor.fetchone()
            if row:
                return {'id': row[0], 'title': row[1], 'ingredients': row[2], 'instructions': row[3]}
            return None
    except Exception as e:
        print(f"Ошибка при получении рецепта {recipe_id}: {e}")
        return None

def delete_recipe(recipe_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
            conn.commit()
            print(f"Рецепт с ID {recipe_id} удален")
    except Exception as e:
        print(f"Ошибка при удалении рецепта {recipe_id}: {e}")