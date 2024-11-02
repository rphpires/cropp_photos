
# Descrição: Arquivo base para conexão com o banco de dados
# Desenvolvido por: Raphael Pires
# Última Revisão: 09/08/2023

import threading
import pyodbc
from dotenv import load_dotenv
import json
import platform

load_dotenv()


class ServiceParameters:
    def __init__(self):
        with open('config.json', 'r') as file:
            data = json.load(file)

        self.cropp_photo = data["cropp_photo"]
        self.last_photo_update = data["last_photo_update"]
        self.quality = data["quality"]


class ApiConnection:
    def __init__(self):
        with open('config.json', 'r') as file:
            data = json.load(file)

        self.url = data["wxs_api_url"]
        self.user = data["wxs_api_user"]
        self.password = data["wxs_api_password"]


class DatabaseReader:
    def __init__(self):
        with open('config.json', 'r') as file:
            data = json.load(file)

        self.server = data["server_name"]
        self.database = data["db_name"]
        self.username = data["db_user"]
        self.password = data["db_password"]
        self.api_url = data["wxs_api_url"]
        self.api_user = data["wxs_api_user"]
        self.api_password = data["wxs_api_password"]

        self.lock = threading.Lock()

    def _create_connection(self):
        connection_string = (
            f"DRIVER={self.get_odbc_client()};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            "Encrypt=no;"
        )
        # print(f'ConnString: {connection_string}')
        return pyodbc.connect(connection_string)

    def _execute_query(self, query):
        connection = self._create_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(query)
            connection.commit()
            return True
        except Exception as e:
            print(f"Error executing query: {str(e)}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()

    def read_data(self, query):
        with self.lock:
            connection = self._create_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(query)
                result = cursor.fetchall()
            except Exception as e:
                result = None
                print(f"Error executing query: {str(e)}")
            finally:
                cursor.close()
                connection.close()

        return result

    def read_single_row(self, query):
        with self.lock:
            connection = self._create_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(query)
                result = cursor.fetchone()
            except Exception as e:
                result = None
                print(f"Error executing query: {str(e)}")
            finally:
                cursor.close()
                connection.close()

        return result

    def execute(self, query):
        return self._execute_query(query)

    def execute_insert(self, query):
        return self._execute_query(query)

    def execute_procedure(self, procedure_name, params=None):
        with self.lock:
            connection = self._create_connection()
            cursor = connection.cursor()

            try:
                if params:
                    cursor.execute(f"EXEC {procedure_name} {', '.join(params)}")
                else:
                    cursor.execute(f"EXEC {procedure_name}")
                connection.commit()
                return True
            except Exception as e:
                print(f"Error executing procedure: {str(e)}")
                connection.rollback()
                return False
            finally:
                cursor.close()
                connection.close()

    def get_odbc_client(self):
        try:
            match check_os():
                case 'Linux':
                    odbc = '{ODBC Driver 18 for SQL Server}'
                case 'Windows':
                    odbc = '{SQL Server}'
                case _:
                    odbc = '{SQL Server}'
        except Exception:
            print('*** Error getting drive ODBC')

        finally:
            return odbc


def check_os():
    os_type = platform.system()
    if os_type == "Windows":
        return "Windows"
    elif os_type == "Linux":
        return "Linux"
    elif os_type == "Darwin":
        return "MacOS"
    else:
        return "Unknown"


if __name__ == "__main__":
    conn = DatabaseReader()
    r = conn.read_data("select count(*) from CHMain")
    print(r)
