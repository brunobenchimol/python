#!/usr/bin/env python3

"""PostgreSQL Auto Kill"""

from configparser import ConfigParser
import sys
import getopt
import os
import psycopg2
import psycopg2.extras

DBFILE = 'db.conf'
LIMIT = 15
TIME_DURATION = 10
AUTOKILL = False
KILLALL = False
VERBOSE = False
DRY_RUN = False

def get_db_statement():
    """Database Statement - Get Locks/Duration"""
    return   """ SELECT
                pid,
                now() - pg_stat_activity.query_start AS query_duration,
                usename,
                client_addr,
                query,
                wait_event,
                state
             FROM pg_stat_activity
             WHERE (now() - pg_stat_activity.query_start) > interval '""" + str(TIME_DURATION) + """ minutes'; """

def create_config_from_env():
    """Create Config from Enviroment Variables instead of File"""
    env_vars = ["PY_PGKILL_DATABASE", "PY_PGKILL_USER", "PY_PGKILL_HOST", "PY_PGKILL_PASSWORD", "PY_PGKILL_AUTOKILL"]

    config = ConfigParser()
    config['postgresql'] = {}

    for var in env_vars:
        if var in os.environ:
            if var == "PY_PGKILL_AUTOKILL":
                if str(os.getenv(var)).lower() == 'true':
                    global AUTOKILL # pylint: disable=global-statement
                    AUTOKILL = True
            else:
                param = var.split("_")[2].lower()
                config['postgresql'][param] = str(os.getenv(var))

    # Assume defaults value for PY_PGKILL_USER and PY_PGKILL_HOST if nothing is set.
    if "PY_PGKILL_USER" not in os.environ:
        config['postgresql']['user'] = "postgres"
    if "PY_PGKILL_HOST" not in os.environ:
        config['postgresql']['host'] = "127.0.0.1"

    return config

def db_kill_query(cursor, row):
    """Database Kill Query"""
    kill_query = 'SELECT pg_terminate_backend(' + str(row['pid']) + ');'

    if VERBOSE:
        print("Killing pid " + str(row['pid']) + " from " +
              str(row['usename']) + "/" + str(row['client_addr']) +
              " with duration " + str(row['query_duration'])
             )
        print("     Query = " + str(row['query']))

    if DRY_RUN:
        print(kill_query + " --- not sending data to database")
    else:
        cursor.execute(kill_query)

def prompt_to_kill_query(cursor, row):
    """Ask before killing query"""
    print("> pid " + str(row['pid']) + " from " +
          str(row['usename']) + "/" + str(row['client_addr']) +
          " with duration " + str(row['query_duration'])
          )
    print("     Query = " + str(row['query']))

    answer = "invalid"
    while answer not in ["yes", "y", "no", "n"]:
        try:
            answer = input("Kill Query PID ("+str(row['pid'])+") (yes/[no]): ") or "no"
            if answer not in ["yes", "y", "no", "n"]:
                print("Please input valid data")
        except SyntaxError:
            print("Syntax Error")

    if answer in ["y", "yes"]:
        db_kill_query(cursor, row)
    else:
        print("Doing nothing for pid " + str(row['pid']))

def db_run():
    # pylint: disable=too-many-branches
    """ Connect to the PostgreSQL database server """
    conn = None
    # read connection parameters
    params = load_config(DBFILE)
    try: # pylint: disable=too-many-nested-blocks
        # connect to the PostgreSQL server
        if VERBOSE:
            print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        #cur = conn.cursor()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Execute statement
        if (params['user']) != 'postgres':
            if VERBOSE:
                print('User is not postgres, setting r_dba role')
            cur.execute('set role r_dba')

        cur.execute(get_db_statement())
        # fetchmany for LIMIT instead of fetchall
        results = cur.fetchmany(LIMIT)

        for row in results:
            # skip some possible unsafe results
            if str(row['client_addr']) not in ["127.0.0.1", "None"]:
                if KILLALL and AUTOKILL:
                    db_kill_query(cur, row)
                elif KILLALL:
                    prompt_to_kill_query(cur, row)
                elif str(row['query']).startswith("SELECT"):
                    if AUTOKILL:
                        db_kill_query(cur, row)
                    else:
                        prompt_to_kill_query(cur, row)

	      # close the communication with the PostgreSQL
        cur.close()

    #except (Exception, psycopg2.DatabaseError) as error:
    except (psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            if VERBOSE:
                print('Database connection closed.')

def load_config(filename, section='postgresql'):
    """Load configuration / init from Database File"""
    if "PY_PGKILL_DATABASE" in os.environ:
        parser = create_config_from_env()
    else:
        # create a parser
        parser = ConfigParser()
        # read config file
        parser.read(filename)

    # get section, default to postgresql
    dbconfig = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            dbconfig[param[0]] = param[1]
    else:
        raise Exception(f"Section {section} not found in the {filename} file")

    return dbconfig

def printhelp():
    """Help Summary"""
    print('Usage: ' + sys.argv[0] + ' [OPTION]...')
    print('Connect to PostgreSQL and kill long running sessions')
    print('')
    print('-f <db.conf>       =  Set database variables to connect instead of setting on code')
    print('-a, --auto-kill    =  Auto kill query without prompting')
    print('-k, --kill-all     =  Kill every Query, default is to kill SELECT only !!!! WARNING: USE WITH CAUTION !!!!')
    print('-n, --limit        =  Limit number of query returned, default = 15')
    print('-t, --time         =  Time duration interval to check, default = 10')
    print('--dry-run          =  Simulation mode, do not kill anything, just check and prints what to do')
    print('-v                 =  Verbose')
    print('-h, --help         =  Show this help')

def main(argv):
    # pylint: disable=global-statement
    """Main Function"""
    try:
        opts, args = getopt.getopt(argv, "hakvf:n:t:", # pylint: disable=unused-variable
                                   ["help", "dbfile =", "auto-kill", "kill-all", "limit =", "time =", "dry-run"])
    except getopt.GetoptError:
        print("Error reading arguments. Try --help")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            printhelp()
            sys.exit()
        elif opt in ["-f", "--dbfile"]:
            global DBFILE
            DBFILE = arg
        elif opt in ["-a", "--auto-kill"]:
            global AUTOKILL
            AUTOKILL = True
        elif opt in ["-k", "--kill-all"]:
            global KILLALL
            KILLALL = True
        elif opt in ["-n", "--limit"]:
            global LIMIT
            LIMIT = int(arg)
        elif opt in ["-t", "--time"]:
            global TIME_DURATION
            TIME_DURATION = arg
        elif opt in ["-v"]:
            global VERBOSE
            VERBOSE = True
        elif opt in ["--dry-run"]:
            global DRY_RUN
            DRY_RUN = True

if __name__ == "__main__":
    main(sys.argv[1:])

    db_run()
