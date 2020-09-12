#!/usr/bin/python

import ConfigParser as configparser
import getpass
import pymysql.cursors
import os.path
from time import gmtime, strftime, sleep, time
from optparse import OptionParser
from prettytable import PrettyTable


def mysql_options():
    parser = OptionParser()
    parser.add_option("-u", "--user", type="string", dest="user", help="MySQL user.")
    parser.add_option("-p", "--password", type="string", dest="password", metavar="PASS", help="MySQL password.")
    parser.add_option("--ask-pass", dest="ask_pass", action="store_true", help="Ask for password.")
    parser.add_option("-H", "--host", type="string", dest="host", help="MySQL host. Default: localhost")
    parser.add_option("-P", "--port", type="int", dest="port", help="MySQL port. Default: 3306")
    parser.add_option("-S", "--socket", type="string", dest="socket", metavar="SOCK", help="MySQL socket. Default: /var/lib/mysql/mysql.sock")
    parser.add_option("--defaults-file", dest="defaults_file", metavar="FILE", help="Use MySQL configuration file.")
    parser.add_option("-t", "--no-transaction-check", action="store_true", dest="no_transaction_check", help="Do not check for transactions running > 60 seconds.")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Print additional information.")
    return parser.parse_args()


def info(message):
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " >>> %s") % message


def verbose(message):
    if options.verbose:
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " >>> %s") % message


def warn(message):
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " >>> [ WARNING ] %s") % message


def error(message):
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " >>> [ CRITICAL ] %s") % message
    exit(1)


def mysql_connect():
    if options.defaults_file is not None:
        connection = pymysql.connect(read_default_file = options.defaults_file)
    else:
        try:
            dot_my_cnf = os.path.expanduser("~/.my.cnf")
            parser = configparser.ConfigParser()
            parser.read(dot_my_cnf)
            has_dot_my_cnf = 1
        except:
            has_dot_my_cnf = None
        conn_host = "localhost"
        if options.host:
            conn_host = options.host
        elif has_dot_my_cnf:
            try:
                conn_host = parser.get('client','host')
            except:
                pass
        conn_user = None
        if options.user:
            conn_user = options.user
        elif has_dot_my_cnf:
            try:
                conn_user = parser.get('client','user')
            except:
                pass
        conn_password = None
        if options.ask_pass:
            conn_password = getpass.getpass()
        elif options.password:
            conn_password = options.password
        elif has_dot_my_cnf:
            try:
                conn_password = parser.get('client','password')
            except:
                pass
        conn_socket = "/var/lib/mysql/mysql.sock"
        if options.socket:
            conn_socket = options.socket
        elif has_dot_my_cnf:
            try:
                conn_socket = parser.get('client','socket')
            except:
                pass
        connection = pymysql.connect(
            host = conn_host,
            user = conn_user,
            password = conn_password,
            unix_socket = conn_socket)
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


def mysql_check_is_replica():
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        sql = "SHOW SLAVE STATUS";
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result is None:
        verbose("This is not a replica. Skipping replication tasks.")
        value = 0
    else:
        verbose("This is a replica.")
        value = 1
    return value


def mysql_stop_replica_single_thread():
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
        verbose("Giving the SQL thread 10 seconds to catch up.")
        sleep(10)
        verbose("Stopping SQL thread.")
        with conn.cursor() as cursor:
            sql = "STOP SLAVE SQL_thread";
            cursor.execute(sql)
            result = cursor.fetchone()
        cursor.close()
    else:
        verbose("SQL thread was already stopped.")
    if slave_io_running == "No" and slave_sql_running == "No":
        warn("Replication was already stopped.")


def mysql_start_replica_single_thread():
    warn("Restarting replication. There was either a problem or you aborted.")
    mysql_query("START SLAVE")


def mysql_check_long_transactions(is_replica):
    info("Checking for long running transactions.")
    with conn.cursor() as cursor:
        sql = "SELECT 1 FROM information_schema.innodb_trx JOIN information_schema.processlist ON innodb_trx.trx_mysql_thread_id = processlist.id WHERE (NOW() - trx_started) > 60 ORDER BY trx_started"
        cursor.execute(sql)
        result = cursor.fetchone()
    cursor.close()
    if result:
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
        if is_replica:
            mysql_start_replica_single_thread()
        error("Transaction(s) found running > 60 seconds. COMMIT, ROLLBACK, or kill them. Otherwise, use the less safe --no-transaction-check.")
    else:
        verbose("There are no transactions running > 60 seconds.")


def mysql_set_dirty_pages_pct(count):
    info("Setting innodb_max_dirty_pages_pct to %s." % count)
    mysql_query("SET GLOBAL innodb_max_dirty_pages_pct = %s" % count)


def mysql_check_dirty_pages(dirty_pages_start):
    verbose("Checking dirty pages. The starting count is %s." % dirty_pages_start)
    timeout = time() + 60
    while True:
        dirty_pages_current = int(mysql_get_status_variable("Innodb_buffer_pool_pages_dirty"))
        if dirty_pages_current == 0:
            info("Dirty pages is 0.")
            break
        elif dirty_pages_current < (int(dirty_pages_start) * .10):
            verbose("Dirty pages is %s." % dirty_pages_current) 
            info("Dirty pages < 10% of the starting count.") 
            break
        elif int(dirty_pages_current) > 500:
            verbose("Dirty pages is %s." % dirty_pages_current) 
            info("Dirty pages < 500.")
            break
        elif time() > timeout:
            warn("Dirty pages is %s, and did not reach < 10 pct of the starting count after 1 minute." % dirty_pages_current)
            break
        else:
            info("Dirty pages is %s, waiting (up to 1 minute) for it to get lower." % dirty_pages_current)
            sleep(1)


def mysql_set_fast_shutdown():
    info("Setting innodb_fast_shutdown to 0.")
    mysql_query("SET GLOBAL innodb_fast_shutdown = 0")


def mysql_set_buffer_pool_dump():
    info("Setting innodb_buffer_pool_dump_at_shutdown to ON.")
    mysql_query("SET GLOBAL innodb_buffer_pool_dump_at_shutdown = ON")
    info("Setting innodb_buffer_pool_dump_pct to 75.")
    mysql_query("SET GLOBAL innodb_buffer_pool_dump_pct = 75")
    buffer_pool_load = mysql_get_global_variable("innodb_buffer_pool_load_at_startup")
    if buffer_pool_load != "ON":
        warn("innodb_buffer_pool_load_at_startup is not enabled. You may want to set this in the my.cnf: innodb_buffer_pool_load_at_startup = ON")


def mysql_prepare_shutdown():
    info("[ START ] Preparing MySQL for shutdown.")
    # Check if the host is a replica.
    is_replica = int(mysql_check_is_replica())
    if is_replica:
        slave_parallel_workers = int(mysql_get_global_variable("slave_parallel_workers"))
        if slave_parallel_workers > 0:
            error("This is a multi-threaded replica.")
        else:
           mysql_stop_replica_single_thread()
    # Check for long running transactions.
    if options.no_transaction_check is None:
        mysql_check_long_transactions(is_replica)
    else:
        warn("--no-transaction-check was used. Not checking for long running transactions.")
    # Get dirty pages details.
    dirty_pages_pct_original = float(mysql_get_global_variable("innodb_max_dirty_pages_pct"))
    verbose("innodb_max_dirty_pages_pct was %s." % dirty_pages_pct_original)
    dirty_pages_start = int(mysql_get_status_variable("Innodb_buffer_pool_pages_dirty"))
    # Set dirty pages to 0 and check that they're low enough.
    mysql_set_dirty_pages_pct(0)
    try:
        mysql_check_dirty_pages(dirty_pages_start)
    except KeyboardInterrupt:
        warn("CTL+C. Reverting changes.")
        mysql_set_dirty_pages_pct(dirty_pages_pct_original)
        if is_replica:
            mysql_start_replica_single_thread()
        error("Terminated.")
    # Set fast shutdown to 0.
    mysql_set_fast_shutdown()
    # Set buffer pool dump configurations.
    mysql_set_buffer_pool_dump()
    info("[ COMPLETED ] MySQL is prepared for shutdown!")


try:
    conn = None
    (options, args) = mysql_options()
    conn = mysql_connect()
    mysql_prepare_shutdown()
except pymysql.Error as e:
    error("ERROR " + str(e[0]) + ": " + e[1])
finally:
    if conn:
        conn.close()
