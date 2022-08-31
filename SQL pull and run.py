import numpy as np
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)

#%%  Declaring all the variables

## locations where the files with confidence scores need to be saved
save_location =  os.getenv('save_location')

## csv file with the SQL code repo
sql_repo_csv_location =  os.getenv('save_location')

## setting the maximum confidence a source can have: 
maximum_confidence_value = float(os.getenv('maximum_confidence_value'))

## setting  the maximum number of iterations in the algo: 
maximum_number_of_iterations =  float(os.getenv('maximum_number_of_iterations'))

## setting the minimum differnce in the trustworthiness scores to be reached to end the algo
minimum_absolute_difference =  float(os.getenv('minimum_absolute_difference'))

# setting the variables for connecting to the DB:
## hostname 
host = os.getenv('host')

##username
user = os.getenv('user')

##password
password=os.getenv('password')

##DB name
database= os.getenv('database')

#%%

## connecting to the DB
mydb = mysql.connector.connect(host = host, user = user , password= password , database= database )


#%% Pre-defined variables

## Function to carry out the iterations of confidence algo 
def carry_out_iterations( data,list_of_cols,t_w,id_colname,gamma): 
    
    """
    Arguments: 
        data : the table serving as input for the confidence algo 
        list_of_cols:  list of column names that serve as unique sources for the data points 
        t_w:  array of initial confidence values (source trustworthiness) for each source. Usually set to 0.5 for each source
        id_colname: Column name with unique id value for each row
        
    Returned values: 
    t_w_df : table with the changing source trustworthiness with each iteration
    train_data_confidence : Final table with the final confidence values for each data point for each source
    
    """
        
    
    max_t_w_value =  0.975
    train_data =  data[list_of_cols].copy()
    
    train_data = train_data.loc[np.sum(~train_data.isna(),axis = 1) > 1,:]
    ## creating empty data frame with same structure as traindata to copy confidence scores 
    
    train_data_confidence =  train_data.copy()
    train_data_confidence.loc[:,:]= 0

    ## calculating (1-t(w)). Carrying out calculation required for the equation
    t_w_inv =  1- t_w
    tau_w =  -np.log(t_w_inv)

    ## creating dataframe that maintains list of confidence values through each iteration
    confidence_iterations = pd.DataFrame(columns =train_data.columns.tolist() + ['iteration'])
    t_w_df = pd.DataFrame(columns = train_data.columns)

    for iteration in range(0,100):

        for col_name in list_of_cols:
            column_matching_df=  train_data_confidence.copy()
            column_matching_df.loc[:,:]= 0
            current_source =  train_data[col_name]

            other_sources_cols = [x for x in list_of_cols if x != current_source.name]

            column_matching_df[col_name] = 1
            for col_name_others in other_sources_cols:
                column_matching_df[col_name_others] = np.where(train_data[col_name_others]==current_source,1,-1)
            column_matching_df[pd.isnull(train_data)]=0

            for col_ii in range(0,column_matching_df.shape[1]):
                column_matching_df.iloc[:,col_ii] = column_matching_df.iloc[:,col_ii] * tau_w[col_ii]

            train_data_confidence[col_name]= np.where(pd.isnull(current_source),np.nan,1/(1 + np.exp( -1 * gamma * ( column_matching_df.sum(axis=1)  ) )))


        ## maintaining record of the trusworthiness scores of websites
        t_w_prev =  t_w.copy()
        t_w_df.loc[iteration]= t_w
        t_w = train_data_confidence.mean()
        t_w [t_w >= max_t_w_value] = max_t_w_value
        t_w_inv =  1- t_w
        tau_w =  -np.log(t_w_inv)

        ## printing itertion number and the trustworthiness score
        print(iteration, np.array(t_w_prev))
        if iteration > 5:
            if np.nansum(np.abs(t_w.values - t_w_prev.values)) < 0.001:
                break
    
    train_data_confidence[id_colname] =  data[id_colname]
    
    return(t_w_df,train_data_confidence )


## Function to get the final confidence values from the source trustworthiness values 
def get_final_confidence(data,list_of_cols, column_to_check_confidence,t_w ,id_colname):
    
    """
    Arguments: 
        data : the table serving as input for the confidence algo 
        list_of_cols:  list of column names that serve as unique sources for the data points 
        column_to_check_confidence:  column for which final confidence needs to be calcuated 
        t_w: trustworthiness score for each source (final values from the iterations)
        id_colname: colum with unqiue id values for each row
        
    Returned values: 
    data  : Table which returns the final confidence scores for the required columns    
    """
        
    train_data =  data[list_of_cols].copy()
    
    column_matching_df =  train_data.copy()
    column_matching_df.loc[:,:]= 0
    
    if (np.isnan(t_w[0])):
        t_w[0] = t_w[1]
    if (np.isnan(t_w[1])):
        t_w[1]= t_w[0]
    
    
    ## calculating (1-t(w)). Carrying out calculation required for the equation
    t_w_inv =  1- t_w
    tau_w =  -np.log(t_w_inv)

    current_source =  data[column_to_check_confidence]

    other_sources_cols = [x for x in list_of_cols ]

    for col_name_others in other_sources_cols:
        column_matching_df[col_name_others] = np.where(train_data[col_name_others]==current_source,1,-1)
    column_matching_df[pd.isnull(train_data)]=0

    for col_ii in range(0,column_matching_df.shape[1]):
        column_matching_df.iloc[:,col_ii] = column_matching_df.iloc[:,col_ii] * tau_w[col_ii]

    final_conf_scores= np.where(pd.isnull(current_source),np.nan,1/(1 + np.exp(-column_matching_df.sum(axis=1))))

    data['final_confidence'] = final_conf_scores

    return(data)


#%% 


## reading the table with the SQL queries for downloading necessary tables 
codes_df = pd.read_csv("sql_code_repo.csv")
codes_df_run = codes_df.loc[codes_df.Multiple_confidence_columns == 1,: ]

for table_no in codes_df_run.index:
    print('Table current :',  table_no , '\n')
    string  = codes_df.loc[table_no,'SQL Code']
    string = string.replace('\n'," ")
    string = string.replace('\t'," ")
    columns = codes_df.loc[table_no,'Columns_list']
    list_of_cols = np.array(columns.split (","))
    
    df = pd.read_sql(string ,con =mydb)
    
    df['id'] = df.index
    df['Krushak_Odisha'] = df.field.combine_first(df.self)
    no_cols =  len(list_of_cols)
    t_w = np.repeat(0.5,no_cols)
    id_colname = 'id'
    gamma = 1
    t_w_df,train_data_confidence = carry_out_iterations( df,list_of_cols,t_w,id_colname, gamma)
    
    column_to_check_confidence = 'Krushak_Odisha'

    data_copy = get_final_confidence(df, column_to_check_confidence ,train_data_confidence ,id_colname)
    df = pd.read_sql(string ,con =mydb)
    table_name_str  = codes_df.loc[table_no,'Field Name']
    df.to_csv( 'data' + table_name_str+str(table_no)+'.csv', encoding = "utf-8")
    
    conf_table = data_copy[['Krushak_Odisha','int_krushk_id'
,'final_confidence']]
    
    conf_table.to_csv( save_location + table_name_str+str(table_no)+'.csv', encoding = "utf-8")