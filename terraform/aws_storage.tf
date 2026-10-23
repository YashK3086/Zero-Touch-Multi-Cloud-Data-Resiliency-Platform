# ============================================================
# AWS — Primary Staging Storage (Free Tier)            [InfraAgent]
# ============================================================

resource "aws_s3_bucket" "sf_primary_stage" {
  bucket        = "sf-dr-primary-stage-${local.env_slug}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "sf_primary_stage" {
  bucket = aws_s3_bucket.sf_primary_stage.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "sf_primary_stage" {
  bucket                  = aws_s3_bucket.sf_primary_stage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sf_primary_stage" {
  bucket = aws_s3_bucket.sf_primary_stage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3: free (KMS would add per-request cost)
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "sf_primary_stage" {
  bucket = aws_s3_bucket.sf_primary_stage.id

  rule {
    id     = "auto-delete-old-objects"
    status = "Enabled"
    filter {}

    expiration {
      days = 1 # Zero-cost guardrail: staged files live max 1 day
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# IAM policy allowing Snowflake (via storage integration role, Phase 2) to use the stage bucket
resource "aws_iam_policy" "snowflake_s3_stage_policy" {
  name        = "snowflake-s3-stage-access-${local.env_slug}"
  description = "Grants Snowflake external stage read/write access to primary S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ObjectAccess"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject", "s3:DeleteObjectVersion"]
        Resource = "${aws_s3_bucket.sf_primary_stage.arn}/*"
      },
      {
        Sid      = "BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.sf_primary_stage.arn
      }
    ]
  })
}
