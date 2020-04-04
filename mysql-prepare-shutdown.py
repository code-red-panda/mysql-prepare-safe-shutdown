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
        connection = pymysql.connect(read_default_file = options.defaults_file)
    else:
        if options.ask_pass:
            password = getpass.getpass()
        else:
            password = options.password
        connection = pymysql.connect(
               host = options.host,
               user = options.user,
               password = password,
               unix_socket = options.socket)
    return connection;

def get_mysql_variable(variable_name):
    with conn.cursor() as cursor:
        sql = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        result = cursor.fetchone()
        value = result[1]
    cursor.close()
    return value;

def get_mysql_slave_status():
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        sql = "SHOW SLAVE STATUS";
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result is not None:
        master_log_file = result["Master_Log_File"]
        read_master_log_pos = int(result["Read_Master_Log_Pos"])
        relay_master_log_file = result["Relay_Master_Log_File"]
        exec_master_log_pos = int(result["Exec_Master_Log_Pos"])
        if master_log_file == relay_master_log_file:
            print("Files match")
        else:
            print("Files do not match")
        if read_master_log_pos == exec_master_log_pos:
            print("Pos match")
        else:
            print("Pos do not match")
    else:
        print("This is not a slave")
       
def stop_slave_single_thread():
    cursorclass=pymysql.cursors.DictCursor
    with conn.cursor() as cursor:
        sql = "STOP SLAVE IO_THREAD";
        cursor.execute(sql)
        row = cursor.fetchone()
        value = row[1]
    cursor.close()
    return value;

(options, args) = mysql_options()
conn = mysql_connect()
get_mysql_slave_status()
slave_parallel_workers = int(get_mysql_variable("slave_parallel_workers"))
if slave_parallel_workers > 0:
  print "slave is mts"
else:
  print "slave is not mts"
conn.close()
