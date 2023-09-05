#!/usr/bin/env python
# coding: utf-8

from datetime import datetime
import configparser
import pandas as pd
import pymysql
import logging
import numpy as np
import os
import warnings
import time
import threading
import concurrent.futures

# CONFIG
config = configparser.ConfigParser()
config.read('./config.ini')

batch_size = config.getint('APP', 'batch_size')
time_limit_queries = config.getint('APP', 'time_limit_queries')
log_file = config.get('FILES', 'log_file')
is_ssh_tunnel_required = config.getboolean('SSH', 'is_ssh_tunnel_required')
ssh_host = config.get('SSH', 'ssh_host')
ssh_username = config.get('SSH', 'ssh_username')
ssh_password = config.get('SSH', 'ssh_password')
database_username = config.get('DATABASE', 'database_username')
database_password = config.get('DATABASE', 'database_password')
database_name = config.get('DATABASE', 'database_name')
database_port = config.getint('DATABASE', 'database_port')
localhost = config.get('DATABASE', 'localhost')
input_csv_file = config.get('FILES', 'input_csv_file')
output_folder = config.get('FILES', 'output_folder')

warnings.filterwarnings('ignore')
logging.basicConfig(filename=log_file, level=logging.INFO, force=True)


if is_ssh_tunnel_required:
    from sshtunnel import SSHTunnelForwarder

    def open_ssh_tunnel(verbose=False):
        global tunnel
        tunnel = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_username,
            ssh_password=ssh_password,
            remote_bind_address=(localhost, 3306)
        )
        tunnel.start()

def mysql_connect():
    global database_port
    if is_ssh_tunnel_required:
        database_port = tunnel.local_bind_port
    connection = pymysql.connect(
        host=localhost,
        user=database_username,
        passwd=database_password,
        db=database_name,
        port=database_port
    )
    return connection

def run_query(sql, conn):
    try:
        return pd.read_sql_query(sql, conn)
    except pymysql.MySQLError as e:
        logging.error(f"SQL Error: {e}")
        print(f"SQL Error: {e}")
        return None

def mysql_disconnect(conn):
    try:
        conn.close()
    except pymysql.err.Error as e:
        if str(e) == "Already closed":
            pass
        else:
            raise

def close_ssh_tunnel():
    tunnel.stop()

def generate_range(n_parts):
    number = 1000000000000
    l = np.linspace(0, number, n_parts + 1, dtype=int)[1:]
    prev = str(0).zfill(12)
    res = []
    for x in l:
        res.append((prev, ('0' * (12 - len(str(x - 1)))) + str(x - 1)))
        prev = ('0' * (12 - len(str(x)))) + str(x)
    return res

# Main Execution
if is_ssh_tunnel_required:
    open_ssh_tunnel()
connection = mysql_connect()

codes_df = pd.read_csv(input_csv_file)
codes_df_run = codes_df.loc[codes_df['Queries to be modified'] == 1,:]

if not os.path.exists(f"./{output_folder}"):
    os.makedirs(output_folder)

RANGE = generate_range(batch_size)

for index, row in codes_df_run.iterrows():
    query_template = row['Final Query'].replace('\n', " ").replace('\t', " ")
    output_path = f'./{output_folder}/' + row['Parent Label'] + '_' + row['Field Name'] + '.csv'
    open(output_path, 'w').close()
    is_header_printed = False

    for i, r in enumerate(RANGE):
        query = query_template.replace('{{X}}', r[0]).replace('{{Y}}', r[1])

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_query, query, connection)
            try:
                df = future.result(timeout=time_limit_queries)
                if not is_header_printed:
                    df.to_csv(output_path, mode='a', header=True, encoding='utf-8', index=False)
                    is_header_printed = True
                else:
                    df.to_csv(output_path, mode='a', header=False, encoding='utf-8', index=False)
                print('Completed for range:', r, 'For Sr. no.', row['SrNo'])
                logging.info('Completed for range: ' + str(r) + ' For Sr. no. ' + str(row['SrNo']) + f' on {datetime.now()}')

            except concurrent.futures.TimeoutError:
                print(f"Skipping for range: {r} For Sr. no. {row['SrNo']} because of timeout")
                logging.error(f"Skipping for range: {r} For Sr. no. {row['SrNo']} because of timeout")
            except pymysql.MySQLError as e:
                print(f"SQL Error for range: {r} For Sr. no. {row['SrNo']}. Error: {e}")
                logging.error(f"SQL Error for range: {r} For Sr. no. {row['SrNo']}. Error: {e}")

mysql_disconnect(connection)
if is_ssh_tunnel_required:
    close_ssh_tunnel()
