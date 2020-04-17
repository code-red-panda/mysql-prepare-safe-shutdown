# Pre-Requisites
- [PyMySQL](https://github.com/PyMySQL/PyMySQL) (Python connector)
- [PTable](https://pypi.org/project/PTable/) (Print tabular data in a pretty table)
```
pip install PyMySQL PTable
```

# About
`mysql-prepare-safe-shutdown` will do the following:
- Check if the host is a slave.
	- If yes, stop replication (single channel, single threaded slaves only).
- Check for transactions running > 60 seconds.
	- If yes, print transactional details and exit.
- Set `innodb_max_dirty_pages_pct` to 0.
- Check if `Innodb_buffer_pool_pages_dirty` is < 500 or < 10% of the starting number of dirty pages.
	- If neither condition is met after 1 minute, the tool will continue to prepare for shutdown.
- Set `innodb_fast_shutdown=0`
- Enable `innodb_buffer_pool_dump_at_shutdown` and `innodb_buffer_pool_load_at_startup`.
- Set `innodb_buffer_pool_dump_pct=75`
- Recommend enabling `innodb_buffer_pool_load_at_startup`

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
This tool currently should not prepare:
- Multi-threaded slaves. It will exit if `slave_parallel_workers > 0`.
- Multi-channel slaves. It does not even check for this condition.
