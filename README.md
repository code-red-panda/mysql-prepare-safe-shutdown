# Pre-Requisites
- [PyMySQL](https://github.com/PyMySQL/PyMySQL) (Python connector)
- [PTable](https://pypi.org/project/PTable/) (Print tabular data in a pretty table)
- Currently the tool is only tested with python 2.7
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
        - This check can be ignored with --no-transaction-check
- Set `innodb_max_dirty_pages_pct` to 0.
- Wait up to 1 minute for `Innodb_buffer_pool_pages_dirty` to be < 500 or < 10% of the starting number of dirty pages.
	- If neither condition is true after 1 minute, the tool will continue to prepare for shutdown.
        - You can abort with CTRL+C during this minute and the tool will restart replication and exit.
- Set `innodb_fast_shutdown=0`.
- Enable `innodb_buffer_pool_dump_at_shutdown` and set `innodb_buffer_pool_dump_pct=75`.
	- The tool will recommend enabling `innodb_buffer_pool_load_at_startup` if it's not already.
- Notify you that MySQL is prepared for shutdown.

# Options
```
Options:
  -h, --help            show this help message and exit
  -u USER, --user=USER  MySQL user
  -p PASS, --password=PASS
                        MySQL password
  --ask-pass            Ask for password
  -H HOST, --host=HOST  MySQL host. Default: localhost
  -P PORT, --port=PORT  MySQL port. Default: 3306
  -S SOCK, --socket=SOCK
                        MySQL socket.
  --defaults-file=FILE  Use MySQL configuration file
  -t, --no-transaction-check
                        Do not check for transactions running > 60 seconds.
  -v, --verbose         Print additional information
```

# Limitations
Currently, this tool should not be used on:
- Multi-threaded replicas. It will exit if the replica has `slave_parallel_workers > 0`.
- Multi-channel replicas. Be careful as the tool does not even check for this condition.

# Examples
Happy path.
```
[vagrant@centos7 ps57]$ ./mysql-prepare-shutdown.py --defaults-file=node1/my.sandbox.cnf --verbose
2020-09-12 15:04:58 >>> [ START ] Preparing MySQL for shutdown.
2020-09-12 15:04:58 >>> This is a replica.
2020-09-12 15:04:58 >>> Stopping replication.
2020-09-12 15:04:58 >>> Stopping IO thread.
2020-09-12 15:04:58 >>> Giving the SQL thread 10 seconds to catch up.
2020-09-12 15:05:08 >>> Stopping SQL thread.
2020-09-12 15:05:08 >>> Checking for long running transactions.
2020-09-12 15:05:08 >>> There are no transactions running > 60 seconds.
2020-09-12 15:05:08 >>> innodb_max_dirty_pages_pct was 0.0.
2020-09-12 15:05:08 >>> Setting innodb_max_dirty_pages_pct to 0.
2020-09-12 15:05:08 >>> Checking dirty pages. The starting count is 3.
2020-09-12 15:05:08 >>> Dirty pages is 3, waiting (up to 1 minute) for it to get lower.
2020-09-12 15:05:09 >>> Dirty pages is 3, waiting (up to 1 minute) for it to get lower.
2020-09-12 15:05:10 >>> Dirty pages is 0.
2020-09-12 15:05:10 >>> Setting innodb_fast_shutdown to 0.
2020-09-12 15:05:10 >>> Setting innodb_buffer_pool_dump_at_shutdown to ON.
2020-09-12 15:05:10 >>> Setting innodb_buffer_pool_dump_pct to 75.
2020-09-12 15:05:10 >>> [ COMPLETED ] MySQL is prepared for shutdown!
```
Aborting due to transactions found running > 60 seconds.
```
[vagrant@centos7 ps57]$ ./mysql-prepare-shutdown.py --defaults-file=node1/my.sandbox.cnf --verbose
2020-09-12 14:24:18 >>> [ START ] Preparing MySQL for shutdown.
2020-09-12 14:24:18 >>> This is a replica.
2020-09-12 14:24:18 >>> Stopping replication.
2020-09-12 14:24:19 >>> Stopping IO thread.
2020-09-12 14:24:19 >>> Giving the SQL thread 10 seconds to catch up.
2020-09-12 14:24:29 >>> Stopping SQL thread.
2020-09-12 14:24:29 >>> Checking for long running transactions.
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
| trx_id |     trx_started     | trx_duration_seconds | processlist_id |   user   |    host   | command | time | info_25 |
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
|  9740  | 2020-09-12 14:06:15 |         1814         |       35       | msandbox | localhost |  Sleep  | 1084 |   None  |
+--------+---------------------+----------------------+----------------+----------+-----------+---------+------+---------+
2020-09-12 14:24:29 >>> [ WARNING ] Restarting replication. There was either a problem or you aborted.
2020-09-12 14:24:29 >>> [ CRITICAL ] Transaction(s) found running > 60 seconds. COMMIT, ROLLBACK, or kill them. Otherwise, use the less safe --no-transaction-check.
```

# To Do
- Kill long running queries.
- Add multi-threaded replica support.
- Add multi-channel replica support.
- Test python3 compatibility.
