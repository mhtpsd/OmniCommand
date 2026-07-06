"""
integrations/bigquery_client.py
---------------------------------
Persist every processed risk-score batch into BigQuery as a historical
log, and provide a query function for the dashboard's trend charts. This
is the file that satisfies the hackathon's GCP data-layer requirement.

ONE-TIME SETUP (do this before writing any code):
1. Create/select a GCP project, enable the BigQuery API.
2. Authenticate: `gcloud auth application-default login`
   (or set GOOGLE_APPLICATION_CREDENTIALS in .env to a service-account
   JSON key with the "BigQuery Data Editor" role).
3. Create the dataset + table once:
     bq mk --dataset {GCP_PROJECT_ID}:omnicommand
     bq mk --table {GCP_PROJECT_ID}:omnicommand.sensor_risk_history \
       pipe_section:STRING,risk_score:FLOAT,risk_level:STRING,\
       avg_pressure:FLOAT,burst_count:INTEGER,updated_at:TIMESTAMP
   (Free tier -- 1 TiB queries/month, 10 GB storage/month -- comfortably
   covers a hackathon demo.)
"""

from functools import lru_cache

from google.cloud import bigquery

from config import settings
from models.schemas import RiskScore


@lru_cache(maxsize=1)
def get_bigquery_client() -> bigquery.Client:
    return bigquery.Client(project=settings.GCP_PROJECT_ID)


def insert_batch(scores: list[RiskScore]) -> None:
    """Historical log -- supplementary, not the critical path. Any failure
    here (bad credentials, no project configured, network hiccup) must
    never crash the live Kafka -> Redis -> dashboard pipeline.

    Uses load_table_from_json (batch load API) instead of insert_rows_json
    (streaming API) because streaming inserts require billing to be enabled;
    the batch load API is available on the free tier.
    """
    if not scores:
        return
    if not settings.GCP_PROJECT_ID:
        print("[bigquery] GCP_PROJECT_ID not set -- skipping historical insert")
        return

    table_id = f"{settings.GCP_PROJECT_ID}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}"
    rows = [s.model_dump(mode="json") for s in scores]

    # Convert datetime objects to ISO strings for JSON serialisation
    for row in rows:
        if hasattr(row.get("updated_at"), "isoformat"):
            row["updated_at"] = row["updated_at"].isoformat()

    try:
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = get_bigquery_client().load_table_from_json(rows, table_id, job_config=job_config)
        job.result()  # blocks until the load job finishes
        print(f"[bigquery] inserted {len(rows)} rows into {table_id}")
    except Exception as exc:
        print(f"[bigquery] failed to insert batch: {exc}")


def query_recent_history(pipe_section: str, hours: int = 24) -> list[dict]:
    """Backs GET /api/history/{pipe_section} in api/routes_risk.py."""
    table_id = f"{settings.GCP_PROJECT_ID}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}"
    query = f"""
        SELECT pipe_section, risk_score, risk_level, avg_pressure,
               burst_count, updated_at
        FROM `{table_id}`
        WHERE pipe_section = @pipe_section
          AND updated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
        ORDER BY updated_at ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("pipe_section", "STRING", pipe_section),
            bigquery.ScalarQueryParameter("hours", "INT64", hours),
        ]
    )

    client = get_bigquery_client()
    result = client.query(query, job_config=job_config).result()
    return [dict(row) for row in result]
