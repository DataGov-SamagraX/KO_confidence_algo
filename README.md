# KO_confidence_algo


This repo is to deploy the confidence algorithm within for the Krushak Odisha DB. This is private DB as it contains the SQL queries (table names and column names) to access the KO data tables


There are 4 main steps to deploy the algo: 
- Clone the github repo for the algorithm 
- Modify the csv file for adding any new sources for each feature
- Change the required input parameters in the [environment file](https://github.com/DataGov-SamagraX/KO_confidence_algo/blob/main/.env) provided. 
- Run the python script and the files with the confidence score will be created in the defined folder location. 

