from mysql import connector
from mysql.connector import Error

class MySQLDatabase:
    def __init__(self, host, user, password, database):
        self.connection = connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.cursor = self.connection.cursor()

    def execute_query(self, query, params=None):
        try:
            self.cursor.execute(query, params)
            self.connection.commit()
            print("Query executed successfully")
        except Error as err:
            print(f"Mysql execute Error: {err}")
            self.connection.rollback()

    def fetch_data(self, query, params=None):
        try:
            self.cursor.execute(query, params)
            result = self.cursor.fetchall()
            return result
        except Error as err:
            print(f"Mysql fetch Error: {err}")
            return None

    def close_connection(self):
        self.cursor.close()
        self.connection.close()

    def __del__(self):
        self.close_connection()
