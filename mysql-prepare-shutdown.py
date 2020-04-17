#!/usr/bin/python

import getpass
import pymysql.cursors
import os.path
import time
from optparse import OptionParser
from prettytable import PrettyTable

def mysql_options():
    parser = OptionParser()
    parser.add_option("-u", "--user", dest="user", default="", help="MySQL user")
    parser.add_option("-p", "--password", dest="password", default="", help="MySQL password")
    parser.add_option("--ask-pass", action="store_true", dest="ask_pass", help="Ask for password")
    parser.add_option("-H", "--host", dest="host", default="localhost", help="MySQL host. Default: localhost")
    parser.add_option("-P", "--port", dest="port", type="int", default="3306", help="MySQL port. Default: 3306")
    parser.add_option("-S", "--socket", dest="socket", default="/var/lib/mysql/mysql.sock", help="MySQL socket. Default: /var/lib/mysql/mysql.sock")
    parser.add_option("--defaults-file", dest="defaults_file", default="~/.my.cnf", help="Use MySQL configuration file. Default: ~/.my.cnf")
    parser.add_option("-t", "--no-transaction-check", action="store_true", dest="no_transaction_check", help="Do not check for transactions running > 60 seconds.")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Print additional information.")
    return parser.parse_args()

def info(message):
    print(">>> %s") % message

def verbose(message):
    if options.verbose:
        print(">>> %s") % message

def error(message):
    print(">>> CRITICAL: %s")% message
    print(">>> Todo: revert settings!")
    exit(1)

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
    return connection

def mysql_get_global_variable(variable_name):
    with conn.cursor() as cursor:
        sql = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        result = cursor.fetchone()
        value = result[1]
    cursor.close()
    return value

def mysql_get_status_variable(variable_name):
    with conn.cursor() as cursor:
        sql = "SHOW GLOBAL STATUS WHERE VARIABLE_NAME=%s";
        cursor.execute(sql, (variable_name))
        result = cursor.fetchone()
        value = result[1]
    cursor.close()
    return value

def mysql_query(sql):
    with conn.cursor() as cursor:
        cursor.execute(sql)
    cursor.close()

def mysql_check_is_slave():
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        sql = "SHOW SLAVE STATUS";
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result is None:
        verbose("This is not a slave. Skipping replication tasks.")
        value = 0
    else:
        verbose("This is a slave.")
        value = 1
    return value

def mysql_stop_slave_single_thread():
    info("Stopping replication.")
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
        verbose("IO thread was already stopped.")
    if slave_sql_running == "Yes":
        verbose("Giving the SQL thread 5 seconds to catch up.")
        time.sleep(5)
        verbose("Stopping SQL thread.")
        with conn.cursor() as cursor:
            sql = "STOP SLAVE SQL_thread";
            cursor.execute(sql)
            result = cursor.fetchone()
        cursor.close()
    else:
        verbose("SQL thread was already stopped.")
    if slave_io_running == "No" and slave_sql_running == "No":
        info("Replication was already stopped.")

def mysql_check_long_transactions():
    info("Checking for long running transactions.")
    with conn.cursor() as cursor:
        sql = "SELECT 1 FROM information_schema.innodb_trx JOIN information_schema.processlist ON innodb_trx.trx_mysql_thread_id = processlist.id WHERE (NOW() - trx_started) > 60 ORDER BY trx_started"
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result:
        info("There are transactions running > 60 seconds.")
        with conn.cursor() as cursor:
            sql = "SELECT trx_id, trx_started, (NOW() - trx_started) trx_duration_seconds, id processlist_id, user, IF(LEFT(HOST, (LOCATE(':', host) - 1)) = '', host, LEFT(HOST, (LOCATE(':', host) - 1))) host, command, time, REPLACE(SUBSTRING(info,1,25),'\n','') info_25 FROM information_schema.innodb_trx JOIN information_schema.processlist ON innodb_trx.trx_mysql_thread_id = processlist.id WHERE (NOW() - trx_started) > 60 ORDER BY trx_started"
            cursor.execute(sql)
            result = cursor.fetchall()
            columns = cursor.description
        cursor.close()
        x = PrettyTable([columns[0][0], columns[1][0], columns[2][0], columns[3][0], columns[4][0], columns[5][0], columns[6][0], columns[7][0], columns[8][0]]) 
        for row in result:
            x.add_row([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]])
        print x
        error("COMMIT, ROLLBACK, or kill these transactions. Otherwise, use --no-transaction-check to ignore them.")
    else:
        verbose("There are no transactions running > 60 seconds.")

def mysql_check_dirty_pages():
    verbose("Checking dirty pages count.")
    dirty_pages_start = mysql_get_status_variable("Innodb_buffer_pool_pages_dirty")
    verbose("Dirty pages starting count is %s." % dirty_pages_start)
    timeout = time.time() + 60
    while True:
        dirty_pages_current = mysql_get_status_variable("Innodb_buffer_pool_pages_dirty")
        if dirty_pages_current == 0:
            info("Dirty pages is 0.")
            break
        elif dirty_pages_current < (int(dirty_pages_start) * .10):
            info("Dirty pages is %s, < 10% of the starting count." % dirty_pages_current) 
            break
        elif int(dirty_pages_current) < 500:
            info("Dirty pages is %s, < 500." % dirty_pages_current)
            break
        elif time.time() > timeout:
            info("Dirty pages is %s, and has not reached < 10% of the starting count after 1 minute. Continuing to prepare for shutdown." % dirty_pages_current)
            break
        else:
            info("Dirty pages is %s, waiting (up to 1 minute) for it to get lower." % dirty_pages_current)
            time.sleep(5)

def mysql_prepare_shutdown():
    print("\n" + time.ctime())
    info("Preparing MySQL for shutdown.")

    # Check if the host is a slave. If true, stop replication.
    is_slave = int(mysql_check_is_slave())
    if is_slave:
        slave_parallel_workers = int(mysql_get_global_variable("slave_parallel_workers"))
        if slave_parallel_workers > 0:
            # Move message to function
            verbose("This is a multi-threaded slave.")
        else:
           mysql_stop_slave_single_thread()

    # Check for long running transactions.
    if options.no_transaction_check is None:
        mysql_check_long_transactions()
    else:
        info("--no-transaction-check was used. Not checking for long running transactions.")

    # Todo: Kill long running connections

    # Set dirty pages and fast shutdown to 0
    info("Setting innodb_max_dirty_pages_pct to 0")
    mysql_query("SET GLOBAL innodb_max_dirty_pages_pct = 0")
    mysql_check_dirty_pages()


    # print safe to shutdown
    # catch ctr+c
    # add error exits

(options, args) = mysql_options()
conn = mysql_connect()
mysql_prepare_shutdown()
conn.close()
