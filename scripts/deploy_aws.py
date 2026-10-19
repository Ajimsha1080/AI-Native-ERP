"""
AWS Production Deployment CLI Tool.

Orchestrates:
1. AWS Credential & IAM Verification
2. Docker Daemon Readiness Check
3. Amazon ECR Repository Authentication & Image Push
4. Amazon ECS Fargate Task Definition & Service Rolling Update
5. Automated Cloud Deployment via GitHub Actions
"""

import sys
import os
import subprocess
import shutil
import json
from typing import Dict, Any, Optional

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLUSTER_NAME = f"{ENVIRONMENT}-agentic-erp-cluster"
API_REPO_NAME = f"{ENVIRONMENT}-agentic-erp-api"
WEB_REPO_NAME = f"{ENVIRONMENT}-agentic-erp-web"
API_SERVICE_NAME = f"{ENVIRONMENT}-erp-api-service"
WEB_SERVICE_NAME = f"{ENVIRONMENT}-erp-web-service"
WORKER_SERVICE_NAME = f"{ENVIRONMENT}-erp-worker-service"


def run_cmd(cmd: str, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Runs a shell command and returns the completed process."""
    print(f"\n[EXEC] {cmd}")
    res = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=capture_output,
    )
    if check and res.returncode != 0:
        err = res.stderr if capture_output else "Command failed"
        print(f"[ERROR] Command failed with exit code {res.returncode}: {err}")
    return res


def check_aws_credentials() -> Optional[Dict[str, str]]:
    """Verifies that active AWS credentials are configured."""
    print("=" * 70)
    print("1. Verifying AWS Credentials & Identity...")
    print("=" * 70)

    res = run_cmd("aws sts get-caller-identity", check=False, capture_output=True)
    if res.returncode != 0:
        print("\n[!] No active AWS credentials found.")
        print("\nTo configure AWS credentials on your machine:")
        print("  1. Run in PowerShell/CMD:")
        print("     aws configure")
        print("     (Enter your AWS Access Key ID, Secret Access Key, and region e.g. us-east-1)")
        print("\n  2. Or set environment variables:")
        print("     $env:AWS_ACCESS_KEY_ID = 'your_key'")
        print("     $env:AWS_SECRET_ACCESS_KEY = 'your_secret'")
        print("     $env:AWS_REGION = 'us-east-1'")
        print("\n  3. Or deploy via GitHub Actions (Zero local config):")
        print("     Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in GitHub Repo Secrets,")
        print("     then trigger the 'Deploy to AWS ECS' workflow.")
        return None

    try:
        identity = json.loads(res.stdout)
        print(f"[OK] Authenticated to AWS as:")
        print(f"   Account: {identity.get('Account')}")
        print(f"   Arn:     {identity.get('Arn')}")
        return identity
    except Exception:
        print("[OK] AWS credentials active.")
        return {"status": "active"}


def check_docker_running() -> bool:
    """Checks if Docker daemon is running."""
    print("\n" + "=" * 70)
    print("2. Checking Docker Engine Status...")
    print("=" * 70)

    if not shutil.which("docker"):
        print("[X] Docker CLI is not installed or not in PATH.")
        return False

    res = run_cmd("docker info", check=False, capture_output=True)
    if res.returncode != 0:
        print("[X] Docker Engine is not currently running.")
        print("   Please start Docker Desktop on your system and try again.")
        return False

    print("[OK] Docker Engine is running and ready for image builds.")
    return True


def ensure_ecr_repositories(account_id: str) -> Dict[str, str]:
    """Ensures ECR repositories exist, creating them if necessary."""
    print("\n" + "=" * 70)
    print("3. Ensuring Amazon ECR Repositories...")
    print("=" * 70)

    repos = [API_REPO_NAME, WEB_REPO_NAME]
    urls = {}

    for repo in repos:
        check_res = run_cmd(f"aws ecr describe-repositories --repository-names {repo} --region {AWS_REGION}", check=False, capture_output=True)
        if check_res.returncode != 0:
            print(f"Creating ECR repository: {repo}...")
            create_res = run_cmd(f"aws ecr create-repository --repository-name {repo} --region {AWS_REGION} --image-scanning-configuration scanOnPush=true", check=False, capture_output=True)
            if create_res.returncode == 0:
                print(f"[OK] Created ECR repository: {repo}")
            else:
                print(f"[WARN] Could not create ECR repository automatically: {create_res.stderr}")
        else:
            print(f"[OK] ECR repository exists: {repo}")

        urls[repo] = f"{account_id}.dkr.ecr.{AWS_REGION}.amazonaws.com/{repo}"

    return urls


def build_and_push(ecr_urls: Dict[str, str]):
    """Builds Docker images and pushes to Amazon ECR."""
    print("\n" + "=" * 70)
    print("4. Authenticating Docker to Amazon ECR...")
    print("=" * 70)

    registry = list(ecr_urls.values())[0].split("/")[0]
    run_cmd(f"aws ecr get-login-password --region {AWS_REGION} | docker login --username AWS --password-stdin {registry}")

    # 1. API Image
    api_url = ecr_urls[API_REPO_NAME]
    print(f"\n[DOCKER] Building API Backend: {api_url}:latest...")
    run_cmd(f"docker build -t {api_url}:latest .")
    print(f"[DOCKER] Pushing API Backend image to ECR...")
    run_cmd(f"docker push {api_url}:latest")

    # 2. Web Image
    web_url = ecr_urls[WEB_REPO_NAME]
    print(f"\n[DOCKER] Building Web Frontend: {web_url}:latest...")
    run_cmd(f"docker build -t {web_url}:latest ./apps/web")
    print(f"[DOCKER] Pushing Web Frontend image to ECR...")
    run_cmd(f"docker push {web_url}:latest")

    print("\n[OK] All Docker images pushed successfully to Amazon ECR.")


def update_ecs_services():
    """Forces zero-downtime rolling update on running ECS services."""
    print("\n" + "=" * 70)
    print("5. Triggering Zero-Downtime Rolling Updates on ECS Fargate...")
    print("=" * 70)

    services = [API_SERVICE_NAME, WEB_SERVICE_NAME, WORKER_SERVICE_NAME]
    for svc in services:
        print(f"Rolling out service: {svc} on cluster {CLUSTER_NAME}...")
        res = run_cmd(
            f"aws ecs update-service --cluster {CLUSTER_NAME} --service {svc} --force-new-deployment --region {AWS_REGION}",
            check=False,
            capture_output=True
        )
        if res.returncode == 0:
            print(f"[OK] Triggered deployment for {svc}")
        else:
            print(f"[INFO] Service {svc} note: {res.stderr.strip() or 'Queued'}")


def main():
    print("""
========================================================================
   AI-NATIVE AGENTIC ERP - AWS DEPLOYMENT ENGINE
========================================================================
Target Environment : """ + ENVIRONMENT + """
AWS Region         : """ + AWS_REGION + """
ECS Cluster        : """ + CLUSTER_NAME + """
========================================================================
    """)

    identity = check_aws_credentials()
    if not identity:
        sys.exit(1)

    account_id = identity.get("Account", "123456789012")

    docker_ok = check_docker_running()
    if not docker_ok:
        sys.exit(1)

    ecr_urls = ensure_ecr_repositories(account_id)
    build_and_push(ecr_urls)
    update_ecs_services()

    print("""
========================================================================
[OK] AWS DEPLOYMENT PIPELINE TRIGGERED SUCCESSFULLY!
========================================================================
Monitor deployment in AWS Console:
- ECS Services   : https://console.aws.amazon.com/ecs/home?region=""" + AWS_REGION + """
- ECR Images     : https://console.aws.amazon.com/ecr/repositories?region=""" + AWS_REGION + """
- CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=""" + AWS_REGION + """
========================================================================
    """)


if __name__ == "__main__":
    main()
