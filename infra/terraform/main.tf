# Market Intelligence Platform - Terraform Skeleton

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "staging"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

provider "aws" {
  region = var.region
}

# S3 bucket for raw document storage
resource "aws_s3_bucket" "raw_documents" {
  bucket = "mip-raw-${var.environment}"

  tags = {
    Environment = var.environment
    Project     = "market-intelligence"
  }
}

resource "aws_s3_bucket_versioning" "raw_documents" {
  bucket = aws_s3_bucket.raw_documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

# RDS PostgreSQL (placeholder)
# resource "aws_db_instance" "postgres" { ... }

# MSK Kafka cluster (placeholder)
# resource "aws_msk_cluster" "kafka" { ... }

output "raw_bucket_name" {
  value = aws_s3_bucket.raw_documents.bucket
}
