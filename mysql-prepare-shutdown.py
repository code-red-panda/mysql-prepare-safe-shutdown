#!/usr/bin/python

import os.path
import getpass
import pymysql.cursors
from optparse import OptionParser

def mysql_options():
  parser = OptionParser()
  parser.add_option("-u", "--user", dest="user", default="", help="MySQL user")
  parser.add_option("-p", "--password", dest="password", default="", help="MySQL password")
  parser.add_option("--ask-pass", action="store_true", dest="ask_pass", help="Ask for password")
  parser.add_option("-H", "--host", dest="host", default="localhost", help="MySQL host. Default: localhost")
  parser.add_option("-P", "--port", dest="port", type="int", default="3306", help="MySQL port. Default: 3306")
  parser.add_option("-S", "--socket", dest="socket", default="/var/lib/mysql/mysql.sock", help="MySQL socket. Default: /var/lib/mysql/mysql.sock")
  parser.add_option("--defaults-file", dest="defaults_file", default="~/.my.cnf", help="Use MySQL configuration file. Default: ~/.my.cnf")
  return parser.parse_args()

def mysql_connect():
    if os.path.expanduser(options.defaults_file):
        conn = pymysql.connect(read_default_file = options.defaults_file)
    else:
        if options.ask_pass:
            password = getpass.getpass()
        else:
            password = options.password
        conn = pymysql.connect(host = options.host, user = options.user, password = password, unix_socket = options.socket)
    return conn;

def get_mysql_variable(variable_name):
    connection = conn
    cursorclass=pymysql.cursors.DictCursor
    with connection.cursor() as cursor:
        sql = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        #cursor.execute(sql)
        result = cursor.fetchone()
        cursor.close()
        value = result[1]
        print(value)

(options, args) = mysql_options()
conn = mysql_connect()
get_mysql_variable("slave_parallel_workers")
conn.close()
