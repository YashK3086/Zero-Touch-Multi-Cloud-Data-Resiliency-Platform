# ============================================================
# Snowpipe & Ingestion Objects on Primary (AWS)
# ============================================================

# Snowflake Stage pointing to AWS S3 Bucket
resource "snowflake_stage" "dr_s3_stage" {
  name     = "SF_PRIMARY_S3_STAGE"
  database = snowflake_database.dr_database.name
  schema   = snowflake_schema.dr_schema.name
  url      = "s3://${aws_s3_bucket.sf_primary_stage.bucket}/financial_data/"
  comment  = "External stage pointing directly to Primary S3 bucket"
}

# Snowflake Target Table for PaySim Transactions
resource "snowflake_table" "dr_financial_table" {
  database = snowflake_database.dr_database.name
  schema   = snowflake_schema.dr_schema.name
  name     = "FINANCIAL_TRANSACTIONS"
  comment  = "PaySim financial transactions table replicated across AWS and Azure"

  column {
    name = "STEP"
    type = "NUMBER(38,0)"
  }
  column {
    name = "TYPE"
    type = "VARCHAR(32)"
  }
  column {
    name = "AMOUNT"
    type = "NUMBER(18,2)"
  }
  column {
    name = "NAMEORIG"
    type = "VARCHAR(64)"
  }
  column {
    name = "OLDBALANCEORG"
    type = "NUMBER(18,2)"
  }
  column {
    name = "NEWBALANCEORIG"
    type = "NUMBER(18,2)"
  }
  column {
    name = "NAMEDEST"
    type = "VARCHAR(64)"
  }
  column {
    name = "OLDBALANCEDEST"
    type = "NUMBER(18,2)"
  }
  column {
    name = "NEWBALANCEDEST"
    type = "NUMBER(18,2)"
  }
  column {
    name = "ISFRAUD"
    type = "NUMBER(38,0)"
  }
  column {
    name = "ISFLAGGEDFRAUD"
    type = "NUMBER(38,0)"
  }
  column {
    name = "INGESTED_AT"
    type = "TIMESTAMP_LTZ(9)"
  }
}

# Real Snowpipe for continuous auto-ingestion into FINANCIAL_TRANSACTIONS
resource "snowflake_pipe" "dr_financial_pipe" {
  name        = "SF_FINANCIAL_PIPE"
  database    = snowflake_database.dr_database.name
  schema      = snowflake_schema.dr_schema.name
  auto_ingest = true
  comment     = "Production Snowpipe auto-ingesting S3 Parquet/CSV files into DR database"

  copy_statement = "COPY INTO SF_DR_DEMO_DB.DR_STAGING.FINANCIAL_TRANSACTIONS FROM @SF_DR_DEMO_DB.DR_STAGING.SF_PRIMARY_S3_STAGE FILE_FORMAT = (TYPE = 'PARQUET') MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
  depends_on     = [snowflake_table.dr_financial_table]
}
# S3 Event Notification -> Snowflake Snowpipe SQS Channel
resource "aws_s3_bucket_notification" "sf_pipe_notification" {
  bucket = aws_s3_bucket.sf_primary_stage.id

  queue {
    queue_arn     = snowflake_pipe.dr_financial_pipe.notification_channel
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "financial_data/"
  }

  depends_on = [snowflake_pipe.dr_financial_pipe]
}
