# TrustShare – Documentation

Start with the [project README](../README.md) for an overview, then use this index.

## Using and running TrustShare

| Document | What it covers |
|---|---|
| [User guide](user-guide.md) | Step-by-step guide for users and administrators, with screenshots of every screen |
| [Setup and configuration](setup.md) | Running with Docker, local HTTPS, Azure Blob Storage or AWS S3, creating the first admin and demo data, environment variables, tests, Postman, troubleshooting |
| [Features](features.md) | The complete feature list, grouped by area |
| [Deployment guide](deployment.md) | Production setup and step-by-step deployment to a free Azure VM with HTTPS, operations, backups, troubleshooting |
| [API reference](api.md) | Every endpoint by module, with the permission it needs |

## Design

| Document | What it covers |
|---|---|
| [Requirements](requirements.md) | Problem and objective, roles, permission matrix, functional and non-functional requirements, user stories |
| [Architecture](architecture.md) | System overview, backend layers, request flows, security design, milestone additions |
| [Database design](database.md) | PostgreSQL tables, MongoDB collections, Redis keys, object storage |
| [Encryption and key management](key-management.md) | Envelope encryption, algorithms, key lifecycle (creation, rotation, recovery, deletion), the secure vault |
| [Wireframes](wireframes.html) | The UI plan made before building (open the file in a browser) |
| [AWS IAM policy](aws-iam-policy.json) | Least-privilege policy for using real AWS S3 |

## Evaluation

| Document | What it covers |
|---|---|
| [Project brief coverage](brief-coverage.md) | Every item of the project brief → where it is implemented and how it is tested, plus what was done differently and what is out of scope |
| [Screenshots](screenshots/) | 37 screens of the running application (demo data, personal details masked) |
| [Postman collections](../postman/) | API checks for Milestones 2 and 3 |
