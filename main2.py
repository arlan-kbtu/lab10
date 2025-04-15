import psycopg2
import csv
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_HOST = "ep-winter-unit-a1pzep3v-pooler.ap-southeast-1.aws.neon.tech"
DB_NAME = "neondb"
DB_USER = "neondb_owner"
DB_PASSWORD = "npg_tiQjpz6AhM0q"
DB_SSLMODE = "require"

def get_connection():
    """Устанавливает соединение с Neon PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode=DB_SSLMODE
        )
        logger.info("Успешное подключение к Neon PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения: {e}")
        return None

def create_table():
    """Создает таблицу phonebook, если она не существует"""
    conn = None
    try:
        conn = get_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS phonebook (
                        id SERIAL PRIMARY KEY,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50),
                        phone VARCHAR(20) NOT NULL UNIQUE,
                        email VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info("Таблица phonebook создана или уже существует")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы: {e}")
    finally:
        if conn:
            conn.close()

def import_from_csv(filename):
    conn = None
    try:
        logger.info(f"Начинается импорт из файла: {filename}")
        conn = get_connection()
        if conn is None:
            logger.error("Не удалось установить соединение с базой данных.")
            print("Ошибка: Не удалось подключиться к базе данных.")
            return

        with conn.cursor() as cur, open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)  # Пропускаем заголовок
                logger.info(f"Заголовок CSV: {header}")
            except StopIteration:
                logger.warning(f"CSV файл '{filename}' пуст.")
                print(f"Предупреждение: CSV файл '{filename}' пуст.")
                return

            imported_count = 0
            skipped_count = 0
            error_count = 0

            for row_number, row in enumerate(reader, start=2):  # Начинаем нумерацию строк с 2 (после заголовка)
                if len(row) >= 2:
                    first_name = row[0].strip()
                    phone = row[1].strip()
                    last_name = row[2].strip() if len(row) > 2 else None
                    email = row[3].strip() if len(row) > 3 else None

                    if not first_name or not phone:
                        logger.warning(f"Строка {row_number}: Пропущена из-за отсутствия имени или телефона: {row}")
                        print(f"Предупреждение: Строка {row_number}: Пропущена из-за отсутствия имени или телефона.")
                        skipped_count += 1
                        continue

                    try:
                        cur.execute("""
                            INSERT INTO phonebook (first_name, last_name, phone, email)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (phone) DO NOTHING
                        """, (first_name, last_name, phone, email))
                        imported_count += 1
                        logger.info(f"Строка {row_number}: Успешно обработана: имя={first_name}, телефон={phone}")
                    except psycopg2.Error as e:
                        error_count += 1
                        logger.error(f"Строка {row_number}: Ошибка при добавлении {first_name} (телефон: {phone}): {e}")
                        print(f"Ошибка: Строка {row_number}: Не удалось добавить {first_name} (телефон: {phone}). Подробности в логах.")
                else:
                    logger.warning(f"Строка {row_number}: Пропущена из-за недостаточного количества столбцов: {row}")
                    print(f"Предупреждение: Строка {row_number}: Пропущена из-за недостаточного количества столбцов.")
                    skipped_count += 1

            conn.commit()
            logger.info(f"Импорт завершен. Успешно импортировано: {imported_count}, пропущено: {skipped_count}, ошибок: {error_count}")
            print(f"Импорт завершен. Успешно импортировано: {imported_count} контактов.")
            if skipped_count > 0:
                print(f"Пропущено {skipped_count} строк из-за отсутствия имени или телефона или недостаточного количества столбцов.")
            if error_count > 0:
                print(f"Произошло {error_count} ошибок при импорте. Подробности смотрите в логах.")

    except FileNotFoundError:
        logger.error(f"Файл не найден: {filename}")
        print(f"Ошибка: Файл '{filename}' не найден.")
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка при импорте: {e}")
        print(f"Произошла непредвиденная ошибка при импорте. Подробности смотрите в логах.")
    finally:
        if conn:
            conn.close()
            logger.info("Соединение с базой данных закрыто.")

def add_contact():
    print("\nДобавление нового контакта:")
    first_name = input("Имя: ").strip()
    phone = input("Телефон: ").strip()
    last_name = input("Фамилия (необязательно): ").strip() or None
    email = input("Email (необязательно): ").strip() or None

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO phonebook (first_name, last_name, phone, email)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (first_name, last_name, phone, email))

            contact_id = cur.fetchone()[0]
            conn.commit()
            print(f"Контакт успешно добавлен с ID {contact_id}!")
    except Exception as e:
        print(f"Ошибка при добавлении контакта: {e}")
    finally:
        if conn:
            conn.close()

def update_contact():
    print("\nОбновление контакта:")
    search_term = input("Введите имя или телефон контакта для обновления: ").strip()

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, first_name, last_name, phone, email
                FROM phonebook
                WHERE first_name ILIKE %s OR phone LIKE %s
            """, (f"%{search_term}%", f"%{search_term}%"))
            results = cur.fetchall()

            if not results:
                print("Контакт не найден.")
                return

            print("\nНайденные контакты:")
            for contact in results:
                print(f"{contact[0]}. {contact[1]} {contact[2] or ''} ({contact[3]}) - {contact[4] or 'Нет email'}")

            contact_id_to_update = input("Введите ID контакта для обновления: ")
            try:
                contact_id_to_update = int(contact_id_to_update)
            except ValueError:
                print("Неверный ID контакта.")
                return

            # Проверяем, существует ли контакт с таким ID
            cur.execute("SELECT * FROM phonebook WHERE id = %s", (contact_id_to_update,))
            if not cur.fetchone():
                print(f"Контакт с ID {contact_id_to_update} не найден.")
                return

            print("\nЧто вы хотите обновить?")
            print("1. Имя")
            print("2. Фамилию")
            print("3. Телефон")
            print("4. Email")
            print("5. Ничего")

            update_choice = input("Выберите действие (1-5): ")

            if update_choice == '1':
                new_name = input("Введите новое имя: ").strip()
                cur.execute("UPDATE phonebook SET first_name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_name, contact_id_to_update))
            elif update_choice == '2':
                new_last_name = input("Введите новую фамилию (или оставьте пустым): ").strip() or None
                cur.execute("UPDATE phonebook SET last_name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_last_name, contact_id_to_update))
            elif update_choice == '3':
                new_phone = input("Введите новый телефон: ").strip()
                cur.execute("UPDATE phonebook SET phone = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_phone, contact_id_to_update))
            elif update_choice == '4':
                new_email = input("Введите новый email (или оставьте пустым): ").strip() or None
                cur.execute("UPDATE phonebook SET email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_email, contact_id_to_update))
            elif update_choice == '5':
                print("Обновление отменено.")
                return
            else:
                print("Неверный выбор!")
                return

            conn.commit()
            print("Контакт успешно обновлен!")

    except Exception as e:
        print(f"Ошибка при обновлении: {e}")
    finally:
        if conn:
            conn.close()

def search_contacts():
    print("\nВарианты поиска:")
    print("1. По имени")
    print("2. По фамилии")
    print("3. По телефону")
    print("4. По email")
    print("5. Показать все контакты")

    choice = input("Выберите вариант поиска (1-5): ")

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            if choice == '1':
                name = input("Введите имя: ")
                cur.execute("SELECT * FROM phonebook WHERE first_name ILIKE %s ORDER BY first_name", (f"%{name}%",))
            elif choice == '2':
                name = input("Введите фамилию: ")
                cur.execute("SELECT * FROM phonebook WHERE last_name ILIKE %s ORDER BY first_name", (f"%{name}%",))
            elif choice == '3':
                phone = input("Введите телефон: ")
                cur.execute("SELECT * FROM phonebook WHERE phone LIKE %s ORDER BY first_name", (f"%{phone}%",))
            elif choice == '4':
                email = input("Введите email: ")
                cur.execute("SELECT * FROM phonebook WHERE email ILIKE %s ORDER BY first_name", (f"%{email}%",))
            elif choice == '5':
                cur.execute("SELECT * FROM phonebook ORDER BY first_name")
            else:
                print("Неверный выбор!")
                return

            contacts = cur.fetchall()
            if not contacts:
                print("Контакты не найдены")
                return

            print("\nНайденные контакты:")
            for contact in contacts:
                print(f"ID: {contact[0]}")
                print(f"Имя: {contact[1]} {contact[2] or ''}")
                print(f"Телефон: {contact[3]}")
                print(f"Email: {contact[4] or 'Нет'}")
                print(f"Обновлен: {contact[6]}")
                print("-" * 40)
    except Exception as e:
        print(f"Ошибка при поиске: {e}")
    finally:
        if conn:
            conn.close()

def delete_contact():
    print("\nУдаление контакта:")
    print("1. По телефону")
    print("2. По имени")

    choice = input("Выберите вариант (1-2): ")

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            if choice == '1':
                phone = input("Введите телефон: ")
                cur.execute("DELETE FROM phonebook WHERE phone = %s RETURNING *", (phone,))
            elif choice == '2':
                name = input("Введите имя: ")
                cur.execute("DELETE FROM phonebook WHERE first_name ILIKE %s RETURNING *", (f"%{name}%",))
            else:
                print("Неверный выбор!")
                return

            deleted = cur.fetchall()
            conn.commit()

            if deleted:
                print(f"Удалено {len(deleted)} контактов:")
                for contact in deleted:
                    print(f"- {contact[1]} {contact[2] or ''} ({contact[3]})")
            else:
                print("Контакты не найдены")
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
    finally:
        if conn:
            conn.close()

def main():
    create_table()

    while True:
        print("\nТелефонная книга")
        print("1. Импорт из CSV")
        print("2. Добавить контакт")
        print("3. Обновить контакт")
        print("4. Поиск контактов")
        print("5. Удалить контакт")
        print("6. Выход")

        choice = input("Выберите действие (1-6): ")

        if choice == '1':
            filename = input("Введите имя CSV файла: ")
            import_from_csv(filename)
        elif choice == '2':
            add_contact()
        elif choice == '3':
            update_contact()
        elif choice == '4':
            search_contacts()
        elif choice == '5':
            delete_contact()
        elif choice == '6':
            print("До свидания!")
            break
        else:
            print("Неверный выбор!")

if __name__ == "__main__":
    main()