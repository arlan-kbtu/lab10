import pygame
import sys
import json
import random
import psycopg2
from psycopg2 import sql
from contextlib import closing
import os
from urllib.parse import urlparse

# Настройки подключения к PostgreSQL
DATABASE_URL = "postgresql://neondb_owner:npg_tiQjpz6AhM0q@ep-winter-unit-a1pzep3v-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# Инициализация pygame
pygame.init()

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (100, 100, 100)

# Константы игры
CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
SCREEN_WIDTH = CELL_SIZE * GRID_WIDTH
SCREEN_HEIGHT = CELL_SIZE * GRID_HEIGHT
PAUSE_KEY = pygame.K_p

# Функции базы данных PostgreSQL
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    current_level INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица результатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    saved_state TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Таблица уровней
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS levels (
                    level INTEGER PRIMARY KEY,
                    speed INTEGER NOT NULL,
                    walls TEXT NOT NULL,
                    description VARCHAR(100)
                )
            ''')
            
            # Стандартные уровни
            cursor.execute('''
                INSERT INTO levels (level, speed, walls, description)
                VALUES 
                    (1, 10, '[]', 'Новичок - без препятствий'),
                    (2, 15, '[[100,100,200,20],[300,300,20,200]]', 'Средний - простые стены'),
                    (3, 20, '[[50,50,20,300],[200,100,300,20],[150,250,200,20]]', 'Эксперт - сложный лабиринт')
                ON CONFLICT (level) DO NOTHING
            ''')
        conn.commit()

def get_user(username):
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT id, username, current_level FROM users WHERE username = %s', 
                (username,)
            )
            return cursor.fetchone()

def create_user(username):
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO users (username) VALUES (%s) RETURNING id', 
                (username,)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()
            return user_id

def save_game_state(user_id, score, level, state):
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO scores (user_id, score, level, saved_state)
                VALUES (%s, %s, %s, %s)
                ''', 
                (user_id, score, level, state)
            )
            conn.commit()

def update_user_level(user_id, level):
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'UPDATE users SET current_level = %s WHERE id = %s', 
                (level, user_id)
            )
            conn.commit()

def get_level_details(level):
    with closing(get_conn()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT speed, walls FROM levels WHERE level = %s', 
                (level,)
            )
            return cursor.fetchone()

class SnakeGame:
    def __init__(self, username):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Змейка - Игрок: {username}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        
        # Состояние игры
        self.username = username
        self.user_id = None
        self.current_level = 1
        self.score = 0
        self.game_over = False
        self.paused = False
        
        # Инициализация БД и пользователя
        init_db()
        self._load_user()
        
        # Инициализация игры
        self._init_game()
    
    def _load_user(self):
        user = get_user(self.username)
        if user:
            self.user_id, _, self.current_level = user
            print(f"С возвращением, {self.username}! Текущий уровень: {self.current_level}")
        else:
            self.user_id = create_user(self.username)
            self.current_level = 1
            print(f"Новый игрок {self.username}! Начинаем с 1 уровня")
        
        # Загрузка уровня
        self.speed, walls_json = get_level_details(self.current_level)
        self.walls = json.loads(walls_json)
    
    def _init_game(self):
        # Начальная позиция змейки
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.snake = [
            [start_x, start_y],
            [start_x - 1, start_y],
            [start_x - 2, start_y]
        ]
        
        # Направление движения
        self.direction = [1, 0]
        self.next_direction = [1, 0]
        
        # Первая еда
        self._place_food()
    
    def _place_food(self):
        while True:
            x = random.randint(0, GRID_WIDTH - 1)
            y = random.randint(0, GRID_HEIGHT - 1)
            
            if [x, y] not in self.snake and not self._is_wall(x, y):
                self.food = [x, y]
                break
    
    def _is_wall(self, x, y):
        for wall in self.walls:
            wall_x, wall_y, wall_w, wall_h = wall
            if (wall_x <= x * CELL_SIZE < wall_x + wall_w and 
                wall_y <= y * CELL_SIZE < wall_y + wall_h):
                return True
        return False
    
    def _draw_walls(self):
        for wall in self.walls:
            pygame.draw.rect(self.screen, GRAY, pygame.Rect(*wall))
    
    def _save_game_state(self):
        state = {
            'snake': self.snake,
            'direction': self.direction,
            'food': self.food,
            'score': self.score,
            'level': self.current_level
        }
        save_game_state(self.user_id, self.score, self.current_level, json.dumps(state))
        print("Игра сохранена!")
    
    def _handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and self.direction != [0, 1]:
                    self.next_direction = [0, -1]
                elif event.key == pygame.K_DOWN and self.direction != [0, -1]:
                    self.next_direction = [0, 1]
                elif event.key == pygame.K_LEFT and self.direction != [1, 0]:
                    self.next_direction = [-1, 0]
                elif event.key == pygame.K_RIGHT and self.direction != [-1, 0]:
                    self.next_direction = [1, 0]
                elif event.key == PAUSE_KEY:
                    self.paused = not self.paused
                    if self.paused:
                        self._save_game_state()
    
    def _update_game(self):
        if self.paused or self.game_over:
            return
        
        self.direction = self.next_direction
        
        # Движение змейки
        head = [self.snake[0][0] + self.direction[0], self.snake[0][1] + self.direction[1]]
        self.snake.insert(0, head)
        
        # Проверка еды
        if head == self.food:
            self.score += 10
            self._place_food()
            
            # Повышение уровня
            if self.score // 50 > (self.score - 10) // 50 and self.current_level < 3:
                self.current_level += 1
                update_user_level(self.user_id, self.current_level)
                self.speed, walls_json = get_level_details(self.current_level)
                self.walls = json.loads(walls_json)
                print(f"Уровень повышен! Теперь уровень {self.current_level}")
        else:
            self.snake.pop()
        
        # Проверка столкновений
        if (head[0] < 0 or head[0] >= GRID_WIDTH or 
            head[1] < 0 or head[1] >= GRID_HEIGHT or 
            head in self.snake[1:] or 
            self._is_wall(head[0], head[1])):
            self.game_over = True
    
    def _draw_game(self):
        self.screen.fill(BLACK)
        
        # Отрисовка стен
        self._draw_walls()
        
        # Отрисовка змейки
        for segment in self.snake:
            pygame.draw.rect(self.screen, GREEN, 
                            pygame.Rect(segment[0] * CELL_SIZE, segment[1] * CELL_SIZE, 
                                       CELL_SIZE, CELL_SIZE))
        
        # Отрисовка еды
        pygame.draw.rect(self.screen, RED, 
                        pygame.Rect(self.food[0] * CELL_SIZE, self.food[1] * CELL_SIZE, 
                                   CELL_SIZE, CELL_SIZE))
        
        # Отрисовка счета и уровня
        score_text = self.font.render(f"Счет: {self.score}", True, WHITE)
        level_text = self.font.render(f"Уровень: {self.current_level}", True, WHITE)
        self.screen.blit(score_text, (10, 10))
        self.screen.blit(level_text, (10, 50))
        
        # Сообщения о паузе/окончании игры
        if self.paused:
            pause_text = self.font.render("ПАУЗА (Нажмите P для продолжения)", True, WHITE)
            self.screen.blit(pause_text, (SCREEN_WIDTH // 2 - 180, SCREEN_HEIGHT // 2))
        elif self.game_over:
            game_over_text = self.font.render("ИГРА ОКОНЧЕНА!", True, WHITE)
            restart_text = self.font.render("Нажмите R для перезапуска", True, WHITE)
            self.screen.blit(game_over_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 20))
            self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 20))
        
        pygame.display.flip()
    
    def run(self):
        while True:
            self._handle_input()
            
            # Перезапуск игры
            keys = pygame.key.get_pressed()
            if self.game_over and keys[pygame.K_r]:
                self.__init__(self.username)
            
            self._update_game()
            self._draw_game()
            self.clock.tick(self.speed)

def main():
    # Ввод имени пользователя
    username = input("Введите ваше имя: ").strip()
    while not username:
        username = input("Имя не может быть пустым. Введите ваше имя: ").strip()
    
    # Запуск игры
    game = SnakeGame(username)
    game.run()

if __name__ == "__main__":
    # Установите psycopg2 если нет: pip install psycopg2-binary
    main()