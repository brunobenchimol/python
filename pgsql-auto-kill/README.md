# pgsql-auto-kill 

# Usage:

Connect to PostgreSQL and kill long running sessions
-f <db.conf>       =  Set database variables to connect instead of setting on code
-a, --auto-kill    =  Auto kill query without prompting
-k, --kill-all     =  Kill every Query, default is to kill SELECT only !!!! WARNING: USE WITH CAUTION !!!!
-n, --limit        =  Limit number of query returned, default = 15
-t, --time         =  Time duration interval to check, default = 10
--dry-run          =  Simulation mode, do not kill anything, just check and prints what to do
-v                 =  Verbose
-h, --help         =  Show this help

# Enviroment Variables for container usage or running without db.conf file

**PY_PGKILL_HOST** -- Host or IP Address
**PY_PGKILL_DATABASE** -- Database name
**PY_PGKILL_USER** -- User
**PY_PGKILL_PASSWORD** -- Password
**PY_PGKILL_AUTOKILL** -- Enable Auto Kill flag with "True"

Enviroment PY_PGKILL_DATABASE is a must if you want to use enviroment variables.
If you do not set USER/HOST after setting DATABASE it will assume 'postgres' and '127.0.0.1'.

# Notes

ENV has a higher prioritity than config files
For passwordless connection: With user 'postgres' remove host and password from db.file section 
# remove host and password for unix socket passwordless connection


# Examples 

Running an example dry-run to find which commands will be output do database. Great way to see how things will go without doing it.
```
$ export PY_PGKILL_HOST=localhost
$ export PY_PGKILL_DATABASE=suppliers
$ export PY_PGKILL_USER=postgres
$ export PY_PGKILL_PASSWORD=SecurePas$1
$ export PY_PGKILL_AUTOKILL=False

$ ./pgsql-auto-kill.py -a -t 5 -n 10 --dry-run
SELECT pg_terminate_backend(102830); --- not sending data to database
SELECT pg_terminate_backend(102829); --- not sending data to database
```

If you want to see set verbose mode (add -v to args). You should get the following output:
```
Killing pid 102829 from con_userdb_apl/192.168.1.11 with duration 0:12:04.650878
     Query = SELECT * FROM clients 
SELECT pg_terminate_backend(102829); --- not sending data to database
```