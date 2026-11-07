# AWS deployment guide

Region used below: `ap-south-1` (Mumbai). Replace `<ACCOUNT_ID>` with your 12-digit AWS account id.
Do these in order. **Do step 0 first**: AWS charges for resources you forget.

## 0. Safety first
1. Create an AWS account, enable MFA on the root user, then create an admin IAM user/role for daily work and stop using root.
2. Billing → Budgets → create a **monthly cost budget** (e.g. ₹500) with email alerts at 50% and 100%.
3. Install AWS CLI v2 and run `aws configure` (or `aws sso login`).

---
## Path A: one EC2 server with Docker Compose (cheapest, good for a demo)

Cost: roughly a t3.small (~₹1,500 to 1,800/month if left on; stop it when not demoing).

1. **S3 bucket** for images: `aws s3 mb s3://krishisense-<yourname>-scans --region ap-south-1`; keep "Block all public access" on.
2. **IAM role for EC2**: create role `krishisense-ec2` (trusted entity: EC2) with an inline policy:
   ```json
   {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:PutObject","s3:GetObject"],
    "Resource":"arn:aws:s3:::krishisense-<yourname>-scans/*"}]}
   ```
3. **Launch EC2**: Ubuntu 24.04, t3.small, 20 GB disk, attach the role. Security group: allow 22 (your IP only), 80 and 443.
4. SSH in and install Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker ubuntu && newgrp docker
   ```
5. Copy the project (`git clone` your repo or `scp`), then `cp .env.example .env` and set:
   `DB_PASSWORD`, `JWT_SECRET`, `DEV_OTP_ECHO=false`, `S3_BUCKET=krishisense-<yourname>-scans`, `CORS_ORIGINS=http://<your-ip>`.
6. In `docker-compose.yml`, change the frontend port mapping from `"3000:80"` to `"80:80"`, and remove the public `ports` of `db`/`ml_service`/`backend` if you want only the web port open (the security group already blocks them).
7. `docker compose up -d --build`, then open `http://<EC2 public IP>`.
8. HTTPS: point a domain at the instance (Elastic IP), install Caddy or Nginx + certbot in front of port 80.
9. Put the ingest job on cron: `0 7 * * * cd /home/ubuntu/krishisense && docker compose --profile jobs run --rm ingest`.

Note: `DEV_OTP_ECHO=false` means nobody can log in until you wire up SMS (`backend/app/services/sms.py`). For a private demo, keep it `true` but share the URL only with people you trust.

---
## Path B: ECS Fargate + RDS + ALB (the "proper" architecture)

Rough monthly cost if left running: ALB ~₹1,500, Fargate (3 small tasks) ~₹3,000 to 4,000, RDS t4g.micro ~₹1,200 to 1,500. **Tear down after demos** (step 12).

### 1. Network
Use the default VPC for learning. Create security groups:
- `sg-alb`: inbound 80/443 from anywhere.
- `sg-app`: inbound 80 and 8000 and 8001 only from `sg-alb` and from itself.
- `sg-db`: inbound 3306 only from `sg-app`.

### 2. S3 buckets
`krishisense-<name>-scans` (images) and optionally `krishisense-<name>-data` (raw ingestion files and models). Block public access.

### 3. RDS MySQL
Create MySQL 8.4, `db.t4g.micro`, 20 GB, not publicly accessible, security group `sg-db`, database name `krishisense`, user `ks`.
Connection string: `mysql+pymysql://ks:<password>@<rds-endpoint>:3306/krishisense?charset=utf8mb4`.

### 4. Secrets
Store in AWS Secrets Manager (or SSM Parameter Store, cheaper): `krishisense/DATABASE_URL`, `krishisense/JWT_SECRET`, `krishisense/DATA_GOV_API_KEY`.

### 5. ECR repositories
```bash
for r in backend ml_service frontend pipelines; do aws ecr create-repository --repository-name krishisense-$r --region ap-south-1; done
```

### 6. Build and push images (first time, manually)
```bash
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com
for r in backend ml_service frontend pipelines; do
  docker build -t krishisense-$r ./$r
  docker tag krishisense-$r:latest <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/krishisense-$r:latest
  docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/krishisense-$r:latest
done
```
The `frontend` image's nginx proxies `/api/` to a host called `backend` (used by Docker Compose). On AWS the ALB routes `/api/*` to the backend directly, so that block is never hit and the container starts fine without it.

### 7. The ML models on AWS
The ML service reads models from `MODELS_DIR`. Simplest options:
- **Bake them into the image**: remove `models/*` from `.gitignore` for your private repo, and add `COPY ../models /models` by building the ml_service image from the repo root with `-f ml_service/Dockerfile` (adjust the COPY paths). Simple; rebuild to update the model.
- **Or** download from S3 at container start (add 5 lines to `app.py` `load_models()` using `boto3.download_file`) and give the task role `s3:GetObject`. Better for the weekly retrain.

### 8. IAM roles
- **Task execution role** `ecsTaskExecutionRole` (AWS managed policy `AmazonECSTaskExecutionRolePolicy` + `secretsmanager:GetSecretValue` on your secrets).
- **Task role** `krishisense-task-role` for the backend: `s3:PutObject/GetObject` on the scans bucket (and `sns:Publish` if you use SMS).

### 9. ECS cluster, task definitions, services
- Create cluster `krishisense` (Fargate).
- Task definitions (Fargate, Linux/X86_64):
  | Service | Container port | CPU / memory | Env / secrets |
  |---|---|---|---|
  | `backend` | 8000 | 0.5 vCPU / 1 GB | `DATABASE_URL`, `JWT_SECRET` (secrets); `S3_BUCKET`, `AWS_REGION`, `ML_SERVICE_URL=http://ml.krishisense.local:8001`, `DEV_OTP_ECHO=false`, `SEED_DEMO_DATA=false`, `CORS_ORIGINS=https://yourdomain` |
  | `ml_service` | 8001 | 1 vCPU / 2 GB | `MODELS_DIR=/models` |
  | `frontend` | 80 | 0.25 vCPU / 0.5 GB | none |
- For `backend` → `ml_service` communication use **ECS Service Connect** or Cloud Map service discovery (e.g. name `ml.krishisense.local`), and set `ML_SERVICE_URL` accordingly.
- Create three services (desired count 1), security group `sg-app`, attach to the ALB target groups below.

### 10. Load balancer
Application Load Balancer, internet-facing, `sg-alb`. Target groups (type IP):
- `tg-frontend` (port 80, health check `/`)
- `tg-backend` (port 8000, health check `/api/health`)
Listener rules: `/api/*` → `tg-backend`, default → `tg-frontend`.
For HTTPS: request a free certificate in ACM for your domain, add a 443 listener, redirect 80 → 443, and point your domain (Route 53 or your registrar) to the ALB.

### 11. Scheduled jobs (the data-engineering part)
Use **EventBridge Scheduler** → target "ECS RunTask":
- Daily 07:00 IST (cron `30 1 * * ? *` UTC): task definition `ingest` (image `krishisense-pipelines`, secrets `DATABASE_URL`, `DATA_GOV_API_KEY`, env `S3_BUCKET=<data bucket>`).
- Daily 07:30 IST (cron `0 2 * * ? *` UTC, after ingest): task definition `alerts` (backend image, command `python -m app.jobs.run_alerts`, same secrets as the backend, task role with `sns:Publish`). See the section "SMS and push price alerts" below.
- Weekly: task definition `retrain` (image `krishisense-ml_service`, command `python train_price.py --out /models`, plus a way to publish the model, see step 7).
Add a CloudWatch alarm on the log group of `ingest` for the string `ERROR` and send it to an SNS email topic. That is your pipeline failure alert.

### 12. Monitoring and cost control
- CloudWatch Logs are on by default for ECS tasks (awslogs driver). Add alarms: ALB `HTTPCode_Target_5XX_Count`, ECS service CPU > 80%.
- **After a demo**: set service desired counts to 0, stop RDS (it restarts automatically after 7 days), delete the ALB if you will not use it for days. Delete everything when finished.

### 13. CI/CD with GitHub Actions
The workflow `.github/workflows/deploy.yml` builds the images, pushes them to ECR and forces a new ECS deployment on every push to `main`.
One-time setup:
1. IAM → Identity providers → add `token.actions.githubusercontent.com` (audience `sts.amazonaws.com`).
2. Create a role `github-deploy` trusted by that provider, restricted to your repo (`repo:<github-user>/<repo>:ref:refs/heads/main`), with permissions for ECR push and `ecs:UpdateService`.
3. In the GitHub repo → Settings → Secrets and variables → Actions: add secret `AWS_ROLE_ARN` (the role's ARN) and variables `AWS_REGION`, `ECS_CLUSTER`.
No long-lived AWS keys are stored anywhere.

## SMS and push price alerts (Amazon SNS + EventBridge)
How it works: the daily `alerts` job reads every active alert, compares it with the latest mandi price, and notifies the farmer
once when the condition becomes true (price above/below a limit, or rises/falls by a percentage in 3 days). It re-arms when the
condition clears. A failed delivery is retried on the next run.

**SMS through Amazon SNS** (`SMS_PROVIDER=sns`)
1. Pick a region where SNS SMS is supported for India (the app defaults to `ap-south-1`; check the SNS SMS supported-regions list).
2. New AWS accounts start in the **SMS sandbox**: you can only text numbers you verify (SNS console → Text messaging (SMS) → Sandbox destination phone numbers). Request production access to leave the sandbox.
3. Set a monthly **SMS spend limit** (SNS → Text messaging → Account spend limit) so a bug cannot run up a bill.
4. **India needs DLT registration** (TRAI rules). Register an entity, a sender id and message templates with a telecom operator's DLT portal. Then set `SNS_SENDER_ID`, `SNS_ENTITY_ID`, `SNS_TEMPLATE_ID`. SMS text must match an approved template, so register the wording from `SMS_TEMPLATES` in `backend/app/services/alert_dispatch.py` (the `{...}` parts are the variables). This takes days to weeks; AWS rules change, so confirm the current steps in the SNS documentation.
5. IAM: add to the task role used by the backend and the `alerts` task:
   `{"Effect":"Allow","Action":"sns:Publish","Resource":"*"}` (SNS direct-to-phone publishes have no topic ARN; scope it as AWS allows).
6. Test: log in, open Alerts, press "Send a test message". Check CloudWatch Logs for `SNS publish failed` if nothing arrives.
Rough cost: SMS to India is billed per message (a fraction of a rupee to a rupee or so, depending on the route). Check the SNS pricing page.

**Phone notifications (Web Push, not an AWS service)**
1. `python backend/scripts/generate_vapid.py`, then store the keys as secrets (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`).
2. Needs HTTPS (ACM certificate on the ALB). `http://localhost` also works for development.
3. Farmers open Alerts and press the notification button once per device. Android Chrome works directly; on iPhone the app must first be added to the home screen (iOS 16.4+).
Push is free, so it is the default channel; SMS reaches farmers without smartphones data or without the app installed.

**Schedule (EventBridge Scheduler → ECS RunTask)**
Create a schedule with cron `0 2 * * ? *` (07:30 IST), target "ECS RunTask", cluster `krishisense`, task definition `krishisense-alerts`,
launch type Fargate, same subnets/security group as the backend. The task definition reuses the backend image with the command
override `python -m app.jobs.run_alerts`. Add a CloudWatch alarm on the log group for `ERROR`.
Locally: `docker compose --profile jobs run --rm alerts`.

## Common problems
- **Spray advisory fails:** the backend needs outbound internet access (to api.open-meteo.com). In a private subnet, add a NAT gateway or use public subnets for the backend task.
- **Backend unhealthy**: check the logs for DB connection errors. Verify `sg-db` allows `sg-app` and that the `DATABASE_URL` driver prefix is `mysql+pymysql://`.
- **Scan returns 503**: backend cannot reach `ml_service`; check `ML_SERVICE_URL` and the security groups.
- **Images not saved to S3**: the task role lacks `s3:PutObject` or `S3_BUCKET` is empty.
- **Upload fails with 413**: ALB/nginx body limit; `client_max_body_size` is 10m in `frontend/nginx.conf`.
