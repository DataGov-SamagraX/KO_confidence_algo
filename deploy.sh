python3 -m venv venv
source venv/bin/activate

pip install sshtunnel
pip install numpy 
pip install pandas 
pip install logging
pip install mysql-connector-python

python sql_pull_save_code.py
python confidence_algo_run_script.py