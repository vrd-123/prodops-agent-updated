# Professional Mermaid Diagram Templates for ProdOps Bot

Generic structure and styling references for Mermaid diagrams. When explaining a ticket or process, **always** derive diagram content from **that ticket's** Jira data (description, comments, changelog, linked issues). Do **not** hardcode content from another ticket.

## Color Palette

### Component Type Colors
* **External Systems / Clients**: `#00D9FF` (Bright Cyan) - White text
* **Routing / Gateways / Load Balancers**: `#FF9800` (Bright Orange) - Dark text
* **Internal Services / Actions**: `#4CAF50` (Bright Green) - White text
* **Databases / Storage**: `#9C27B0` (Bright Purple) - White text
* **File Systems / Buckets**: `#FFC107` (Bright Yellow) - Dark text
* **Data Processing / ETL / Pipelines**: `#009688` (Bright Teal) - White text
* **Networking / SFTP / VPN**: `#3F51B5` (Bright Indigo) - White text
* **Security / IAM / Auth**: `#F44336` (Bright Red) - White text
* **Decision Points / Blockers**: `#E91E63` (Bright Pink) - White text
* **Status: Done / Success**: `#4CAF50` (Bright Green) - White text
* **Status: In Progress**: `#2196F3` (Bright Blue) - White text
* **Status: Blocked / Closed**: `#F44336` (Bright Red) - White text
* **Status: Waiting / Pending**: `#FF9800` (Bright Orange) - Dark text

---

## Template 1: Ticket Resolution Flow

Use the **target ticket's** actual resolution steps from comments/changelog. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'primaryBorderColor':'#2E7D32',
  'lineColor':'#2196F3',
  'secondaryColor':'#FF9800',
  'tertiaryColor':'#9C27B0',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'edgeLabelBackground':'#1E1E1E',
  'clusterBkg':'#3D3D3D',
  'clusterBorder':'#4CAF50',
  'defaultLinkColor':'#2196F3',
  'titleColor':'#FFFFFF',
  'tertiaryBorderColor':'#7B1FA2'
}}}%%
flowchart TD
    A([🎫 Ticket Created]) --> B[🔀 Route to Correct Board]
    B --> C{❓ Prerequisites Complete?}
    C -->|✅ Yes| D[⚙️ Execute Resolution]
    C -->|❌ No| E[📋 Gather Missing Info]
    E --> F[📤 Request from Client/Team]
    F --> G[📥 Info Received]
    G --> C
    D --> H[🔄 Deploy / Implement]
    H --> I([✅ Resolved])

    style A fill:#00D9FF,stroke:#0097A7,color:#000
    style B fill:#FF9800,stroke:#E65100,color:#000
    style C fill:#E91E63,stroke:#AD1457,color:#fff
    style D fill:#4CAF50,stroke:#2E7D32,color:#fff
    style E fill:#F44336,stroke:#B71C1C,color:#fff
    style F fill:#3F51B5,stroke:#1A237E,color:#fff
    style G fill:#009688,stroke:#004D40,color:#fff
    style H fill:#9C27B0,stroke:#4A148C,color:#fff
    style I fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## Template 2: Infrastructure / Data Flow Architecture

Use the **target ticket's** infrastructure components from description/comments. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'primaryBorderColor':'#2E7D32',
  'lineColor':'#2196F3',
  'secondaryColor':'#FF9800',
  'tertiaryColor':'#9C27B0',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'edgeLabelBackground':'#1E1E1E',
  'clusterBkg':'#3D3D3D',
  'clusterBorder':'#4CAF50',
  'defaultLinkColor':'#2196F3',
  'titleColor':'#FFFFFF',
  'tertiaryBorderColor':'#7B1FA2'
}}}%%
flowchart LR
    subgraph Client["🏥 Client Environment"]
        SRC[💾 Source System]
    end

    subgraph Transport["🔒 Secure Transport"]
        PROTO[🔌 Protocol / Gateway]
    end

    subgraph Platform["☁️ Abacus NextGen"]
        LAND[📥 Landing Zone]
        PROC[🔄 Processing Pipeline]
        STORE[(🗄️ Data Store)]
        OUT[📊 Output / Analytics]
    end

    subgraph Security["🔒 Security & IAM"]
        AUTH[🔑 Authentication]
        FW[🛡️ Firewall / Whitelist]
    end

    SRC -->|"Upload Files"| PROTO
    PROTO -->|"Authenticated"| LAND
    AUTH -.->|"Validates"| PROTO
    FW -.->|"IP Whitelist"| PROTO
    LAND -->|"ETL Pipeline"| PROC
    PROC -->|"Transformed"| STORE
    STORE -->|"Reports"| OUT

    style SRC fill:#00D9FF,stroke:#0097A7,color:#000
    style PROTO fill:#3F51B5,stroke:#1A237E,color:#fff
    style LAND fill:#FFC107,stroke:#F57F17,color:#000
    style PROC fill:#009688,stroke:#004D40,color:#fff
    style STORE fill:#9C27B0,stroke:#4A148C,color:#fff
    style OUT fill:#4CAF50,stroke:#2E7D32,color:#fff
    style AUTH fill:#F44336,stroke:#B71C1C,color:#fff
    style FW fill:#F44336,stroke:#B71C1C,color:#fff
```

---

## Template 3: Ticket Communication Sequence

Use the **target ticket's** actual commenters and actions from the comment history. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'actorBkg':'#00D9FF',
  'actorTextColor':'#000',
  'actorBorder':'#0097A7',
  'activationBorderColor':'#4CAF50',
  'signalColor':'#FFFFFF',
  'signalTextColor':'#FFFFFF',
  'noteBkgColor':'#3D3D3D',
  'noteBorderColor':'#4CAF50',
  'noteTextColor':'#FFFFFF',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'loopTextColor':'#FFFFFF',
  'labelBoxBkgColor':'#3D3D3D',
  'labelBoxBorderColor':'#4CAF50',
  'labelTextColor':'#FFFFFF',
  'fontSize':'13px'
}}}%%
sequenceDiagram
    participant REP as 👤 Reporter
    participant LEAD as 👤 Team Lead
    participant INFRA as ⚙️ Infra Engineer
    participant CLIENT as 🏥 Client

    REP->>LEAD: 🎫 Filed ticket
    Note over REP,LEAD: 📅 Date - Board/Context

    LEAD->>REP: 📋 Listed prerequisites
    Note over LEAD: ❓ Info gaps identified

    REP->>CLIENT: 📤 Requested credentials
    CLIENT-->>REP: 🔑 Sent SSH key + IPs

    REP->>INFRA: 📥 Handed off prerequisites
    INFRA->>INFRA: 🔄 Deploy infrastructure
    Note over INFRA: ✅ Provisioned successfully
```

---

## Template 4: Ticket Relationship Map

Use the **target ticket's** actual linked issues and contributors from Jira fields. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'primaryBorderColor':'#2E7D32',
  'lineColor':'#2196F3',
  'secondaryColor':'#FF9800',
  'tertiaryColor':'#9C27B0',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'edgeLabelBackground':'#1E1E1E',
  'clusterBkg':'#3D3D3D',
  'clusterBorder':'#4CAF50',
  'defaultLinkColor':'#2196F3',
  'titleColor':'#FFFFFF',
  'tertiaryBorderColor':'#7B1FA2'
}}}%%
graph TB
    subgraph Tickets["🎫 Linked Issues"]
        MAIN["🎫 TICKET-KEY<br/>Ticket Summary"]
        LINKED1["🔗 LINKED-KEY-1<br/>Linked Summary 1"]
        LINKED2["🔗 LINKED-KEY-2<br/>Linked Summary 2"]
    end

    subgraph People["👥 Contributors"]
        P1(("👤<br/>Person 1<br/>Reporter"))
        P2(("👤<br/>Person 2<br/>Assignee"))
        P3(("👤<br/>Person 3<br/>Commenter"))
    end

    LINKED1 -->|"relates to"| MAIN
    LINKED2 -->|"cloned to"| MAIN
    P1 -.-|"reported"| MAIN
    P2 -.-|"assigned"| MAIN
    P3 -.-|"commented"| MAIN

    style MAIN fill:#00D9FF,stroke:#0097A7,color:#000
    style LINKED1 fill:#FF9800,stroke:#E65100,color:#000
    style LINKED2 fill:#FF9800,stroke:#E65100,color:#000
    style P1 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style P2 fill:#9C27B0,stroke:#4A148C,color:#fff
    style P3 fill:#009688,stroke:#004D40,color:#fff
```

---

## Template 5: Status Lifecycle

Use the **target ticket's** actual status transitions from the changelog. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'lineColor':'#2196F3',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'labelColor':'#FFFFFF',
  'altBackground':'#3D3D3D',
  'fontSize':'14px'
}}}%%
stateDiagram-v2
    direction LR

    [*] --> Backlog: 🎫 Created
    Backlog --> InProgress: 👤 Assigned by Lead
    InProgress --> Blocked: ❌ Missing Prerequisites
    Blocked --> InProgress: ✅ Info Received
    InProgress --> Done: 🚀 Deployed

    note right of Backlog: 📅 Created Date
    note right of Blocked: ⏳ Waiting on Client
    note right of Done: ✅ Resolution Summary
```

---

## Template 6: Deployment Pipeline

Use the **target ticket's** actual deployment steps from description/comments. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'primaryBorderColor':'#2E7D32',
  'lineColor':'#2196F3',
  'secondaryColor':'#FF9800',
  'tertiaryColor':'#9C27B0',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'edgeLabelBackground':'#1E1E1E',
  'clusterBkg':'#3D3D3D',
  'clusterBorder':'#4CAF50',
  'defaultLinkColor':'#2196F3',
  'titleColor':'#FFFFFF',
  'tertiaryBorderColor':'#7B1FA2'
}}}%%
flowchart TD
    subgraph Config["📁 Configuration"]
        C1[📝 Update Tenant Config]
        C2[🔑 Add SSH Keys]
        C3[🛡️ Set CIDR Whitelist]
    end

    subgraph Deploy["🚀 Deployment"]
        D1[⚙️ Run Deployment Tool]
        D2[☁️ Provision Cloud Resources]
        D3[🌐 Create DNS Records]
        D4[👤 Create Service Users]
    end

    subgraph Verify["✅ Verification"]
        V1[🔌 Test Connectivity]
        V2[📤 Test File Upload]
        V3[🔄 Verify Pipeline Pickup]
        V4[📋 Hand Off to Client]
    end

    C1 --> C2 --> C3
    C3 --> D1
    D1 --> D2 --> D3 --> D4
    D4 --> V1
    V1 --> V2 --> V3 --> V4

    style C1 fill:#FFC107,stroke:#F57F17,color:#000
    style C2 fill:#F44336,stroke:#B71C1C,color:#fff
    style C3 fill:#F44336,stroke:#B71C1C,color:#fff
    style D1 fill:#9C27B0,stroke:#4A148C,color:#fff
    style D2 fill:#3F51B5,stroke:#1A237E,color:#fff
    style D3 fill:#3F51B5,stroke:#1A237E,color:#fff
    style D4 fill:#009688,stroke:#004D40,color:#fff
    style V1 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style V2 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style V3 fill:#4CAF50,stroke:#2E7D32,color:#fff
    style V4 fill:#00D9FF,stroke:#0097A7,color:#000
```

---

## Template 7: API & Integrations Call Flow

**Use when** the ticket involves API errors, integration failures, webhooks, OAuth, FHIR APIs, or external service calls.

**Mandatory rule:** Every API/integration diagram MUST show **where calls originate** (caller component + environment) and **what they target** (full endpoint URL or service path, HTTP method, auth type). Edge labels must include method + path (e.g. `POST /api/event/nasco`).

Derive all nodes and edges from the **target ticket's** description, comments, and logs. Placeholder structure only:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#4CAF50',
  'primaryTextColor':'#ffffff',
  'primaryBorderColor':'#2E7D32',
  'lineColor':'#2196F3',
  'secondaryColor':'#FF9800',
  'tertiaryColor':'#9C27B0',
  'background':'#1E1E1E',
  'mainBkgColor':'#2D2D2D',
  'textColor':'#FFFFFF',
  'edgeLabelBackground':'#1E1E1E',
  'clusterBkg':'#3D3D3D',
  'clusterBorder':'#4CAF50',
  'defaultLinkColor':'#2196F3',
  'titleColor':'#FFFFFF',
  'tertiaryBorderColor':'#7B1FA2'
}}}%%
flowchart LR
    subgraph Caller["🏥 Caller — Where calls are made"]
        APP[⚙️ Client App / Job<br/>env + component name]
    end

    subgraph Gateway["🌐 Routing Layer"]
        EDGE[🌐 API Gateway / Proxy<br/>Apigee / ALB / Ingress]
    end

    subgraph Target["🎯 Target — What is called"]
        API[⚙️ Abacus API Service<br/>host + route path]
        AUTH[🔒 Auth Layer<br/>IAM / OAuth / API Key]
    end

    subgraph Response["📥 Response"]
        OK[✅ 200 Success]
        ERR[❌ 4xx/5xx Error<br/>error message from logs]
    end

    APP -->|"METHOD /path<br/>protocol + auth"| EDGE
    EDGE -->|"forward to backend"| API
    AUTH -.->|"validates"| API
    API -->|"success"| OK
    API -->|"failure"| ERR

    style APP fill:#00D9FF,stroke:#0097A7,color:#000
    style EDGE fill:#FF9800,stroke:#E65100,color:#000
    style API fill:#4CAF50,stroke:#2E7D32,color:#fff
    style AUTH fill:#F44336,stroke:#B71C1C,color:#fff
    style OK fill:#4CAF50,stroke:#2E7D32,color:#fff
    style ERR fill:#F44336,stroke:#B71C1C,color:#fff
```

### API & Integrations — Required Edge Labels

| Edge | Must include |
|------|--------------|
| Caller → Gateway | HTTP method, path, protocol (HTTPS), auth type (SigV4, OAuth, API key) |
| Gateway → Target | Backend host or service name, forwarded path |
| Target → Response | Status code (200, 403, 500) and error class from ticket logs |

### API & Integrations — Data Sources (priority order)

1. Ticket description — URLs, endpoints, error codes
2. Comments — API gateway logs, request/response samples
3. Attachments — log files with HTTP traces, screenshots of API consoles
4. Confluence design docs — only if linked in ticket or service config

**Do NOT** draw a generic "API box" without naming the caller, endpoint, and method.

---

## Usage Guidelines

1. **Always include the** `%%{init:}%%` directive at the start of every diagram
2. **Use emoji icons** consistently for component types (see Icon Reference below)
3. **Apply inline `style` rules** for consistent coloring on every node
4. **Use bright, high-contrast colors** that work on dark backgrounds
5. **Label all connections** with action/protocol/relationship info
6. **Use subgraphs** to organize components by zone/layer/phase
7. **Keep node labels short** — under 40 characters; use `<br/>` for line breaks
8. **Remove unused placeholder nodes** — only include what the ticket data supports
9. **Add more nodes** if the ticket has more steps/people/issues — copy the pattern
10. **Never reuse another ticket's diagram content** — derive nodes and edges from the ticket being explained
11. **API & Integrations tickets** — use Template 7; every call arrow must show caller → endpoint with method, path, and auth; include error responses from logs when present

---

## Icon Reference

* 🎫 Tickets / Issues / Work Items
* 🏥 External Systems (Clients, Vendors, Partners)
* 🌐 API Gateway / Load Balancer / DNS
* ⚙️ Application Services / Deployment Tools
* 🗄️ Databases (RDS, Postgres, etc.)
* 💾 Storage (S3, SFTP Landing, File Systems)
* 🔄 Data Processing / ETL / Pipelines
* 🔒 Security / IAM / Authentication
* 🔑 SSH Keys / Credentials / Secrets
* 🛡️ Firewall / Whitelist / Security Groups
* 🔀 Routing / Decision Points / Triage
* ✅ Success / Resolved / Completed
* ❌ Blocked / Failed / Closed / Error
* ⏳ Waiting / Pending / On Hold
* 📋 Prerequisites / Checklists / Requirements
* 📤 Outbound (Request sent, File uploaded)
* 📥 Inbound (Response received, File landed)
* 📊 Monitoring / Analytics / Reports
* 🔌 Networking / VPC / Connectivity
* 📅 Date / Time Operations / Milestones
* 📁 File / Folder / Config Operations
* 📝 Template / Transformation / Config Files
* 👤 Person / User / Assignee
* 👥 Team / Group / Contributors
* 🔗 Linked Issue / Dependency
* 🚀 Deploy / Launch / Go Live
* ☁️ Cloud Resources (AWS, Transfer Family, S3)