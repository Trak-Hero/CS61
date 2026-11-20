# MySQL connection utility. read credentials from ~/.my.cnf.
import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        option_files=os.path.expanduser("~/.my.cnf"),
        database="CS61_Project",
        autocommit=False
    )