import os
import logging

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from google.cloud import storage
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateExternalTableOperator
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.json as pj
import pyarrow.parquet as pq
import requests
import json
import pandas as pd

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")


api_url = "https://datausa.io/api/data?drilldowns=Nation&measures=Population"
saved_response = "data_usa.json"
saved_csv = saved_response.replace('.json', '.csv')

path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
# path_to_local_home = "/opt/airflow/"
parquet_file = saved_csv.replace('.csv', '.parquet')
BIGQUERY_DATASET = os.environ.get("BIGQUERY_DATASET", 'data_usa')

def fetch_api_task(api_url, save_loc):
    response = requests.get(api_url)
    data = response.json()
    with open(save_loc, 'w') as outfile:
        json.dump(data, outfile)


def save_as_csv(src_file):
    if not src_file.endswith('.json'):
        logging.error("Can only accept source files in CSV format, for the moment")
        return
    table = pj.read_json(src_file)
    table_arr = table['data'].to_numpy()

    list_tbl = list(i for i in table_arr[0])
    df = pd.DataFrame.from_dict(list_tbl)
    df_table = pa.Table.from_pandas(df)
    pv.write_csv(df_table, f"{path_to_local_home}/{saved_csv}")


def format_to_parquet(src_file):
    if not src_file.endswith('.csv'):
        logging.error("Can only accept source files in CSV format, for the moment")
        return
    table = pv.read_csv(src_file)
    pq.write_table(table, src_file.replace('.csv', '.parquet'))


# NOTE: takes 20 mins, at an upload speed of 800kbps. Faster if your internet has a better upload speed
def upload_to_gcs(bucket, object_name, local_file):
    """
    Ref: https://cloud.google.com/storage/docs/uploading-objects#storage-upload-object-python
    :param bucket: GCS bucket name
    :param object_name: target path & file-name
    :param local_file: source path & file-name
    :return:
    """
    # WORKAROUND to prevent timeout for files > 6 MB on 800 kbps upload speed.
    # (Ref: https://github.com/googleapis/python-storage/issues/74)
    storage.blob._MAX_MULTIPART_SIZE = 5 * 1024 * 1024  # 5 MB
    storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024  # 5 MB
    # End of Workaround

    client = storage.Client()
    bucket = client.bucket(bucket)

    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_file)


default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "retries": 1,
}

# NOTE: DAG declaration - using a Context Manager (an implicit way)
with DAG(
    dag_id="data_ingestion_gcs_dag",
    schedule_interval="@daily",
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=['dtc-de'],
) as dag:

    call_dataset_task = PythonOperator(
        task_id="call_dataset_task",
        python_callable=fetch_api_task,
        op_kwargs={
            "api_url": api_url,
            "save_loc": f"{path_to_local_home}/{saved_response}",
        }
    )

    save_as_csv = PythonOperator(
        task_id="save_as_csv",
        python_callable=save_as_csv,
        op_kwargs={
            "src_file": f"{path_to_local_home}/{saved_response}",
        }
    )

    format_to_parquet_task = PythonOperator(
        task_id="format_to_parquet_task",
        python_callable=format_to_parquet,
        op_kwargs={
            "src_file": f"{path_to_local_home}/{saved_csv}",
        },
    )

    local_to_gcs_task = PythonOperator(
        task_id="local_to_gcs_task",
        python_callable=upload_to_gcs,
        op_kwargs={
            "bucket": BUCKET,
            "object_name": f"raw/{parquet_file}",
            "local_file": f"{path_to_local_home}/{parquet_file}",
        },
    )

    bigquery_external_table_task = BigQueryCreateExternalTableOperator(
        task_id="bigquery_external_table_task",
        table_resource={
            "tableReference": {
                "projectId": PROJECT_ID,
                "datasetId": BIGQUERY_DATASET,
                "tableId": "external_table",
            },
            "externalDataConfiguration": {
                "sourceFormat": "PARQUET",
                "sourceUris": [f"gs://{BUCKET}/raw/{parquet_file}"],
            },
        },
    )

    call_dataset_task >> save_as_csv >> format_to_parquet_task >> local_to_gcs_task >> bigquery_external_table_task
