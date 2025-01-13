import sqlite3


class Table:
    def __init__(self, db_path, name):
        self.db_path = db_path
        self.name = name.lower()

    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None:
                self.connection.rollback()
            else:
                self.connection.commit()
        finally:
            if self.connection:
                self.connection.close()

    def create(self, columns, primary):
        return self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self.name}({', '.join(columns)}, PRIMARY KEY ({primary}))"
        )

    def insert(self, data):
        payload = list(data.values())

        command = f"INSERT OR IGNORE INTO {self.name} ({', '.join(list(data.keys()))}) VALUES ({', '.join(['?'] * len(data))})"
        self.cursor.execute(command, payload)

    def update(self, data, where_key, set_key):
        payload = [where_key + set_key + data[set_key]]

        command = f"UPDATE {self.name} SET {set_key} = ? WHERE {where_key} = ?"
        return self.cursor.executem(command, payload)

    def upsert(self, data, conflict_key, set_key):
        payload = list(data.values())
        payload.append(data[set_key])

        command = f"""INSERT INTO {self.name} ({", ".join(list(data.keys()))})
            VALUES({", ".join(["?"] * len(data))}) 
            ON CONFLICT({conflict_key}) 
            DO UPDATE SET {set_key} = ?"""
        return self.cursor.execute(command, payload)

    def select(self, columns):
        command = f"SELECT {', '.join(columns)} FROM {self.name}"
        response = self.cursor.execute(command)

        data = []
        for row in response.fetchall():
            data.append({key: value for key, value in zip(columns, row)})

        return data
