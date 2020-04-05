#!/usr/bin/python

import getpass
import pymysql.cursors
import os.path
import time
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
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Print additional information.")
    return parser.parse_args()

def verbose(message):
    if options.verbose:
        print("%s") % message

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

def mysql_get_global_variable(variable_name):
    with conn.cursor() as cursor:
        sql = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        result = cursor.fetchone()
        value = result[1]
    cursor.close()
    return value;

def mysql_get_status_variable(variable_name):
    with conn.cursor() as cursor:
        sql = "SHOW GLOBAL STATUS WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        result = cursor.fetchone()
        value = result[1]
    cursor.close()
    return value;

def mysql_is_slave():
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        sql = "SHOW SLAVE STATUS";
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result is None:
        verbose("This is not a slave.")
        value = 0;
    else:
        verbose("This is a slave.")
        value = 1;
    return value;

def mysql_stop_slave_single_thread():
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        sql = "SHOW SLAVE STATUS";
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    slave_io_running = result["Slave_IO_Running"]
    slave_sql_running = result["Slave_SQL_Running"]
    if slave_io_running == "Yes":
        verbose("Stopping IO thread.")
        with conn.cursor() as cursor:
            sql = "STOP SLAVE IO_THREAD";
            cursor.execute(sql)
            result = cursor.fetchone()
        cursor.close()
    else:
        verbose("IO thread was already stopped...")
    if slave_sql_running == "Yes":
        mysql_is_slave_current()
        verbose("Stopping SQL thread.")
        with conn.cursor() as cursor:
            sql = "STOP SLAVE SQL_thread";
            cursor.execute(sql)
            result = cursor.fetchone()
        cursor.close()
    else:
        verbose("SQL thread was already stopped...")
    if slave_io_running == "No" and slave_sql_running == "No":
        print("Slave was already stopped.")
    cursor.close()

def mysql_is_slave_current():
    timeout = time.time() + 60
    while True:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SHOW SLAVE STATUS";
            cursor.execute(sql)
            result = cursor.fetchone()
        cursor.close()
        master_log_file = result["Master_Log_File"]
        read_master_log_pos = int(result["Read_Master_Log_Pos"])
        relay_master_log_file = result["Relay_Master_Log_File"]
        exec_master_log_pos = int(result["Exec_Master_Log_Pos"])
        seconds_behind_master = result["Seconds_Behind_Master"]
        if master_log_file == relay_master_log_file and read_master_log_pos == exec_master_log_pos:
            print("Slave is current with master.")
            break
        elif time.time() > timeout:
            print("Slave has not caught up with master after 1 minute. Continuing to prepare for shutdown.")
            break
        else:
            print("Slave is lagging %s seconds behind master...waiting for it to catch up." % seconds_behind_master)
            time.sleep(5)
       
def mysql_prepare_shutdown():
    print("Preparing MySQL for shutdown...")
    is_slave = int(mysql_is_slave())
    if is_slave:
        print("Stopping replication...")
        slave_parallel_workers = int(mysql_get_global_variable("slave_parallel_workers"))
        if slave_parallel_workers > 0:
            verbose("This is a multi-threaded slave.")
        else:
           mysql_stop_slave_single_thread()
    # check for open trx > 60s
    # kill long running connections
    # fast shutdown=0, max dirty pages = 0
    # print safe to shutdown
    # catch ctr+c
    # add error exits

(options, args) = mysql_options()
conn = mysql_connect()
mysql_prepare_shutdown()
conn.close()
