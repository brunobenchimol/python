#!/usr/bin/env python3

import sys, getopt, os
import psycopg2, psycopg2.extras
from configparser import ConfigParser

dbfile = 'db.conf'
limit = 15
time_duration = 10
autokill = False
killall = False
verbose = False
dry_run = False


def get_db_statement():
 return           """ SELECT
                     pid,
                     now() - pg_stat_activity.query_start AS query_duration,
                     usename,
                     client_addr,
                     query,
                     wait_event,
                     state
                  FROM pg_stat_activity
                  WHERE (now() - pg_stat_activity.query_start) > interval '""" + str(time_duration) + """ minutes'; """ 

def create_config_from_env():
   ENV_VARS = ["PY_PGKILL_DATABASE", "PY_PGKILL_USER", "PY_PGKILL_HOST", "PY_PGKILL_PASSWORD", "PY_PGKILL_AUTOKILL"] 

   config = ConfigParser()
   config['postgresql'] = {}

   for var in ENV_VARS:
       if var in os.environ:
          if var == "PY_PGKILL_AUTOKILL":
             if "true" == str(os.getenv(var)).lower():
               global autokill
               autokill = True
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
   kill_query = 'SELECT pg_terminate_backend(' + str(row['pid']) + ');'
   
   if verbose:
      print("Killing pid " + str(row['pid']) + " from " + str(row['usename']) + "/" + str(row['client_addr']) + " with duration " + str(row['query_duration']))
      print("     Query = " + str(row['query']))
      
   if dry_run:
      print(kill_query + " --- not sending data to database")
   else:
      cursor.execute(kill_query)
   
def prompt_to_kill_query(cursor,row):
   kill_query = 'SELECT pg_terminate_backend(' + str(row['pid']) + ');'

   print("> pid " + str(row['pid']) + " from " + str(row['usename']) + "/" + str(row['client_addr']) + " with duration " + str(row['query_duration']))
   print("     Query = " + str(row['query']))
   
   answer = "invalid"
   while answer not in ["yes", "y", "no", "n"]:
      try:
         answer = input("Kill Query PID ("+str(row['pid'])+") (yes/[no]): ") or "no"
         if answer not in ["yes", "y", "no", "n"]:
            print("Please input valid data")
      except SyntaxError:
         print("Syntax Error")
   
   if answer == 'y' or answer == 'yes':
      db_kill_query(cursor,row)
   else:
      print("Doing nothing for pid " + str(row['pid']))

def db_run():
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = load_config(dbfile)

        # connect to the PostgreSQL server
        if verbose:
            print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)
		
        # create a cursor
        #cur = conn.cursor()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

   # Execute statement
        if (params['user']) != 'postgres':
           if verbose:
               print('User is not postgres, setting r_dba role')
           cur.execute('set role r_dba')
        
        cur.execute(get_db_statement())
        # fetchmany for LIMIT instead of fetchall
        results = cur.fetchmany(limit)
 
        for row in results:
           # skip some possible unsafe results
           if str(row['client_addr']) not in ["127.0.0.1", "None"]:
               if killall and autokill:
                  db_kill_query(cur,row)
               elif killall:
                  prompt_to_kill_query(cur,row)
               elif str(row['query']).startswith("SELECT"):
                     if autokill:
                        db_kill_query(cur,row)
                     else:
                        prompt_to_kill_query(cur,row)

	# close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            if verbose:
               print('Database connection closed.')

def load_config(filename, section='postgresql'):
  
   if "PY_PGKILL_DATABASE" in os.environ:
      parser = create_config_from_env()
   else:
      # create a parser
      parser = ConfigParser()
      # read config file
      parser.read(filename)
      
   # get section, default to postgresql
   db = {}
   if parser.has_section(section):
       params = parser.items(section)
       for param in params:
           db[param[0]] = param[1]
   else:
       raise Exception('Section {0} not found in the {1} file'.format(section, filename))
    
   return db

def printhelp():
   print ('Usage: ' + sys.argv[0] + ' [OPTION]...')
   print ('Connect to PostgreSQL and kill long running sessions')
   print ('')
   print ('-f <db.conf>       =  Set database variables to connect instead of setting on code')
   print ('-a, --auto-kill    =  Auto kill query without prompting')
   print ('-k, --kill-all     =  Kill every Query, default is to kill SELECT only !!!! WARNING: USE WITH CAUTION !!!!')
   print ('-n, --limit        =  Limit number of query returned, default = 15')
   print ('-t, --time         =  Time duration interval to check, default = 10')
   print ('--dry-run          =  Simulation mode, do not kill anything, just check and prints what to do')
   print ('-v                 =  Verbose')
   print ('-h, --help         =  Show this help')

def main(argv):
   
   try:
      opts, args = getopt.getopt(argv, "hakvf:n:t:", ["help","dbfile =","auto-kill", "kill-all", "limit =", "time =", "dry-run"])
   except getopt.GetoptError:
      print ("Error reading arguments. Try --help")
      sys.exit(2)
   for opt, arg in opts:
      if opt in ["-h", "--help"]:
         printhelp()
         sys.exit()
      elif opt in ["-f", "--dbfile"]:
         global dbfile
         dbfile = arg
      elif opt in ["-a", "--auto-kill"]:
         global autokill
         autokill = True
      elif opt in ["-k", "--kill-all"]:
         global killall
         killall = True
      elif opt in ["-n", "--limit"]:
         global limit
         limit = int(arg)
      elif opt in ["-t", "--time"]:
         global time_duration
         time_duration = arg
      elif opt in ["-v"]:
         global verbose
         verbose = True 
      elif opt in ["--dry-run"]:
         global dry_run
         dry_run = True
      
if __name__ == "__main__":
   main(sys.argv[1:])

   db_run() 