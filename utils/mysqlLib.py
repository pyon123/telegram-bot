import atexit
from mysql.connector import pooling, Error

class MySQL:
    def __init__(self, host, user, password, database):
        self.pool = pooling.MySQLConnectionPool(
            host=host,
            user=user,
            password=password,
            database=database,
            pool_size=5
        )

    def execute_query(self, query, params=None):
        connection = self.pool.get_connection()
        cursor = None

        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            connection.commit()
            print("Query executed successfully")
        except Error as err:
            print(f"Mysql execute Error: {err}")
            connection.rollback()
        finally:
            if cursor:
                cursor.close()
            connection.close()

    def fetch_data(self, query, params=None):
        connection = self.pool.get_connection()
        cursor = None

        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            return result
        except Error as err:
            print(f"Mysql fetch Error: {err}")
            return None
        finally:
            if cursor:
                cursor.close()
            connection.close()
