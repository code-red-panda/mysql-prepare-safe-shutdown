# Pre-Requisites
- Python 3.2+
- [PyMySQL](https://github.com/PyMySQL/PyMySQL) (Python connector)
- [PTable](https://pypi.org/project/PTable/) (Print tabular data in a pretty table)
```
pip install PyMySQL PTable
```

# About
`mysql-prepare-shutdown` will NOT stop MySQL. It will only prepare MySQL by doing the following:
- Check if the host is a replica.
	- If yes, stop replication.
- Check if any transactions are running > 60 seconds.
	- If no, continue to prepare for shutdown.
	- If yes, print transaction details to review, restart replication, and exit.
	- This check can be ignored with `--no-transaction-check`
- Set `innodb_max_dirty_pages_pct` to 0.
- Wait up to 1 minute for `Innodb_buffer_pool_pages_dirty` to be < 500 or < 10% of the starting number of dirty pages.
	- If neither condition is true after 1 minute, the tool will still continue to prepare for shutdown.
	- You can abort with CTRL+C during this minute and the tool will restart replication and exit.
- Set `innodb_fast_shutdown=0`.
- Enable `innodb_buffer_pool_dump_at_shutdown` and set `innodb_buffer_pool_dump_pct=75`.
	- The tool will recommend enabling `innodb_buffer_pool_load_at_startup` if it's not already.
- Notify you that MySQL is prepared for shutdown.

# Options
```
usage: mysql-prepare-shutdown.py [-h] [-u USER] [-p PASS] [--ask-pass] [-H HOST] [-P PORT] [-S SOCK] [--defaults-file FILE] [-t] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -u USER, --user USER  MySQL user.
  -p PASS, --password PASS
                        MySQL password.
  --ask-pass            Ask for password.
  -H HOST, --host HOST  MySQL host. Default: localhost
  -P PORT, --port PORT  MySQL port. Default: 3306
  -S SOCK, --socket SOCK
                        MySQL socket. Default: /var/lib/mysql/mysql.sock
  --defaults-file FILE  Use MySQL configuration file.
  -t, --no-transaction-check
                        Do not check for transactions running > 60 seconds.
  -v, --verbose         Print additional information.
```

# Limitations
Currently, this tool should not be used on:
- Multi-threaded replicas. It will exit if the replica has `slave_parallel_workers > 0`.
- Multi-channel replicas. Be careful as the tool does not even check for this condition.

# Examples
Happy path.
```
# ./mysql-prepare-shutdown.py --verbose
2020-09-12 18:28:41 >>> [ START ] Preparing MySQL for shutdown.
2020-09-12 18:28:41 >>> This is a replica.
2020-09-12 18:28:41 >>> Stopping replication.
2020-09-12 18:28:41 >>> Stopping IO thread.
2020-09-12 18:28:41 >>> Giving the SQL thread 10 seconds to catch up.
2020-09-12 18:28:51 >>> Stopping SQL thread.
2020-09-12 18:28:51 >>> Checking for long running transactions.
2020-09-12 18:28:51 >>> There are no transactions running > 60 seconds.
2020-09-12 18:28:51 >>> innodb_max_dirty_pages_pct was 90.0.
2020-09-12 18:28:51 >>> Setting innodb_max_dirty_pages_pct to 0.
2020-09-12 18:28:51 >>> Checking dirty pages. The starting count is 6.
2020-09-12 18:28:51 >>> Dirty pages is 6, waiting (up to 1 minute) for it to get lower.
2020-09-12 18:28:52 >>> Dirty pages is 1, waiting (up to 1 minute) for it to get lower.
2020-09-12 18:28:53 >>> Dirty pages is 0.
2020-09-12 18:28:53 >>> Setting innodb_fast_shutdown to 0.
2020-09-12 18:28:53 >>> Setting innodb_buffer_pool_dump_at_shutdown to ON.
2020-09-12 18:28:53 >>> Setting innodb_buffer_pool_dump_pct to 75.
2020-09-12 18:28:53 >>> [ COMPLETED ] MySQL is prepared for shutdown!
```
Aborting due to transactions found running > 60 seconds.
```
# ./mysql-prepare-shutdown.py --verbose
2020-09-12 18:36:09 >>> [ START ] Preparing MySQL for shutdown.
2020-09-12 18:36:09 >>> This is a replica.
2020-09-12 18:36:09 >>> Stopping replication.
2020-09-12 18:36:09 >>> Stopping IO thread.
2020-09-12 18:36:09 >>> Giving the SQL thread 10 seconds to catch up.
2020-09-12 18:36:19 >>> Stopping SQL thread.
2020-09-12 18:36:19 >>> Checking for long running transactions.
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
| trx_id |     trx_started     | trx_duration_seconds | processlist_id |   user   |    host   | command | time | info_25 |
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
|  3932  | 2020-09-12 13:34:50 |         169          |       14       | msandbox | localhost |  Sleep  |  15  |   None  |
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
2020-09-12 18:36:19 >>> [ WARNING ] Restarting replication. There was either a problem or you aborted.
2020-09-12 18:36:19 >>> [ CRITICAL ] Transaction(s) found running > 60 seconds. COMMIT, ROLLBACK, or kill them. Otherwise, use the less safe --no-transaction-check.
```

# To Do
- Kill long running queries.
- Add multi-threaded replica support.
- Add multi-channel replica support.
