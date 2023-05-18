#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from datetime import datetime

import pandas as pd
import pymysql
import logging
import sshtunnel
from sshtunnel import SSHTunnelForwarder
import numpy as np
import os
import logging
import warnings
import time
import threading

# CONFIG
batch_size = 20 # this is batch size of Aadhaar
time_limit_queries = 60 * 60 * 2 #secs
log_file = 'TestCSVlogs.log'
ssh_host = '20.193.244.68'
ssh_username = 'audit'
#ssh_password = 
database_username = 'kauditU1'
#database_password = 
database_name = 'dss_production'
localhost = '127.0.0.1'
input_csv_file = 'sql_code_repo_v5.csv'
output_folder = 'SQL_dump'


warnings.filterwarnings('ignore') # suppress pandas warnings
logging.basicConfig(filename=log_file, level=logging.INFO)


def open_ssh_tunnel(verbose=False):
    """Open an SSH tunnel and connect using a username and password.
    
    :param verbose: Set to True to show logging
    :return tunnel: Global SSH tunnel connection
    """
    
    if verbose:
        sshtunnel.DEFAULT_LOGLEVEL = logging.DEBUG
    
    global tunnel
    tunnel = SSHTunnelForwarder(
        (ssh_host, 22),
        ssh_username = ssh_username,
        ssh_password = ssh_password,
        remote_bind_address = (localhost, 3306)
    )
    
    tunnel.start()

def mysql_connect():
    """Connect to a MySQL server using the SSH tunnel connection
    
    :return connection: Global MySQL database connection
    """
    
    connection = pymysql.connect(
        host=localhost,
        user=database_username,
        passwd=database_password,
        db=database_name,
        port=tunnel.local_bind_port
    )
    return connection

def run_query(sql, conn):
    """Runs a given SQL query via the global database connection.
    
    :param sql: MySQL query
    :return: Pandas dataframe containing results
    """
    
    return pd.read_sql_query(sql, conn)

def mysql_disconnect(conn):
    """Closes the MySQL database connection.
    """
    
    conn.close()

def close_ssh_tunnel():
    """Closes the SSH tunnel connection.
    """
    
    tunnel.close


# In[ ]:


## reading the table with the SQL queries for downloading necessary tables 
codes_df = pd.read_csv(input_csv_file)
codes_df_run = codes_df.loc[codes_df.Multiple_confidence_columns == 1,: ]
codes_df_run = codes_df[(codes_df['Queries to be modified']) == 1]


# In[ ]:


open_ssh_tunnel()
# connection = mysql_connect()


# In[ ]:


def generate_range(n_parts):
    number = 1000000000000
    l = np.linspace(0, number, n_parts+1, dtype=int)[1:]
    prev = str(0).zfill(12)
    res = []
    for x in l:
        res.append(( prev, ('0' * (12 - len(str(x - 1)))) + str(x - 1) ))
        prev = ('0' * (12 - len(str(x)))) + str(x)
    return res

# generate_range(20)


# In[ ]:


def do_thread_work(query, timeout):
    '''
    it will sleep for specified time then it will try to kill the given query
    '''
    print(f'sleeping for {timeout}secs')
    time.sleep(timeout)
    print('sleep complete')
    conn = mysql_connect()
    query = query.rstrip(';')
    print('query thread', query)
    with conn.cursor() as cursor:
        sql = f"""
            SELECT id FROM INFORMATION_SCHEMA.PROCESSLIST WHERE INFO LIKE "{query}%"
        """
        cursor.execute(sql)
        result = cursor.fetchone()
        if result:
            print(f'killing query id {result[0]}')
            sql = f"kill {result[0]}"
            cursor.execute(sql)
    conn.close()


# In[ ]:


if not os.path.exists(f"./{output_folder}"):
    os.makedirs(output_folder)

RANGE = generate_range(batch_size) # this is batch size of Aadhaar

for index, row in codes_df_run.iterrows():
    print('\nTable current :',  index, '\n')
    logging.info(f'\nTable current : {index} on {datetime.now()} \n')
    query_template = codes_df.loc[index,'Optimized Query']
    query_template = query_template.replace('\n'," ")
    query_template = query_template.replace('\t'," ")
    # columns = codes_df.loc[index,'Columns_list']
    # list_of_cols = np.array(columns.split (","))

    # create output path if exist then do wipe
    output_path = f'./{output_folder}/' + row['Parent Label'] + '_' + row['Field Name'] +'.csv'
    open(output_path, 'w').close()
    is_header_printed = False
    
    for i, r in enumerate(RANGE):
        print('Starting for range: ' + str(r) + ' For Sr. no. ' + str(row['SrNo']))
        logging.info('Starting for range: ' + str(r) + ' For Sr. no. ' + str(row['SrNo']) + f' on {datetime.now()}')
        query = query_template.replace('{{X}}', r[0]).replace('{{Y}}', r[1])
        
        # thread for time limiting the query
        x = threading.Thread(target=do_thread_work, daemon=True, args=[query, time_limit_queries])
        x.start()
        
        connection = mysql_connect()
        try:
            df = run_query(query, connection)
            if not is_header_printed:
                df.to_csv(output_path, mode='a', header=True, encoding='utf-8', index=False)
                is_header_printed = True
            else:
                df.to_csv(output_path, mode='a', header=False, encoding='utf-8', index=False)
            print('Completed for range: ' + str(r) + ' For Sr. no. ' + str(row['SrNo']))
            logging.info('Completed for range: ' + str(r) + ' For Sr. no. ' + str(row['SrNo']) + f' on {datetime.now()}')    
        except Exception as e:
            # print(f"Skipping Query r. no. {row['SrNo']} because timeout")
            print(f"Skipping for range: {r} For Sr. no. {row['SrNo']} because of timeout")
            logging.error(f"Skipping for range: {r} For Sr. no. {row['SrNo']} because of timeout")
        connection.close()


# In[ ]:


# mysql_disconnect(connection)
close_ssh_tunnel()

