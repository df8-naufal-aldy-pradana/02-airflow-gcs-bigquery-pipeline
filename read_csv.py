import pandas as pd

dataset_url = f"https://datausa.io/api/data?drilldowns=Nation&measures=Population/{dataset_file}"
api_url = "https://datausa.io/api/data?drilldowns=Nation&measures=Population"

path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
local_file = f"{path_to_local_home}/{parquet_file}"

df = pd.read_json(local_file)
print(df)
# df.to_csv (src_file, index = None)