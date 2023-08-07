#!/usr/bin/env python
# coding: utf-8


from datetime import datetime
import configparser

import pandas as pd
import pymysql
import logging
#import sshtunnel
#from sshtunnel import SSHTunnelForwarder
import numpy as np
import os
import logging
import warnings
import time
import threading

# CONFIG
config = configparser.ConfigParser()
config.read('./config.ini')

batch_size = config.getint('APP','batch_size') # this is batch size of Aadhaar
time_limit_queries = config.getint('APP','time_limit_queries') #secs

log_file = config.get('FILES','log_file')

is_ssh_tunnel_required = config.getboolean('SSH', 'is_ssh_tunnel_required')
ssh_host = config.get('SSH','ssh_host')
ssh_username = config.get('SSH','ssh_username')
ssh_password = config.get('SSH','ssh_password')

database_username = config.get('DATABASE','database_username')
database_password = config.get('DATABASE','database_password') 
database_name = config.get('DATABASE','database_name')
localhost = config.get('DATABASE','localhost')
database_port = config.getint('DATABASE','database_port')

input_csv_file = config.get('FILES','input_csv_file')
output_folder = config.get('FILES','output_folder')

warnings.filterwarnings('ignore') # suppress pandas warnings
# logging.basicConfig(filename=log_file, level=logging.INFO)



if is_ssh_tunnel_required:
    import sshtunnel
    from sshtunnel import SSHTunnelForwarder

def open_ssh_tunnel(verbose=False):
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
    if is_ssh_tunnel_required:
        database_port=tunnel.local_bind_port

    connection = pymysql.connect(
        host=localhost,
        user=database_username,
        passwd=database_password,
        db=database_name,
        port=database_port
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
    
    tunnel.stop()


## reading the table with the SQL queries for downloading necessary tables 
codes_df = pd.read_csv(input_csv_file)
codes_df_run = codes_df.loc[codes_df.Multiple_confidence_columns == 1,: ]
codes_df_run = codes_df[(codes_df['Queries to be modified1']) == 1]



if is_ssh_tunnel_required:
    open_ssh_tunnel()
connection = mysql_connect()



def generate_range(n_parts):
    number = 1000000000000
    l = np.linspace(0, number, n_parts+1, dtype=int)[1:]
    prev = str(0).zfill(12)
    res = []
    for x in l:
        res.append(( prev, ('0' * (12 - len(str(x - 1)))) + str(x - 1) ))
        prev = ('0' * (12 - len(str(x)))) + str(x)
        break
    return res

#generate_range(20)


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



if not os.path.exists(f"./{output_folder}"):
    os.makedirs(output_folder)

RANGE = generate_range(batch_size) # this is batch size of Aadhaar

for index, row in codes_df_run.iterrows():
    print('\nTable current :',  index, '\n')
    logging.info(f'\nTable current : {index} on {datetime.now()} \n')
    query_template = codes_df.loc[index,'Final Query']
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




mysql_disconnect(connection)
close_ssh_tunnel()

